# Gherkin Shell Script Test Runner

## Overview

The `gherkin_runner.py` script is a Behavior-Driven Development (BDD) test runner. It is designed to execute feature files written in the Gherkin language (`.gherkin` files) by mapping the test steps to shell script implementations. This unique approach allows for human-readable test specifications while using powerful shell commands for the actual test logic.

The runner is written in Python and is designed to be cross-platform, working on both Linux and Windows (with a compatible shell environment like Git Bash).

## How It Works

### Parsing Feature Files
The script starts by parsing a user-provided `.gherkin` file to understand its structure, including Features, Scenarios, and Steps (Given, When, Then).

### Discovering Implementations
It then searches for step implementations. By default, it looks in the `../gherkin-implements` directory for any `.gherkin` files containing special `IMPLEMENTS` blocks that define the shell scripts for Gherkin steps.

### Matching Steps to Scripts
For each step in a scenario, the runner uses regular expressions to find a matching `IMPLEMENTS` pattern. It can capture arguments from the step text (e.g., filenames, user names) and pass them to the script as variables like `$MATCH_1`.

### Executing Shell Scripts
Once a match is found, the runner executes the associated shell script.

- A step **passes** if the script exits with a `0` status code
- A step **fails** if it exits with any non-zero status code. stdout and stderr are printed for debugging
- If a step fails, all subsequent steps in that scenario are skipped
- If no matching implementation is found for a step, it is marked as **undefined**

### Reporting
After running all scenarios, a summary is printed to the console. This can be either a human-readable, color-coded summary or a machine-readable JSON object for automation purposes.

## Setup and Prerequisites

### Python
Python 3.6 or newer must be installed.

### Dependencies
The script requires the `gherkin-official` Python library. You can install it using pip:

```bash
pip install gherkin-official
```

### Shell Environment

**Linux / macOS:** A standard Bash shell is typically available by default.

**Windows:** A Unix-like shell environment is required. Git Bash, which comes with Git for Windows, is the recommended tool. Ensure its bin directory is added to your system's PATH.

## Command-Line Usage

The script is invoked from the command line with the following syntax:

```bash
python gherkin_runner.py <feature_file> [--impl-dir <dir>] [--json] [implementation_files...]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `feature_file` | **(Required)** The path to the `.gherkin` feature file you want to execute |
| `--impl-dir <dir>` | Specifies the directory to search for implementation files. Defaults to `../gherkin-implements` |
| `--json` | When present, suppresses the standard colorized output and prints a machine-readable JSON object of the results to the standard output |
| `implementation_files` | A space-separated list of specific implementation files to use. If provided, this overrides the automatic search in the `--impl-dir` |

## Testing and Examples

### 1. Project Setup

First, create the following directory and file structure to test the examples. This example assumes you have a `rules` directory located one level above your test execution directory.

```
test-project/
├── gherkin-features/
│   └── simplicity_test.gherkin
│
├── gherkin-implements/
│   └── architecture_steps.gherkin
│
├── rules/
│   ├── AR-001-reproducible.md
│   ├── AR-002-modular.md
│   └── ... (and other rules)
│
└── gherkin_runner.py
```

- Copy the `gherkin_runner.py` script into the `test-project` directory
- Create your `rules` directory as shown, or ensure it exists at the correct relative path

### 2. Example Feature File

Create a file named `simplicity_test.gherkin` inside `gherkin-features`.

**gherkin-features/simplicity_test.gherkin:**

```gherkin
Feature: Verification for Simplicity Principle (AP-001)
  As an Enterprise Architect
  I want to ensure the number of architectural rules is minimal
  So that the architecture remains simple and easy to understand.

  Scenario: Count the number of active architectural rules
    Given I have access to the architecture repository
    When I count the number of files in the 'rules' directory
    Then the total number should be less than 10
```

### 3. Example Implementation File

Create `architecture_steps.gherkin` inside `gherkin-implements`. These shell scripts will now check for a real directory and count the specific rule files within it.

**gherkin-implements/architecture_steps.gherkin:**

```gherkin
IMPLEMENTS Given I have access to the architecture repository
    # Check if the rules directory exists at the expected relative path.
    # The '..' assumes the test is run from a directory like 'gherkin-features'.
    if [ -d "../rules" ]; then
        echo "Found architecture repository at ../rules"
        exit 0
    else
        echo "Error: Architecture repository not found at ../rules"
        exit 1
    fi

