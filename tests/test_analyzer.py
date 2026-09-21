import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_reviewer import AIReviewer
from joern import JoernAnalyzer
from path_checker import PathChecker
from reporter import Reporter


class JoernParserTests(unittest.TestCase):

    def test_joern_path_can_come_from_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            joern = Path(temp) / "joern"
            joern.touch()

            with patch.dict("os.environ", {"JOERN_PATH": str(joern)}):
                analyzer = JoernAnalyzer()

        self.assertEqual(analyzer.joern, joern)

    def test_parse_uses_complete_source_statement(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.py"
            source.write_text(
                "\n".join(
                    [
                        "def helper():",
                        "    pass",
                        "",
                        "def main():",
                        "    result = helper()",
                    ]
                )
            )

            result = JoernAnalyzer._parse(
                "FUNCTION|helper\nCALL|GLOBAL|main|5|helper()",
                source,
            )

        self.assertEqual(result["file"], "sample.py")
        self.assertEqual(result["functions"][0]["name"], "helper")
        self.assertEqual(
            result["functions"][0]["calls"][0]["statement"],
            "result = helper()",
        )

    def test_parse_labels_nested_function_context_as_global_class(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.py"
            source.write_text(
                "\n".join(
                    [
                        "def init(app):",
                        "    def route_get():",
                        "        return route_post()",
                        "",
                        "    def route_post():",
                        "        return 'ok'",
                    ]
                )
            )

            result = JoernAnalyzer._parse(
                "FUNCTION|init.route_post\nCALL|init|route_get|3|route_post()",
                source,
            )

        call = result["functions"][0]["calls"][0]

        self.assertEqual(call["class"], "GLOBAL")
        self.assertEqual(call["method"], "route_get")
        self.assertEqual(call["statement"], "return route_post()")


class ReporterTests(unittest.TestCase):

    def test_reporter_saves_analysis_report(self):
        result = {
            "file": "sample.py",
            "functions": [
                {
                    "name": "helper",
                    "calls": [
                        {
                            "class": "GLOBAL",
                            "method": "main",
                            "statement": "result = helper()",
                        }
                    ],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp:
            path = Reporter(temp).save(result)
            text = path.read_text()

        self.assertEqual(path.name, "sample_analysis.txt")
        self.assertIn("Function: helper", text)
        self.assertIn("<GLOBAL, main, result = helper()>", text)

    def test_reporter_includes_check_path_section_when_enabled(self):
        result = {
            "file": "sample.py",
            "functions": [
                {
                    "name": "dead",
                    "calls": [
                        {
                            "class": "GLOBAL",
                            "method": "main",
                            "statement": "return dead()",
                            "path": {
                                "status": "UNREACHABLE",
                                "reason": "Appears after return at line 5",
                            },
                        }
                    ],
                }
            ],
            "check_path": {
                "enabled": True,
                "calls_checked": 1,
                "unreachable_calls": 1,
            },
        }

        with tempfile.TemporaryDirectory() as temp:
            path = Reporter(temp).save(result)
            text = path.read_text()

        self.assertEqual(path.name, "sample_path_analysis.txt")
        self.assertIn("CHECK PATH ANALYSIS", text)
        self.assertIn("Path: UNREACHABLE", text)
        self.assertIn("Unreachable calls: 1", text)

    def test_reporter_filename_includes_ai_and_path_tags(self):
        result = {
            "file": "sample.py",
            "functions": [],
            "check_path": {
                "enabled": True,
                "calls_checked": 0,
                "unreachable_calls": 0,
            },
            "ai_review": "No calls were found.",
        }

        with tempfile.TemporaryDirectory() as temp:
            path = Reporter(temp).save(result)

        self.assertEqual(path.name, "sample_path_ai_analysis.txt")


class PathCheckerTests(unittest.TestCase):

    def test_marks_call_after_return_as_unreachable(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.py"
            source.write_text(
                "\n".join(
                    [
                        "def helper():",
                        "    return 'ok'",
                        "",
                        "def main():",
                        "    return 'done'",
                        "    return helper()",
                    ]
                )
            )
            result = {
                "file": "sample.py",
                "functions": [
                    {
                        "name": "helper",
                        "calls": [
                            {
                                "class": "GLOBAL",
                                "method": "main",
                                "line": 6,
                                "call": "helper()",
                                "statement": "return helper()",
                            }
                        ],
                    }
                ],
            }

            checked = PathChecker().add_path_checks(result, source)

        call = checked["functions"][0]["calls"][0]

        self.assertEqual(call["path"]["status"], "UNREACHABLE")
        self.assertIn("return", call["path"]["reason"])
        self.assertEqual(checked["check_path"]["unreachable_calls"], 1)


class AIReviewerTests(unittest.TestCase):

    def test_ai_review_requires_api_key(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.py"
            source.write_text("def main():\n    pass\n")
            result = {
                "file": "sample.py",
                "functions": [],
            }

            with patch.dict("os.environ", {}, clear=True):
                review = AIReviewer().review(result, source)

        self.assertIn("OPENAI_API_KEY is not set", review)

    def test_ai_prompt_requests_vulnerability_risk_table(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.py"
            source.write_text("def main():\n    pass\n")
            result = {
                "file": "sample.py",
                "functions": [],
            }

            prompt = AIReviewer()._prompt(result, source)

        self.assertIn("vulnerability and bug risk table", prompt)
        self.assertIn("SQL injection", prompt)
        self.assertIn("XSS", prompt)
        self.assertIn("path traversal", prompt)
        self.assertIn("dead code/unreachable code", prompt)


if __name__ == "__main__":
    unittest.main()
