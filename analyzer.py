import argparse
import logging
from pathlib import Path

from ai_reviewer import AIReviewer
from env_config import load_environment
from joern import JoernAnalyzer
from path_checker import PathChecker
from reporter import Reporter


class ProgramAnalyzer:
    """Coordinates analysis of Python files and report generation."""

    def __init__(
        self,
        dataset="dataset",
        reports="reports",
        joern_path=None,
        check_path=False,
        ai_review=False,
        ai_model=None,
    ):
        self.dataset = Path(dataset)
        self.joern = JoernAnalyzer(joern_path)
        self.path_checker = PathChecker() if check_path else None
        self.ai_reviewer = AIReviewer(ai_model) if ai_review else None
        self.reporter = Reporter(reports)
        self.logger = logging.getLogger(__name__)

    def run(self):
        """Analyze every Python file in the configured dataset directory."""

        files = sorted(self.dataset.rglob("*.py"))

        if not files:
            self.logger.warning("No Python files found in %s", self.dataset)
            return []

        self.logger.info("Found %d Python files", len(files))

        reports = []

        for index, source in enumerate(files, 1):
            self.logger.info("[%d/%d] Analyzing %s", index, len(files), source)

            try:
                reports.append(self.analyze_file(source))
            except Exception as error:
                self.logger.error("Failed: %s - %s", source.name, error)

        self.logger.info(
            "Finished: %d succeeded, %d failed",
            len(reports),
            len(files) - len(reports),
        )

        return reports

    def analyze_file(self, source):
        """Analyze one Python source file and save its report."""

        source = Path(source)

        if not source.exists():
            raise FileNotFoundError(f"File does not exist: {source}")

        if source.suffix.lower() != ".py":
            raise ValueError("Please provide a Python (.py) file.")

        result = self.joern.analyze(source)

        if self.path_checker:
            result = self.path_checker.add_path_checks(result, source)

        if self.ai_reviewer:
            result["ai_review"] = self.ai_reviewer.review(result, source)

        report = self.reporter.save(result)

        calls = sum(len(function["calls"]) for function in result["functions"])

        self.logger.info(
            "Found %d functions and %d calls",
            len(result["functions"]),
            calls,
        )
        self.logger.info("Saved: %s", report)

        return report


def _build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Statically analyze Python function definitions and function calls "
            "using Joern."
        )
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="dataset",
        help="Python file or dataset directory to analyze. Defaults to dataset/.",
    )
    parser.add_argument(
        "--reports",
        default="reports",
        help="Directory where analysis reports are saved.",
    )
    parser.add_argument(
        "--joern",
        default=None,
        help="Path to the Joern executable.",
    )
    parser.add_argument(
        "--check-path",
        action="store_true",
        help=(
            "Add CHECK PATH ANALYSIS for obvious unreachable call locations, "
            "such as calls after return statements."
        ),
    )
    parser.add_argument(
        "--ai-review",
        action="store_true",
        help=(
            "Add an optional AI REVIEW section. Requires OPENAI_API_KEY. "
            "The AI explains analyzer results but does not replace Joern."
        ),
    )
    parser.add_argument(
        "--ai-model",
        default=None,
        help="OpenAI model for --ai-review. Defaults to OPENAI_MODEL or gpt-5.",
    )
    return parser


def main():
    load_environment()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")

    args = _build_parser().parse_args()
    path = Path(args.path)

    analyzer = ProgramAnalyzer(
        dataset=path if path.is_dir() else path.parent,
        reports=args.reports,
        joern_path=args.joern,
        check_path=args.check_path,
        ai_review=args.ai_review,
        ai_model=args.ai_model,
    )

    if path.is_file():
        analyzer.analyze_file(path)
    else:
        analyzer.run()


if __name__ == "__main__":
    main()
