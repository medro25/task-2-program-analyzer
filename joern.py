import ast
import os
import subprocess
import tempfile
from pathlib import Path


class JoernAnalyzer:
    """Uses Joern to statically analyze Python source code."""

    DEFAULT_PATH = Path.home() / "bin" / "joern" / "joern-cli" / "joern"

    def __init__(self, joern_path=None):
        configured_path = joern_path or os.environ.get("JOERN_PATH")
        configured_path = configured_path or None
        self.joern = Path(configured_path or self.DEFAULT_PATH)

        if not self.joern.exists():
            raise FileNotFoundError(f"Joern not found: {self.joern}")

    def analyze(self, source):
        """Run Joern against a Python file and return parsed analysis data."""

        source = Path(source)
        

        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            query_file = temp / "analysis.sc"
            output_file = temp / "results.txt"

            query_file.write_text(
                self._query(source.resolve(), output_file.resolve())
            )

            process = subprocess.run(
                [str(self.joern), "--script", str(query_file)],
                capture_output=True,
                cwd=temp,
                text=True,
            )

            if process.returncode:
                details = process.stderr.strip() or process.stdout.strip()
                raise RuntimeError(details or "Joern analysis failed.")

            if not output_file.exists():
                raise RuntimeError("Joern produced no result.")

            return self._parse(output_file.read_text(), source)

    @staticmethod
    def _parse(text, source):
        """Convert Joern output into Python data structures."""

        source = Path(source)
        source_text = source.read_text(errors="replace")
        source_lines = source_text.splitlines()
        contexts = JoernAnalyzer._source_contexts(source_text)
        functions = []
        current = None

        for line in text.splitlines():
            if line.startswith("FUNCTION|"):
                current = {
                    "name": line.split("|", 1)[1],
                    "calls": [],
                }
                functions.append(current)

            elif line.startswith("CALL|") and current:
                parts = line.split("|", 4)

                if len(parts) != 5:
                    continue

                _, class_name, method, number, code = parts
                number = int(number)

                statement = (
                    source_lines[number - 1].strip()
                    if 0 < number <= len(source_lines)
                    else code
                )
                context = JoernAnalyzer._context_for_line(contexts, number)

                if context:
                    class_name = context["class"]
                    method = context["method"]

                current["calls"].append(
                    {
                        "class": class_name,
                        "method": method,
                        "line": number,
                        "call": code,
                        "statement": statement,
                    }
                )

        JoernAnalyzer._clean_calls(functions, source_text)

        return {
            "file": source.name,
            "path": str(source),
            "functions": functions,
        }

    @classmethod
    def _query(cls, source, output):
        """Create the Joern CPG query."""

        source = cls._scala_string(source)
        output = cls._scala_string(output)

        return f'''
import io.shiftleft.semanticcpg.language.*
import java.io.PrintWriter

importCode("{source}")

val writer = new PrintWriter("{output}")

val functions = cpg.method
    .filter {{ m =>
        m.lineNumber.isDefined &&
        m.fullName.startsWith(":<module>.") &&
        (m.name.startsWith("<") == false) &&
        (m.name.contains("metaClassAdapter") == false)
    }}
    .l

val functionNames = functions.map(_.name).toSet

functions.foreach {{ function =>

    val displayName =
        function.fullName.stripPrefix(":<module>.")

    writer.println(
        "FUNCTION|" +
        displayName
    )

    val calls = cpg.call
        .filter {{ call =>
            functionNames.contains(call.name) &&
            call.name == function.name &&
            call.lineNumber != function.lineNumber &&
            (call.code.trim.startsWith("def ") == false) &&
            (call.code.trim.startsWith("async def ") == false)
        }}
        .l

    calls.foreach {{ call =>

        val callerMethod = call.method.name
        val callerFullName = call.method.fullName
        val parts = callerFullName.split("\\\\.")

        val callerClass =
            if (
                callerFullName.startsWith(":<module>.") &&
                parts.length >= 3
            )
                parts(parts.length - 2)
            else
                "GLOBAL"

        val methodName =
            if (callerMethod == "<module>")
                "GLOBAL"
            else
                callerMethod

        writer.println(
            "CALL|" +
            callerClass + "|" +
            methodName + "|" +
            call.lineNumber.getOrElse(-1) + "|" +
            call.code.replace("\\n", " ")
        )
    }}
}}

writer.close()
'''

    @staticmethod
    def _scala_string(path):
        return str(path).replace("\\", "\\\\").replace('"', '\\"')

    @classmethod
    def _clean_calls(cls, functions, source_text):
        function_names = [
            cls._short_name(function["name"])
            for function in functions
        ]
        duplicate_names = {
            name
            for name in function_names
            if function_names.count(name) > 1
        }
        targets_by_line = cls._targets_by_line(source_text)

        for function in functions:
            short_name = cls._short_name(function["name"])
            calls = []

            for call in function["calls"]:
                statement = call["statement"].lstrip()

                if statement.startswith(("def ", "async def ")):
                    continue

                targets = targets_by_line.get(call.get("line"), set())
                matching_targets = {
                    target
                    for target in targets
                    if cls._short_name(target) == short_name
                }

                if (
                    short_name in duplicate_names
                    and matching_targets
                    and function["name"] not in matching_targets
                ):
                    continue

                calls.append(call)

            function["calls"] = calls

    @staticmethod
    def _short_name(name):
        return name.rsplit(".", 1)[-1]

    @staticmethod
    def _targets_by_line(source_text):
        try:
            tree = ast.parse(source_text)
        except SyntaxError:
            return {}

        class_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        }
        var_types = {}
        init_attrs = {}
        attr_types = {}
        targets = {}
        class_stack = []

        for class_node in ast.walk(tree):
            if not isinstance(class_node, ast.ClassDef):
                continue

            for node in class_node.body:
                if not (isinstance(node, ast.FunctionDef) and node.name == "__init__"):
                    continue

                params = [arg.arg for arg in node.args.args]

                for statement in ast.walk(node):
                    if not isinstance(statement, ast.Assign):
                        continue

                    for target in statement.targets:
                        if (
                            isinstance(target, ast.Attribute)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "self"
                            and isinstance(statement.value, ast.Name)
                            and statement.value.id in params
                        ):
                            index = params.index(statement.value.id) - 1
                            if index < 0:
                                continue

                            init_attrs.setdefault(class_node.name, {})[
                                target.attr
                            ] = index

        for statement in tree.body:
            if not (
                isinstance(statement, ast.Assign)
                and isinstance(statement.value, ast.Call)
                and isinstance(statement.value.func, ast.Name)
                and statement.value.func.id in class_names
            ):
                continue

            class_name = statement.value.func.id

            for target in statement.targets:
                if not isinstance(target, ast.Name):
                    continue

                var_types[target.id] = class_name

                for attr, index in init_attrs.get(class_name, {}).items():
                    if index < len(statement.value.args):
                        argument = statement.value.args[index]

                        if isinstance(argument, ast.Name) and argument.id in var_types:
                            attr_types.setdefault(class_name, {})[attr] = var_types[
                                argument.id
                            ]

        def receiver_type(node):
            if isinstance(node, ast.Name):
                if node.id == "self" and class_stack:
                    return class_stack[-1]
                return var_types.get(node.id)

            if isinstance(node, ast.Attribute):
                owner = receiver_type(node.value)
                return attr_types.get(owner, {}).get(node.attr)

            return None

        def visit(node):
            if isinstance(node, ast.ClassDef):
                class_stack.append(node.name)

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                owner = receiver_type(node.func.value)

                if owner:
                    targets.setdefault(node.lineno, set()).add(f"{owner}.{node.func.attr}")

            for child in ast.iter_child_nodes(node):
                visit(child)

            if isinstance(node, ast.ClassDef):
                class_stack.pop()

        visit(tree)
        return targets

    @staticmethod
    def _source_contexts(source_text):
        """Build source-line ranges for Python class/function context."""

        try:
            tree = ast.parse(source_text)
        except SyntaxError:
            return []

        contexts = []

        def visit(node, class_stack=None):
            class_stack = class_stack or []

            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    visit(child, class_stack + [child.name])
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    contexts.append(
                        {
                            "start": child.lineno,
                            "end": getattr(child, "end_lineno", child.lineno),
                            "class": class_stack[-1] if class_stack else "GLOBAL",
                            "method": child.name,
                        }
                    )
                    visit(child, class_stack)
                else:
                    visit(child, class_stack)

        visit(tree)
        return contexts

    @staticmethod
    def _context_for_line(contexts, line_number):
        matches = [
            context
            for context in contexts
            if context["start"] <= line_number <= context["end"]
        ]

        if not matches:
            return None

        return min(matches, key=lambda context: context["end"] - context["start"])
