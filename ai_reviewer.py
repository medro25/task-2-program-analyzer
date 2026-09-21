import json
import os
import urllib.error
import urllib.request
from pathlib import Path


class AIReviewer:
    """Optional OpenAI-powered explanation layer for analysis reports."""

    API_URL = "https://api.openai.com/v1/responses"
    DEFAULT_MODEL = "gpt-5"

    def __init__(self, model=None):
        self.model = model or os.environ.get("OPENAI_MODEL") or self.DEFAULT_MODEL

    def review(self, result, source):
        api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key or api_key == "your_openai_api_key_here":
            return (
                "AI review was requested, but OPENAI_API_KEY is not set. "
                "Set OPENAI_API_KEY or run without --ai-review."
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
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            return f"AI review failed with HTTP {error.code}: {details}"
        except Exception as error:
            return f"AI review failed: {error}"

        return self._extract_text(data) or "AI review completed with no text output."

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
