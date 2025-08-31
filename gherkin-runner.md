# Gherkin Shell Script Test Runner

## Overview

The ```gherkin_runner.py``` script is a **Behavior-Driven Development (BDD)** test runner. 

It is designed to execute feature files written in the Gherkin language (```.gherkin``` files) by mapping the test steps to shell script implementations. This unique approach allows for human-readable test specifications while using powerful shell commands for the actual test logic.

The runner is written in Python and is designed to be cross-platform, working on both Linux and Windows (with a compatible shell environment like Git Bash).

## How It Works

* **Parsing Feature Files:** The script starts by parsing a user-provided ```.gherkin``` file to understand its structure, including Features, Scenarios, and Steps (Given, When, Then).
  
* **Discovering Implementations:** It then searches for step implementations. By default, it looks in the ```../gherkin-implements``` directory for any ```.gherkin``` files containing special **IMPLEMENTS** blocks that define the shell scripts for Gherkin steps.
  
* **Matching Steps to Scripts:** For each step in a scenario, the runner uses regular expressions to find a matching IMPLEMENTS pattern. It can capture arguments from the step text (e.g., filenames, user names) and pass them to the script as variables like ```$MATCH_1```.
  
* **Executing Shell Scripts:** Once a match is found, the runner executes the associated shell script.
  
  * A step **passes** if the script exits with a ```0``` status code.
  
  * A step **fails** if it exits with any non-zero status code. `stdout` and `stderr` are printed for debugging.
  
  * If a step fails, all subsequent steps in that scenario are **skipped**.

  * If no matching implementation is found for a step, it is marked as **undefined**.

*  **Reporting:** After running all scenarios, a summary is printed to the console. This can be either a human-readable, color-coded summary or a machine-readable JSON object for automation purposes.

## Setup and Prerequisites

* Python: Python 3.6 or newer must be installed

* Dependencies: The script requires the `gherkin-official` Python library. You can install it using `pip`:
  
```
 pip install gherkin-official
```

 * Shell Environment:
   * Linux / macOS: A standard Bash shell is typically available by default.
   * Windows: A Unix-like shell environment is required. Git Bash, which comes with Git for Windows, is the recommended tool. Ensure its bin directory is added to your system's PATH.

## Command-Line Usage
The script is invoked from the command line with the following syntax:
```
python gherkin\_runner.py <feature\_file> \[--impl-dir <dir>] \[--json] \[implementation\_files...]
```

### Arguments:

| Argument | Description |
|----------|-------------|
| `feature_file` | (Required) The path to the `.gherkin` feature file you want to execute. |
| `--impl-dir <dir>` | Specifies the directory to search for implementation files. Defaults to `../gherkin-implements`. |
| `--json` | When present, suppresses the standard colorized output and prints a machine-readable JSON object of the results to the standard output. |
| `implementation_files` | A space-separated list of specific implementation files to use. If provided, this overrides the automatic search in the `--impl-dir`. |


## Testing and Examples

### Project Setup

First, create the following directory and file structure to test the examples:

```
test-project/
├── gherkin-features/
│   └── login_test.gherkin
│
├── gherkin-implements/
│   └── auth_steps.gherkin
│
└── gherkin_runner.py
```

• Copy the `gherkin_runner.py` script into the `test-project` directory.

###  Example Feature File

Create a file named `login_test.gherkin` inside `gherkin-features`. This scenario will include a failing step to demonstrate the output.

`gherkin-features/login_test.gherkin`:

```gherkin
Feature: User Authentication
  As a site administrator
  I want to check user login functionality

  Scenario: A valid user can log in
    Given a user 'admin' exists
    When the user 'admin' logs in with a correct password
    Then the login should be successful

  Scenario: An invalid user is rejected
    Given a user 'guest' does not exist
    When the user 'guest' attempts to log in
    Then the login should fail with message 'Invalid credentials'
```

### Example Implementation File

Create `auth_steps.gherkin` inside `gherkin-implements`.

`gherkin-implements/auth_steps.gherkin`:

