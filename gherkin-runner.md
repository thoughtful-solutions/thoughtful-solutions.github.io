# Gherkin Shell Script Test Runner

## Overview

The `gherkin_runner.py` script executes Gherkin feature files (`.gherkin`) by mapping test steps to shell script implementations. This enables human-readable test specifications backed by powerful shell commands for Enterprise Architecture validation, compliance checking, and system verification.

## How It Works

1. **Parse**: Reads `.gherkin` feature files containing scenarios and steps
2. **Match**: Uses regex patterns to find matching shell script implementations  
3. **Execute**: Runs shell scripts with automatic variable extraction and step chaining
4. **Report**: Provides human-readable or JSON output for automation

## Gherkin Language Structure

### Keywords and Their Purpose

| Keyword | Purpose | Example |
|---------|---------|---------|
| **Feature** | Describes the overall capability being tested | `Feature: API Authentication` |
| **Scenario** | A specific test case within the feature | `Scenario: Valid login succeeds` |
| **Given** | Sets up initial conditions/context | `Given I have valid credentials` |
| **When** | Describes the action being performed | `When I submit a login request` |
| **Then** | Defines the expected outcome | `Then I should receive an access token` |
| **And** | Continues the previous step type (Given/When/Then) | `And the token should be valid for 1 hour` |

### Basic Structure
```gherkin
Feature: Brief description of what's being tested
  Optional longer description explaining business value
  
  Scenario: Specific test case name
    Given some initial condition
    When an action is performed  
    Then an expected result occurs
    And additional validation
```

## Variable System

### MATCH_# Variables
Regular expression capture groups `()` automatically become environment variables:

```gherkin
# Step: "Then I should have 5 files in /tmp directory"
# Pattern: "Then I should have (\d+) files in (.+) directory"
IMPLEMENTS Then I should have (\d+) files in (.+) directory
    count=$MATCH_1      # Contains "5"
    directory=$MATCH_2  # Contains "/tmp"
    
    actual_count=$(find "$directory" -type f | wc -l)
    if [ "$actual_count" -eq "$count" ]; then
        echo "Found exactly $count files"
        exit 0
    else
        echo "Expected $count files, found $actual_count"
        exit 1
    fi
```

### PREVIOUS_STEP_STDOUT Variable
Each step receives the stdout output from the previous successful step:

```gherkin
IMPLEMENTS When I count files in directory "(.+)"
    find "$MATCH_1" -type f | wc -l    # Outputs count to stdout

IMPLEMENTS Then the count should be greater than (\d+)
    actual=$PREVIOUS_STEP_STDOUT       # Gets count from previous step
    expected=$MATCH_1
    
    if [ "$actual" -gt "$expected" ]; then
        echo "✓ Found $actual files (> $expected)"
        exit 0
    else
        echo "✗ Only $actual files (≤ $expected)"  
        exit 1
    fi
```

**Why Use PREVIOUS_STEP_STDOUT Instead of Files:**
- **Cleaner**: No temporary file cleanup required
- **Safer**: No file permission or collision issues
- **Portable**: Works identically across all platforms
- **Atomic**: Data transfer happens automatically between steps
- **Debuggable**: Output visible in logs and debug mode

## Installation and Setup

```bash
# Install dependencies
pip install gherkin-official

# Basic usage
python gherkin_runner.py feature.gherkin

# With debug output
python gherkin_runner.py feature.gherkin --debug

# JSON output for automation
python gherkin_runner.py feature.gherkin --json
```

## Complete Working Example

### Feature File: simple_demo.gherkin
```gherkin
Feature: Variable Demonstration
  Scenario: Show MATCH and PREVIOUS_STEP_STDOUT usage
    Given I have 3 test files in directory "/tmp/demo"
    When I count the actual files
    Then the counts should match
    And I should see a success message
```