IMPLEMENTS When I count the number of files in the 'rules' directory
    # Count only the markdown rule files (AR-*.md) in the specified directory.
    # This ignores other files like spec.yaml.
    # The count is saved to a temporary file for the next step.
    find ../rules -type f -name "AR-*.md" | wc -l > file_count.tmp

IMPLEMENTS Then the total number should be less than (\d+)
    # Read the count from the previous step and the max number from the Gherkin step
    actual_count=$(cat file_count.tmp)
    expected_max=$MATCH_1

    # Perform the check. Exit with 0 for success, 1 for failure.
    if [ "$actual_count" -lt "$expected_max" ]; then
        echo "Check passed: $actual_count is less than $expected_max."
        exit 0
    else
        echo "Check failed: $actual_count is not less than $expected_max."
        exit 1
    fi
```

### 4. Running the Tests

Navigate to the `gherkin-features` directory to run the commands.

#### Standard Human-Readable Output

This is the default mode, ideal for viewing results directly in the terminal.

**Command (Linux or Windows/Git Bash):**

```bash
cd test-project/gherkin-features/
python ../gherkin_runner.py simplicity_test.gherkin
```

**Expected Output:**

```
--- Gherkin Test Runner ---
Searching for implementation files in: /path/to/test-project/gherkin-implements
...
Feature: Verification for Simplicity Principle (AP-001)

  Scenario: Count the number of active architectural rules
    ✔ Given I have access to the architecture repository
    ✔ When I count the number of files in the 'rules' directory
    ✔ Then the total number should be less than 10
...
--------------------------------------------------
Run Summary:
  Scenarios: 1 total, 1 passed, 0 failed
  Steps:     3 total, 3 passed, 0 failed, 0 skipped, 0 undefined
--------------------------------------------------
```

#### Machine-Readable JSON Output

Using the `--json` flag is perfect for CI/CD pipelines or when you need to process the results with another tool.

**Command:**

```bash
python ../gherkin_runner.py simplicity_test.gherkin --json
```

**Result (Piped to stdout):**

```json
{
  "feature": {
    "name": "Verification for Simplicity Principle (AP-001)",
    "file": "simplicity_test.gherkin"
  },
  "summary": {
    "scenarios": {
      "total": 1,
      "passed": 1,
      "failed": 0
    },
    "steps": {
      "total": 3,
      "passed": 3,
      "failed": 0,
      "skipped": 0,
      "undefined": 0
    }
  },
  "scenarios": [
    {
      "name": "Count the number of active architectural rules",
      "status": "passed",
      "steps": [
        {
          "keyword": "Given",
          "text": "I have access to the architecture repository",
          "status": "passed",
          "output": null
        },
        {
          "keyword": "When",
          "text": "I count the number of files in the 'rules' directory",
          "status": "passed",
          "output": null
        },
        {
          "keyword": "Then",
          "text": "the total number should be less than 10",
          "status": "passed",
          "output": null
        }
      ]
    }
  ]
}
```

## Advanced Example: Processing JSON with jq

The JSON output becomes powerful when combined with command-line JSON processors like `jq`. This allows you to easily query and transform the results for reporting or analysis.

### Example 1: Get the names of all failed scenarios

```bash
# This command pipes the JSON output to jq
python ../gherkin_runner.py simplicity_test.gherkin --json | jq '.scenarios[] | select(.status=="failed") | .name'
```

**Output:**
```
(No output, as the test passed)
```

### Example 2: Create a simple summary report

```bash
python ../gherkin_runner.py simplicity_test.gherkin --json | jq '"Total Scenarios: \(.summary.scenarios.total), Passed: \(.summary.scenarios.passed), Failed: \(.summary.scenarios.failed)"'
```

**Output:**
```
"Total Scenarios: 1, Passed: 1, Failed: 0"
```