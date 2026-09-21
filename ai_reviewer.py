import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


logging.getLogger(__name__).addHandler(logging.NullHandler())


class AIReviewer:
    """Optional OpenAI-powered explanation layer for analysis reports."""

    API_URL = "https://api.openai.com/v1/responses"
    DEFAULT_MODEL = "gpt-5"
    REQUEST_TIMEOUT_SECONDS = 90
    MAX_ATTEMPTS = 2
    RETRY_DELAY_SECONDS = 3
    RETRYABLE_HTTP_CODES = {408, 429, 500, 502, 503, 504}

    def __init__(self, model=None, timeout=None, max_attempts=None, retry_delay=None):
        self.model = model or os.environ.get("OPENAI_MODEL") or self.DEFAULT_MODEL
        self.timeout = timeout or self.REQUEST_TIMEOUT_SECONDS
        self.max_attempts = max_attempts or self.MAX_ATTEMPTS
        self.retry_delay = retry_delay if retry_delay is not None else self.RETRY_DELAY_SECONDS
        self.logger = logging.getLogger(__name__)

    def review(self, result, source):
        api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key or api_key == "your_openai_api_key_here":
            return (
                "AI review was requested, but OPENAI_API_KEY is not set. "
                "Set OPENAI_API_KEY or run without --ai-review."
            )

        self.logger.info(
            "AI review started for %s using %s",
            Path(source).name,
            self.model,
        )
        prompt = self._prompt(result, source)
        payload = {
            "model": self.model,
            "store": False,
            "input": [
                {
                    "role": "developer",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "You explain static-analysis reports. Do not invent "
                                "functions, calls, vulnerabilities, or reachability facts. "
                                "Use only the analyzer result and source excerpt. Mention "
                                "risk for vulnerabilities or bugs only when the source excerpt "
                                "supports it, and clearly label uncertainty. Use likelihood "
                                "labels, not mathematical probabilities: HIGH, MEDIUM, LOW, "
                                "NOT EVIDENT, or UNKNOWN. The functions list groups each "
                                "defined function with locations where that function is called; "
                                "do not describe that callee-based grouping as a mapping "
                                "inconsistency. Keep the review concise and practical."
                            ),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            ],
        }

        request = urllib.request.Request(
            self.API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            data = self._send_request(request)
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            self.logger.error("AI review failed with HTTP %s", error.code)
            return f"AI review failed with HTTP {error.code}: {details}"
        except Exception as error:
            self.logger.error(
                "AI review failed after %d attempts: %s",
                self.max_attempts,
                error,
            )
            return (
                f"AI review failed after {self.max_attempts} "
                f"attempts: {error}"
            )

        self.logger.info("AI review finished")
        return self._extract_text(data) or "AI review completed with no text output."

    def _send_request(self, request):
        """Send the OpenAI request with a bounded retry loop."""

        for attempt in range(1, self.max_attempts + 1):
            self.logger.info(
                "AI review attempt %d/%d, timeout %ds",
                attempt,
                self.max_attempts,
                self.timeout,
            )
            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout,
                ) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                if not self._should_retry_http(error, attempt):
                    raise
                last_error = error
            except (TimeoutError, urllib.error.URLError, OSError) as error:
                if attempt == self.max_attempts:
                    raise
                last_error = error

            self.logger.warning(
                "AI review attempt %d/%d failed: %s",
                attempt,
                self.max_attempts,
                last_error,
            )
            if self.retry_delay:
                self.logger.info("Retrying AI review in %ds", self.retry_delay)
                time.sleep(self.retry_delay)

        raise last_error

    def _should_retry_http(self, error, attempt):
        return (
            error.code in self.RETRYABLE_HTTP_CODES
            and attempt < self.max_attempts
        )

    def _prompt(self, result, source):
        source = Path(source)
        source_text = source.read_text(errors="replace")

        summary = {
            "file": result["file"],
            "functions": result["functions"],
            "check_path": result.get("check_path"),
        }

        return (
            "Review this static-analysis result for a Python program analyzer.\n\n"
            "Important: each function entry contains call locations where that "
            "function is called. It is callee-based, not caller-based.\n\n"
            "Explain:\n"
            "1. what functions were found,\n"
            "2. what call locations matter,\n"
            "3. what CHECK PATH says if present,\n"
            "4. a vulnerability and bug risk table using likelihood labels only,\n"
            "5. why the visible risks may matter for security analysis,\n"
            "6. any limitations of the result.\n\n"
            "For the risk table, include these categories and mark each as "
            "HIGH, MEDIUM, LOW, NOT EVIDENT, or UNKNOWN: SQL injection, XSS, "
            "path traversal/file access, command injection, SSRF/network access, "
            "insecure deserialization, hardcoded secrets, authentication or "
            "authorization weakness, weak cryptography, input validation bug, "
            "error handling bug, dead code/unreachable code, resource leak, "
            "and other visible bug risk. For each category, give a one-sentence "
            "reason grounded in the source excerpt. If the excerpt does not show "
            "evidence, write NOT EVIDENT instead of guessing.\n\n"
            "Analyzer result JSON:\n"
            f"{json.dumps(summary, indent=2)}\n\n"
            "Source excerpt:\n"
            f"{source_text[:12000]}"
        )

    @staticmethod
    def _extract_text(data):
        if isinstance(data.get("output_text"), str):
            return data["output_text"].strip()

        chunks = []

        for item in data.get("output", []):
            for content in item.get("content", []):
                text = content.get("text")

                if isinstance(text, str):
                    chunks.append(text)

        return "\n".join(chunks).strip()