### Implementation File: demo_steps.gherkin
```gherkin
IMPLEMENTS Given I have (\d+) test files in directory "(.+)"
    count=$MATCH_1
    directory=$MATCH_2
    
    # Create directory and files
    mkdir -p "$directory"
    for i in $(seq 1 $count); do
        echo "test data $i" > "$directory/file_$i.txt"
    done
    
    echo "Created $count files in $directory"

IMPLEMENTS When I count the actual files
    # Use the directory from previous step's output
    directory=$(echo "$PREVIOUS_STEP_STDOUT" | awk '{print $NF}')
    
    # Count and output the number
    find "$directory" -name "*.txt" -type f | wc -l

IMPLEMENTS Then the counts should match
    actual_count=$PREVIOUS_STEP_STDOUT
    expected_count=3  # We know we created 3 files
    
    if [ "$actual_count" -eq "$expected_count" ]; then
        echo "✓ Counts match: $actual_count"
        exit 0
    else
        echo "✗ Expected $expected_count, got $actual_count"
        exit 1
    fi

IMPLEMENTS And I should see a success message
    previous_result=$PREVIOUS_STEP_STDOUT
    
    if echo "$previous_result" | grep -q "✓"; then
        echo "SUCCESS: Test completed with positive result"
        exit 0
    else
        echo "FAILED: No success indicator found"
        exit 1
    fi
```

### Running the Example
```bash
python gherkin_runner.py simple_demo.gherkin
```

**Output:**
```
--- Gherkin Test Runner ---
Feature: Variable Demonstration

  Scenario: Show MATCH and PREVIOUS_STEP_STDOUT usage
    ✓ Given I have 3 test files in directory "/tmp/demo"
    ✓ When I count the actual files  
    ✓ Then the counts should match
    ✓ And I should see a success message

--------------------------------------------------
Run Summary:
  Scenarios: 1 total, 1 passed, 0 failed
  Steps:     4 total, 4 passed, 0 failed, 0 skipped, 0 undefined
--------------------------------------------------
```

## Enterprise Architecture Example

This example demonstrates validating architectural principles using the provided files.

### V-001-simplicity-principle-is-verified-by-a-low-rule-count.gherkin
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

### architecture_steps.gherkin
```gherkin
IMPLEMENTS Given I have access to the architecture repository
    if [ -d "../rules" ]; then
        echo "Found architecture repository at ../rules"
        exit 0
    else
        echo "Error: Architecture repository not found at ../rules"
        exit 1
    fi

IMPLEMENTS When I count the number of files in the '(.+)' directory
    directory=$MATCH_1
    find "../$directory" -type f -name "AR-*.md" | wc -l

IMPLEMENTS Then the total number should be less than (\d+)
    actual_count=$PREVIOUS_STEP_STDOUT
    expected_max=$MATCH_1
    
    # Remove whitespace for clean comparison
    actual_count=$(echo "$actual_count" | tr -d ' \n\r')
    
    if [ "$actual_count" -lt "$expected_max" ]; then
        echo "Check passed: $actual_count is less than $expected_max."
        exit 0
    else
        echo "Check failed: $actual_count is not less than $expected_max."
        exit 1
    fi
```

## Command Reference

| Flag | Purpose |
|------|---------|
| `--impl-dir <path>` | Implementation files directory (default: `../gherkin-implements`) |
| `--json` | Machine-readable JSON output for CI/CD |
| `--debug` | Show variable values and script execution details |

### JSON Output for Automation
```bash
python gherkin_runner.py test.gherkin --json | jq '.summary.scenarios.failed'
```

## Best Practices

### ✅ DO: Use stdout for step chaining
```gherkin
IMPLEMENTS When I get user count
    curl -s api/users | jq '. | length'    # Output to stdout

IMPLEMENTS Then count should be (\d+)
    actual=$PREVIOUS_STEP_STDOUT           # Use previous output
    expected=$MATCH_1
    test "$actual" -eq "$expected"
```

### ❌ AVOID: Temporary files
```gherkin
IMPLEMENTS When I get user count
    curl -s api/users | jq '. | length' > ./tmp/count    # File-based

IMPLEMENTS Then count should be (\d+)
    actual=$(cat ./tmp/count)                            # Fragile
    rm ./tmp/count                                       # Manual cleanup
```

### Error Handling
```gherkin
IMPLEMENTS When I check service "(.+)"
    service=$MATCH_1
    
    if ! curl -f "http://localhost/$service/health" 2>/dev/null; then
        echo "Service $service is not responding"
        exit 1
    fi
    
    echo "Service $service is healthy"
```

This runner is particularly powerful for Enterprise Architecture compliance testing, where you need to validate principles, count resources, check configurations, and verify architectural decisions are being followed consistently across your organization.