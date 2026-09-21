import ast
from pathlib import Path


class PathChecker:
    """Adds simple reachability facts for reported call locations."""

    def add_path_checks(self, result, source):
        source = Path(source)
        source_lines = source.read_text(errors="replace").splitlines()
        unreachable = self._unreachable_lines("\n".join(source_lines))

        total = 0
        unreachable_count = 0

        for function in result["functions"]:
            for call in function["calls"]:
                total += 1
                line = call.get("line", -1)

                if line in unreachable:
                    unreachable_count += 1
                    call["path"] = {
                        "status": "UNREACHABLE",
                        "reason": unreachable[line],
                    }
                elif line > 0:
                    call["path"] = {
                        "status": "REACHABLE",
                        "reason": (
                            "No earlier terminating statement blocks this call "
                            "in the same block."
                        ),
                    }
                else:
                    call["path"] = {
                        "status": "UNKNOWN",
                        "reason": "Joern did not provide a usable source line.",
                    }

        result["check_path"] = {
            "enabled": True,
            "calls_checked": total,
            "unreachable_calls": unreachable_count,
        }

        return result

    def _unreachable_lines(self, source_text):
        try:
            tree = ast.parse(source_text)
        except SyntaxError:
            return {}

        source_lines = source_text.splitlines()
        unreachable = {}

        def line_text(line_number):
            if 0 < line_number <= len(source_lines):
                return source_lines[line_number - 1].strip()
            return ""

        def mark_statement(stmt, reason):
            start = getattr(stmt, "lineno", None)
            end = getattr(stmt, "end_lineno", start)

            if not start:
                return

            for line in range(start, end + 1):
                unreachable[line] = reason

        def terminal_reason(stmt):
            if isinstance(stmt, ast.Return):
                return f"Appears after return at line {stmt.lineno}: {line_text(stmt.lineno)}"
            if isinstance(stmt, ast.Raise):
                return f"Appears after raise at line {stmt.lineno}: {line_text(stmt.lineno)}"
            if isinstance(stmt, ast.Break):
                return f"Appears after break at line {stmt.lineno}: {line_text(stmt.lineno)}"
            if isinstance(stmt, ast.Continue):
                return f"Appears after continue at line {stmt.lineno}: {line_text(stmt.lineno)}"
            if isinstance(stmt, ast.If) and stmt.body and stmt.orelse:
                if block_always_terminates(stmt.body) and block_always_terminates(stmt.orelse):
                    return (
                        "Appears after an if statement where both branches "
                        f"terminate at line {stmt.lineno}."
                    )
            return None

        def block_always_terminates(statements):
            for stmt in statements:
                if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    continue
                if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                    return True
                if isinstance(stmt, ast.If) and stmt.body and stmt.orelse:
                    if block_always_terminates(stmt.body) and block_always_terminates(stmt.orelse):
                        return True
            return False

        def scan_block(statements):
            reachable = True
            blocked_by = None

            for stmt in statements:
                if not reachable:
                    mark_statement(stmt, blocked_by)
                    continue

                scan_nested_blocks(stmt)

                reason = terminal_reason(stmt)

                if reason:
                    reachable = False
                    blocked_by = reason

        def scan_nested_blocks(stmt):
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scan_block(stmt.body)
                return

            if isinstance(stmt, ast.ClassDef):
                scan_block(stmt.body)
                return

            for field in (
                "body",
                "orelse",
                "finalbody",
            ):
                value = getattr(stmt, field, None)

                if isinstance(value, list):
                    scan_block(value)

            for handler in getattr(stmt, "handlers", []):
                scan_block(handler.body)

        scan_block(tree.body)
        return unreachable
