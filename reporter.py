from pathlib import Path


class Reporter:
    """Creates and saves analysis reports."""

    def __init__(self, directory="reports"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, result):
        report = self._build(result)
        filename = self._filename(result)
        path = self.directory / filename
        path.write_text(report)
        return path

    def _filename(self, result):
        stem = Path(result["file"]).stem
        tags = []

        if result.get("check_path"):
            tags.append("path")

        if result.get("ai_review"):
            tags.append("ai")

        if tags:
            return f"{stem}_{'_'.join(tags)}_analysis.txt"

        return f"{stem}_analysis.txt"

    def _build(self, result):
        functions = result["functions"]
        total_calls = sum(len(function["calls"]) for function in functions)

        lines = [
            "=" * 60,
            "SIMPLE PYTHON PROGRAM ANALYZER",
            "=" * 60,
            "",
            f"Analyzed file: {result['file']}",
            f"Number of defined functions: {len(functions)}",
            "",
            "DEFINED FUNCTIONS",
            "-" * 60,
        ]

        if functions:
            lines.extend(function["name"] for function in functions)
        else:
            lines.append("No user-defined functions found.")

        lines += [
            "",
            "=" * 60,
            "FUNCTION CALL LOCATIONS",
            "=" * 60,
        ]

        for function in functions:
            lines.append(f"\nFunction: {function['name']}")

            if not function["calls"]:
                lines.append("  No calls found")
                continue

            for call in function["calls"]:
                lines.append(
                    f"  <{call['class']}, "
                    f"{call['method']}, "
                    f"{call['statement']}>"
                )

        if result.get("check_path"):
            lines += [
                "",
                "=" * 60,
                "CHECK PATH ANALYSIS",
                "=" * 60,
            ]

            for function in functions:
                for call in function["calls"]:
                    path = call.get("path")

                    if not path:
                        continue

                    lines += [
                        f"\nFunction: {function['name']}",
                        (
                            f"  Call: <{call['class']}, "
                            f"{call['method']}, "
                            f"{call['statement']}>"
                        ),
                        f"  Path: {path['status']}",
                        f"  Reason: {path['reason']}",
                    ]

            lines += [
                "",
                f"Calls checked: {result['check_path']['calls_checked']}",
                (
                    "Unreachable calls: "
                    f"{result['check_path']['unreachable_calls']}"
                ),
            ]

        if result.get("ai_review"):
            lines += [
                "",
                "=" * 60,
                "AI REVIEW",
                "=" * 60,
                result["ai_review"],
            ]

        lines += [
            "",
            "=" * 60,
            "SUMMARY",
            "=" * 60,
            f"Functions found: {len(functions)}",
            f"Function calls found: {total_calls}",
            "",
            "GLOBAL means that the call is outside a class or function.",
        ]

        return "\n".join(lines)