```bash
IMPLEMENTS Given a user '(\S+)' exists
  echo "User '$MATCH_1' is configured."

IMPLEMENTS Given a user '(\S+)' does not exist
  echo "Verified that user '$MATCH_1' does not exist."

IMPLEMENTS When the user '(\S+)' logs in with a correct password
  echo "Simulating successful login for '$MATCH_1'."
  exit 0

IMPLEMENTS When the user '(\S+)' attempts to log in
  echo "Simulating failed login for '$MATCH_1'."
  exit 0

IMPLEMENTS Then the login should be successful
  echo "Success!"
  exit 0

IMPLEMENTS Then the login should fail with message '(.+)'
  echo "Checking for failure message..."
  echo "Error: Actual message was 'Access denied'"
  # This script will fail because the message doesn't match
  exit 1
```

### Running the Tests

Navigate to the `gherkin-features` directory to run the commands.

#### Standard Human-Readable Output

This is the default mode, ideal for viewing results directly in the terminal.

**Command (Linux or Windows/Git Bash):**

```bash
cd test-project/gherkin-features/
python ../gherkin_runner.py login_test.gherkin
```

**Expected Output:**

```
--- Gherkin Test Runner ---
Searching for implementation files in: /path/to/test-project/gherkin-implements
...
Feature: User Authentication

  Scenario: A valid user can log in
    ✓ Given a user 'admin' exists
    ✓ When the user 'admin' logs in with a correct password
    ✓ Then the login should be successful

  Scenario: An invalid user is rejected
    ✓ Given a user 'guest' does not exist
    ✓ When the user 'guest' attempts to log in
    ✗ Then the login should fail with message 'Invalid credentials'
      stderr: Checking for failure message...
      Error: Actual message was 'Access denied'
...
```

#### Machine-Readable JSON Output

Using the `--json` flag is perfect for CI/CD pipelines or when you need to process the results with another tool.

**Command:**

```bash
python ../gherkin_runner.py login_test.gherkin --json
```

**Result (Piped to stdout):**

```json
{
  "feature": {
    "name": "User Authentication",
    "file": "login_test.gherkin"
  },
  "summary": {
    "scenarios": { "total": 2, "passed": 1, "failed": 1 },
    "steps": { "total": 6, "passed": 5, "failed": 1, "skipped": 0, "undefined": 0 }
  },
  "scenarios": [
    {
      "name": "A valid user can log in",
      "status": "passed",
      "steps": [
        { "keyword": "Given", "text": "a user 'admin' exists", "status": "passed", "output": null },
        { "keyword": "When", "text": "the user 'admin' logs in with a correct password", "status": "passed", "output": null },
        { "keyword": "Then", "text": "the login should be successful", "status": "passed", "output": null }
      ]
    },
    {
      "name": "An invalid user is rejected",
      "status": "failed",
      "steps": [
        { "keyword": "Given", "text": "a user 'guest' does not exist", "status": "passed", "output": null },
        { "keyword": "When", "text": "the user 'guest' attempts to log in", "status": "passed", "output": null },
        {
          "keyword": "Then",
          "text": "the login should fail with message 'Invalid credentials'",
          "status": "failed",
          "output": {
            "stdout": "Checking for failure message...\\nError: Actual message was 'Access denied'",
            "stderr": ""
          }
        }
      ]
    }
  ]
}
```

### Advanced Example: Processing JSON with `jq`

The JSON output becomes powerful when combined with command-line JSON processors like `jq`. This allows you to easily query and transform the results for reporting or analysis.

#### Get the names of all failed scenarios

```bash
# This command pipes the JSON output to jq
python ../gherkin_runner.py login_test.gherkin --json | jq '.scenarios[] | select(.status=="failed") | .name'
```

**Output:**

```
"An invalid user is rejected"
```

### Create a simple summary report

```bash
python ../gherkin_runner.py login_test.gherkin --json | jq '"Total Scenarios: \(.summary.scenarios.total), Passed: \(.summary.scenarios.passed), Failed: \(.summary.scenarios.failed)"'
```

**Output:**

```
"Total Scenarios: 2, Passed: 1, Failed: 1"
```
