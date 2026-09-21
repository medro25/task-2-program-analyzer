# Simple Python Program Analyzer

Writer: Errafay Amine

This project is a small static program analyzer for Python code. It uses
[Joern](https://joern.io/) to inspect Python source files and produce readable
text reports.

The analyzer does not run the Python programs. It reads the source code, builds
analysis data with Joern, and reports:

- the functions defined in the program
- where each defined function is called
- the call location as a tuple: `<class, method, statement>`
- optional path information for obvious unreachable calls
- optional AI review for explaining the result and visible bug or security risks

## Project Description

The main goal is to answer Task 2 for the Python option:

> Given a Python program, find the complete list of functions defined in the
> program, and for each function, list the locations where that function is
> called.

This project chooses the Joern option because Joern supports multiple languages,
including Python. Joern parses the source code and builds a code property graph
(CPG). The project runs a Joern query over that graph, extracts function and call
information, then converts it into a simple report.

The workflow is:

1. `analyzer.py` receives a Python file or a dataset folder.
2. `joern.py` runs Joern on each Python file.
3. Joern finds user-defined functions and calls to those functions.
4. `joern.py` parses the Joern output into Python dictionaries.
5. Optional features add path-checking and AI review sections.
6. `reporter.py` writes a text report into `reports/`.

## Task 2 Requirements

Task 2 asks for a simple program analyzer. The Python version of the task asks
for:

1. a complete list of functions defined in a Python program
2. for each function, a list of call locations
3. each call location written as `<class, method, statement>`
4. code and README documentation explaining the implementation

This project addresses those requirements as follows:

- `joern.py` uses Joern to analyze Python source code statically.
- The Joern query collects user-defined functions from the program.
- For every defined function, the query finds calls whose name matches that
  function.
- `_parse()` in `joern.py` converts Joern output into the report data format.
- `reporter.py` writes the required function list and call-location tuples.
- `README.md` explains the implementation, setup, commands, reports, and
  limitations.

A normal report includes:

```text
DEFINED FUNCTIONS
------------------------------------------------------------
Account.__init__
Account.deposit
Account.withdraw
Account.__str__
main

FUNCTION CALL LOCATIONS
============================================================
Function: Account.deposit
  <GLOBAL, main, my_account.deposit(amount)>
```

The tuple means:

- `class`: the class where the call appears, or `GLOBAL` if it is not inside a class
- `method`: the function or method where the call appears, or `GLOBAL` if it is top-level code
- `statement`: the source statement containing the call

## Project Structure

```text
analyzer.py          Main workflow and command-line interface
joern.py             Runs Joern and parses Joern output
reporter.py          Builds and saves text reports
path_checker.py      Optional CHECK PATH analysis
ai_reviewer.py       Optional OpenAI-based report review
env_config.py        Loads .env values for local runs
requirements.txt     Python package dependencies
Dockerfile           Docker image with Python, Joern, and dependencies
compose.yaml         Docker Compose service definition
joern-install.sh     Helper script used to install Joern
dataset/             Python files used for analysis
reports/             Generated report files
tests/               Unit tests
.gitignore           Keeps generated files and secrets out of git
.dockerignore        Keeps secrets and generated files out of Docker builds
```

The `dataset/` folder is flat. Python files are stored directly inside it. It
contains example Python programs and selected OWASP Benchmark Python files. See
`dataset/SOURCE.md` for the source repositories and license notes.

`dataset/test.py` is the main reference file used in this README. It contains
classes, methods, repeated method names, normal calls, and visible security-risk
patterns, so it is useful for checking the analyzer output.

## How to Run Locally

### Prerequisites

You need:

- Python 3
- `pip`
- `curl` and `unzip` if you want to install Joern using `joern-install.sh`
- Joern installed locally

### Install Python Dependencies

Run these commands from the project root folder. The project root is the folder
that contains `analyzer.py`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The only Python dependency currently needed is:

```text
python-dotenv
```

The other imports, such as `argparse`, `logging`, `ast`, `json`, `pathlib`, and
`subprocess`, are part of the Python standard library.

### Install or Configure Joern

For local runs, the analyzer expects Joern at:

```text
~/bin/joern/joern-cli/joern
```

You can install Joern into that default location with:

```bash
./joern-install.sh
```

If Joern is installed somewhere else, pass its path with `--joern`:

```bash
python analyzer.py dataset/test.py --joern /path/to/joern
```

You can also set `JOERN_PATH` in your shell, but this is optional. Docker sets
the Joern path automatically, so `JOERN_PATH` is not needed when using Docker.

### Recommended Local Order

Use this order when running the project locally:

1. Install the Python dependencies.
2. Install or configure Joern.
3. Run the unit tests.
4. Run the analyzer.
5. Open the generated report in `reports/`.

Run the tests first:

```bash
python -m unittest discover -s tests
```

Then run the analyzer. For example:

```bash
python analyzer.py dataset/test.py --check-path --ai-review
```

### Report Location

Reports are written to:

```text
reports/
```

Use `--reports` to choose another output folder:

```bash
python analyzer.py dataset/test.py --reports my_reports
```

### Common Local Run Commands

Run the unit tests before using one of these analyzer commands:

```bash
python -m unittest discover -s tests
```

Analyze the whole dataset:

```bash
python analyzer.py
```

Analyze one Python file:

```bash
python analyzer.py dataset/test.py
```

Analyze one file with CHECK PATH:

```bash
python analyzer.py dataset/test.py --check-path
```

Analyze one file with AI Review:

```bash
python analyzer.py dataset/test.py --ai-review
```

Analyze one file with CHECK PATH and AI Review:

```bash
python analyzer.py dataset/test.py --check-path --ai-review
```

Analyze the whole dataset with CHECK PATH:

```bash
python analyzer.py dataset --check-path
```

Analyze the whole dataset with CHECK PATH and AI Review:

```bash
python analyzer.py dataset --check-path --ai-review
```

## How to Run with Docker

Docker is the easiest way to run the project because Joern is installed inside
the Docker image.

You need:

- Docker Desktop or another Docker engine
- Docker Compose

Check Docker:

```bash
docker --version
docker compose version
```

Docker Compose reads `.env` because `compose.yaml` includes it. For non-AI
runs, the file can be empty. For AI review, it must contain your OpenAI API key.

```bash
touch .env
```

### Build the Docker Image

Run this from the project root folder:

```bash
docker compose build
```

This step builds the image and runs the unit tests inside Docker. If the build
passes, then run the analyzer commands.

The Docker image installs:

- Java runtime
- Python
- Python dependencies from `requirements.txt`
- Joern

### Run with Docker Compose

Recommended Docker order:

1. Build the image.
2. Let the Docker build run the unit tests.
3. Run the analyzer command.
4. Check the generated report in `reports/`.

Analyze the whole dataset:

```bash
docker compose run --rm analyzer
```

Analyze one file:

```bash
docker compose run --rm analyzer dataset/test.py
```

The `--rm` option removes the temporary container after the run finishes. Docker
may show a new container name each time. That is normal. The image is reused;
only the temporary runtime container is new.

### Docker Volumes

`compose.yaml` mounts:

```text
./dataset  -> /app/dataset   read-only
./reports  -> /app/reports   writable
```

This means:

- the container reads your local `dataset/` files
- the container writes reports back to your local `reports/` folder
- reports remain on your Mac after the container exits

### Plain Docker Commands

Build the image:

```bash
docker build -t task2-analyzer .
```

Run the default dataset:

```bash
docker run --rm \
  -v "$PWD/dataset:/app/dataset:ro" \
  -v "$PWD/reports:/app/reports" \
  task2-analyzer
```

Run one file:

```bash
docker run --rm \
  -v "$PWD/dataset:/app/dataset:ro" \
  -v "$PWD/reports:/app/reports" \
  task2-analyzer dataset/test.py
```

## Extra Feature: CHECK PATH

`--check-path` adds a `CHECK PATH ANALYSIS` section to the report.

It checks whether reported call locations are obviously reachable or
unreachable. For example, a call after a `return` statement in the same block is
marked unreachable.

Run locally:

```bash
python analyzer.py dataset/test.py --check-path
```

Run with Docker Compose:

```bash
docker compose run --rm analyzer dataset/test.py --check-path
```

### CHECK PATH Status Values

`REACHABLE` means the checker did not find an earlier terminating statement that
blocks the call in the same block.

`UNREACHABLE` means the checker found an obvious reason the call cannot execute,
such as appearing after `return`, `raise`, `break`, or `continue`.

`UNKNOWN` means the analyzer did not have a usable source line for the call.

## Extra Feature: AI Review

`--ai-review` adds an `AI REVIEW` section to the report.

The AI review explains the static-analysis result in plain English. It does not
replace Joern. Joern still produces the core facts: functions and call
locations.

Run locally:

```bash
python analyzer.py dataset/test.py --ai-review
```

Run with Docker Compose:

```bash
docker compose run --rm analyzer dataset/test.py --ai-review
```

### What Is Sent to the AI

When `--ai-review` is enabled, the project sends:

- the analyzed file name
- the function and call-location result
- the optional CHECK PATH result if it exists
- a source excerpt from the analyzed file

The source excerpt is limited in `ai_reviewer.py` so the request stays small.

### Vulnerability and Bug Risk Review

The AI is asked to produce a short vulnerability and bug risk table. It uses
labels instead of numeric probabilities:

```text
HIGH
MEDIUM
LOW
NOT EVIDENT
UNKNOWN
```

The requested categories include:

- SQL injection
- XSS
- path traversal or file access
- command injection
- SSRF or network access
- insecure deserialization
- hardcoded secrets
- authentication or authorization weakness
- weak cryptography
- input validation bugs
- error handling bugs
- dead code or unreachable code
- resource leaks
- other visible bug risks

The AI is instructed not to invent vulnerabilities. If the source excerpt does
not show evidence for a category, the review should say `NOT EVIDENT` or
`UNKNOWN`.

## AI API Configuration

AI review requires an OpenAI API key.

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5
```

Do not put a real API key in the README. Do not commit `.env` to git.

This project already ignores `.env` in:

```text
.gitignore
.dockerignore
```

`OPENAI_API_KEY` is required only when using `--ai-review`.

`OPENAI_MODEL` is optional. If it is not set, the project uses `gpt-5`.

You can create an API key here:

[OpenAI API keys](https://platform.openai.com/api-keys)

## Running All Cases

All commands below should be run from the project root folder. That is the
folder that contains `analyzer.py`, `Dockerfile`, and `compose.yaml`.

The recommended order is:

1. Run the unit tests.
2. Run the analyzer mode you want.
3. Check the generated report in `reports/`.

### Local Commands

Step 1: run the tests.

```bash
python -m unittest discover -s tests
```

Step 2: choose one analyzer command.

Normal analysis of the whole dataset:

```bash
python analyzer.py
```

Normal analysis of one file:

```bash
python analyzer.py dataset/test.py
```

CHECK PATH only:

```bash
python analyzer.py dataset/test.py --check-path
```

AI Review only:

```bash
python analyzer.py dataset/test.py --ai-review
```

CHECK PATH plus AI Review:

```bash
python analyzer.py dataset/test.py --check-path --ai-review
```

Analyze the whole dataset with CHECK PATH:

```bash
python analyzer.py dataset --check-path
```

Analyze the whole dataset with CHECK PATH and AI Review:

```bash
python analyzer.py dataset --check-path --ai-review
```

### Docker Compose Commands

Step 1: build the Docker image. This also runs the unit tests.

```bash
docker compose build
```

Step 2: choose one analyzer command.

Normal analysis of the whole dataset:

```bash
docker compose run --rm analyzer
```

Normal analysis of one file:

```bash
docker compose run --rm analyzer dataset/test.py
```

CHECK PATH only:

```bash
docker compose run --rm analyzer dataset/test.py --check-path
```

AI Review only:

```bash
docker compose run --rm analyzer dataset/test.py --ai-review
```

CHECK PATH plus AI Review:

```bash
docker compose run --rm analyzer dataset/test.py --check-path --ai-review
```

Analyze the whole dataset with CHECK PATH:

```bash
docker compose run --rm analyzer dataset --check-path
```

Analyze the whole dataset with CHECK PATH and AI Review:

```bash
docker compose run --rm analyzer dataset --check-path --ai-review
```

### Plain Docker Commands

Normal analysis:

```bash
docker run --rm \
  -v "$PWD/dataset:/app/dataset:ro" \
  -v "$PWD/reports:/app/reports" \
  task2-analyzer
```

CHECK PATH plus AI Review:

```bash
docker run --rm \
  --env-file .env \
  -v "$PWD/dataset:/app/dataset:ro" \
  -v "$PWD/reports:/app/reports" \
  task2-analyzer dataset/test.py --check-path --ai-review
```

## Testing

Run the unit tests before running the analyzer, before submitting the project,
and before pushing new code changes.

Local test command:

```bash
python -m unittest discover -s tests
```

The tests cover:

- Joern path configuration
- parsing Joern output
- source statement extraction
- nested function context labels
- duplicate method-name cleanup
- report generation
- report filename tags
- CHECK PATH unreachable-call detection
- AI review behavior when the API key is missing
- AI review timeout retry behavior
- the AI prompt risk categories

The Docker image also runs the unit tests during the build:

```bash
docker compose build
```

## Reports

Reports are plain text files saved in `reports/`.

A report has these main sections:

```text
SIMPLE PYTHON PROGRAM ANALYZER
DEFINED FUNCTIONS
FUNCTION CALL LOCATIONS
CHECK PATH ANALYSIS      only when --check-path is enabled
AI REVIEW                only when --ai-review is enabled
SUMMARY
```

Report filenames show which optional features were enabled:

```text
sample_analysis.txt
sample_path_analysis.txt
sample_ai_analysis.txt
sample_path_ai_analysis.txt
```

Examples:

- `test_analysis.txt` is a normal report.
- `test_path_analysis.txt` includes CHECK PATH.
- `test_ai_analysis.txt` includes AI Review.
- `test_path_ai_analysis.txt` includes both extra sections.

`reports/` is ignored by git because reports are generated output.

## Future Improvements

Good next improvements would be:

- improve CHECK PATH into a deeper control-flow analysis
- model more complex branches, loops, exceptions, and nested paths
- improve the report writer with more formats, such as JSON or HTML
- add more tests for difficult Python call patterns

## Notes

This is a simple static analyzer built for the assignment. It is useful for
showing function definitions, function-call locations, and basic call
reachability information.

It does not execute the analyzed code. It does not guarantee that every dynamic
Python behavior is resolved. Calls made through reflection, monkey patching,
dynamic imports, generated code, or complex aliasing may not be fully captured.

The AI review is only an explanation layer. The required Task 2 result comes
from Joern and the project code, not from the AI.
