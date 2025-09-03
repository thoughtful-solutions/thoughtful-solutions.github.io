#!/usr/bin/env python3
"""
Gherkin Test Runner with Cross-Platform Support
Executes Gherkin feature files using shell script implementations.
Handles line ending issues and works on both Windows and Linux.
"""

import re
import os
import sys
import shutil
import subprocess
import json
import argparse
from pathlib import Path
from gherkin.parser import Parser

class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


def normalize_line_endings(text):
    """
    Normalize line endings to Unix format (LF only).
    This removes Windows CRLF issues that cause bash parsing errors.
    """
    if text is None:
        return ""
    # Replace CRLF with LF, then ensure no stray CR characters remain
    return text.replace('\r\n', '\n').replace('\r', '\n')


def clean_script_content(script_content):
    """
    Clean, prepare, and strip shebang from script content for execution.
    """
    if not script_content:
        return ""
    
    cleaned = normalize_line_endings(script_content)
    lines = cleaned.split('\n')

    # Strip shebang if present, as the runner calls bash explicitly
    if lines and lines[0].strip().startswith("#!"):
        lines.pop(0)
    
    # Remove trailing whitespace from each line while preserving structure
    cleaned_lines = [line.rstrip() for line in lines]
    
    return '\n'.join(cleaned_lines)


def print_colored(text, color='', end='\n', file=sys.stdout):
    """Print text with color if supported to the specified file stream."""
    # Check if we're in a terminal that supports colors for the given file stream
    if hasattr(file, 'isatty') and file.isatty():
        print(f"{color}{text}{Colors.RESET}", end=end, file=file)
    else:
        print(text, end=end, file=file)


def find_bash_executable():
    """
    Find a suitable bash executable, prioritizing native Windows shells (like Git Bash)
    over WSL to ensure consistent behavior and environment.
    """
    # On non-Windows systems, 'bash' in the PATH is almost always the right choice.
    if sys.platform != "win32":
        return 'bash'

    # --- On Windows, find a native bash, avoiding WSL ---

    # 1. Best Method: Find bash relative to git.exe in the PATH.
    # This works reliably with standard installers, Scoop, Chocolatey, etc.
    git_path = shutil.which('git')
    if git_path:
        # The bash.exe for Git is in the same directory as git.exe
        bash_path = os.path.join(os.path.dirname(git_path), 'bash.exe')
        if os.path.exists(bash_path):
            return bash_path

    # 2. Fallback: Check common hardcoded installation paths for Git Bash.
    possible_paths = [
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Git", "bin", "bash.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Git", "bin", "bash.exe"),
    ]
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        possible_paths.append(os.path.join(local_app_data, "Programs", "Git", "bin", "bash.exe"))

    for path in possible_paths:
        if os.path.exists(path):
            return path

    # 3. Last Resort: Check if 'bash' is in the PATH and verify it's not WSL.
    bash_in_path = shutil.which('bash')
    if bash_in_path:
        try:
            # `uname -o` identifies the OS. Git Bash (Msys) -> 'Msys', WSL -> 'GNU/Linux'.
            result = subprocess.run(
                [bash_in_path, '-c', 'uname -o'],
                capture_output=True, text=True, timeout=3, encoding='utf-8'
            )
            if result.returncode == 0 and 'linux' not in result.stdout.lower():
                return bash_in_path
        except (subprocess.TimeoutExpired, OSError):
            # Command failed or timed out, so we can't trust this bash.
            pass

    # 4. Failure: If we've reached this point, no suitable bash was found.
    print_colored("ERROR: A suitable non-WSL bash executable was not found.", Colors.RED, file=sys.stderr)
    print_colored("Please install Git for Windows (https://git-scm.com/downloads) and ensure its 'bin' directory is in your system's PATH.", Colors.YELLOW, file=sys.stderr)
    sys.exit(1)


def execute_shell_script(script_content, variables=None, context=None, debug=False, timeout=60):
    """
    Execute a shell script, passing variables via the environment for robustness.
    """
    if variables is None:
        variables = {}
    if context is None:
        context = {}

    cleaned_script = clean_script_content(script_content)

    if not cleaned_script.strip():
        return subprocess.CompletedProcess(
            args=['bash'], returncode=1, stdout='', stderr='Empty script content'
        )

    bash_executable = find_bash_executable()
    
    try:
        # Pass variables via the environment, which is robust and avoids quoting issues.
        script_env = os.environ.copy()
        all_vars = {**context, **variables}
        
        # Add all variables to the environment as strings
        for key, value in all_vars.items():
            script_env[key] = str(value)

        command = [bash_executable, '-c', cleaned_script]

        if debug:
            print("--- DEBUG: Variables passed to script (as environment) ---")
            print(json.dumps(all_vars, indent=2) if all_vars else "None")
            print(f"--- DEBUG: Using bash executable: {bash_executable} ---")
            print("--- DEBUG: Executing script ---")
            print(cleaned_script)
            print("------------------------------------------")

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            env=script_env  # Pass the constructed environment here
        )
            
        if debug:
            print(f"--- DEBUG: Result (Exit Code: {result.returncode}) ---")
            if result.stdout and result.stdout.strip():
                print(f"  stdout:\n{result.stdout}")
            if result.stderr and result.stderr.strip():
                print(f"  stderr:\n{result.stderr}")
            print("---------------------------------")
            
        return result
            
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=[bash_executable, '-c', '...'], 
            returncode=124, 
            stdout='', 
            stderr=f'Script execution timed out after {timeout} seconds'
        )
    except Exception as e:
        return subprocess.CompletedProcess(
            args=[bash_executable, '-c', '...'], 
            returncode=1, 
            stdout='', 
            stderr=f'Error executing script: {str(e)}'
        )


def load_implementation_file(file_path, debug=False):
    """
    Load implementation file with automatic line ending normalization.
    """
    implementations = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8', newline=None) as f:
            content = f.read()
        
        content = normalize_line_endings(content)
        
        if debug:
            print(f"Loading implementations from: {file_path}")
        
        implements_pattern = r'^IMPLEMENTS\s+(.+?)$'
        lines = content.split('\n')
        
        current_step = None
        current_script = []
        
        for line in lines:
            implements_match = re.match(implements_pattern, line.strip())
            
            if implements_match:
                if current_step and current_script:
                    script_content = '\n'.join(current_script)
                    implementations[current_step] = clean_script_content(script_content)
                
                current_step = implements_match.group(1).strip()
                current_script = []
            elif current_step is not None:
                current_script.append(line)
        
        if current_step and current_script:
            script_content = '\n'.join(current_script)
            implementations[current_step] = clean_script_content(script_content)
        
        if debug:
            print(f"Found {len(implementations)} implementations")
            for step_pattern in implementations.keys():
                print(f"  - {step_pattern}")
            
    except Exception as e:
        print(f"Error loading implementation file {file_path}: {str(e)}")
    
    return implementations


def find_implementation_files(impl_dir, debug=False):
    """
    Find all implementation files in the specified directory.
    """
    impl_dir = Path(impl_dir)
    if not impl_dir.exists():
        if debug:
            print(f"Implementation directory does not exist: {impl_dir}")
        return []
    
    gherkin_files = list(impl_dir.glob('*.gherkin'))
    
    if debug:
        print(f"Searching for implementation files in: {impl_dir.absolute()}")
        print(f"Found {len(gherkin_files)} implementation file(s)")
        for file in gherkin_files:
            print(f"  - {file.name}")
    
    return [str(f) for f in gherkin_files]


def load_all_implementations(impl_files, debug=False):
    """
    Load all implementation files and combine them into a single dictionary.
    """
    all_implementations = {}
    
    print(f"Loading implementations from {len(impl_files)} file(s)...")
    
    for impl_file in impl_files:
        implementations = load_implementation_file(impl_file, debug)
        
        for step_pattern, script in implementations.items():
            if step_pattern in all_implementations:
                print(f"{Colors.YELLOW}Warning: Duplicate implementation for step: {step_pattern}{Colors.RESET}")
            all_implementations[step_pattern] = script
    
    print(f"Found {len(all_implementations)} step implementations.")
    return all_implementations


def run_step(step_text, step_keyword, implementations, context=None, debug=False):
    """
    Run a single step by finding a matching implementation.
    """
    full_step_text = f"{step_keyword} {step_text}".strip()
    
    for pattern, script_content in implementations.items():
        try:
            # First, attempt to match against the raw step text (without keyword)
            match = re.match(f"^{pattern}$", step_text, re.IGNORECASE)
            
            # If no match, try matching against the full text (with keyword)
            if not match:
                match = re.match(f"^{pattern}$", full_step_text, re.IGNORECASE)

            if match:
                variables = {}
                for i, group in enumerate(match.groups(), 1):
                    variables[f'MATCH_{i}'] = group if group is not None else ""
                
                result = execute_shell_script(script_content, variables, context, debug)
                
                return {
                    'status': 'passed' if result.returncode == 0 else 'failed',
                    'output': result.stderr if result.returncode != 0 and result.stderr.strip() else None,
                    'stdout': result.stdout if result.stdout else None,
                    'stderr': result.stderr if result.stderr else None,
                    'exit_code': result.returncode
                }
                
        except re.error as e:
            if debug:
                print(f"Invalid regex pattern '{pattern}': {e}")
            continue
    
    return {'status': 'undefined', 'output': f'No implementation found for: {full_step_text}'}


def run_gherkin_file(feature_file, implementations, debug=False, json_output=False):
    """
    Run a Gherkin feature file using the provided implementations.
    """
    try:
        with open(feature_file, 'r', encoding='utf-8', newline=None) as f:
            feature_content = f.read()
        
        feature_content = normalize_line_endings(feature_content)
        
        parser = Parser()
        gherkin_document = parser.parse(feature_content)
        
        if not gherkin_document.get('feature'):
            raise Exception("No feature found in the file")
        
        feature = gherkin_document['feature']
        
        results = {
            'feature': {'name': feature['name'], 'file': feature_file},
            'scenarios': [],
            'summary': {
                'scenarios': {'total': 0, 'passed': 0, 'failed': 0},
                'steps': {'total': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'undefined': 0}
            }
        }
        
        if not json_output:
            print_colored(f"Feature: {feature['name']}", Colors.BOLD)
        
        for child in feature.get('children', []):
            if 'scenario' in child:
                scenario = child['scenario']
                scenario_result = {'name': scenario['name'], 'status': 'passed', 'steps': []}
                results['summary']['scenarios']['total'] += 1
                
                if not json_output:
                    print_colored(f"\n  Scenario: {scenario['name']}")
                
                scenario_failed = False
                scenario_context = {}

                for step in scenario.get('steps', []):
                    results['summary']['steps']['total'] += 1
                    step_keyword = step['keyword'].strip()
                    step_text = step['text']
                    
                    if scenario_failed:
                        step_result = {'keyword': step_keyword, 'text': step_text, 'status': 'skipped'}
                        results['summary']['steps']['skipped'] += 1
                        if not json_output:
                            print_colored(f"    - {step_keyword} {step_text}", Colors.YELLOW)
                    else:
                        step_result = run_step(step_text, step_keyword, implementations, scenario_context, debug)
                        step_result['keyword'] = step_keyword
                        step_result['text'] = step_text
                        
                        if step_result['status'] == 'passed':
                            results['summary']['steps']['passed'] += 1
                            if step_result.get('stdout') is not None:
                                scenario_context['PREVIOUS_STEP_STDOUT'] = step_result['stdout'].strip()
                            if not json_output:
                                print_colored(f"    ✓ {step_keyword} {step_text}", Colors.GREEN)
                        else:
                            scenario_failed = True
                            scenario_result['status'] = 'failed'
                            if step_result['status'] == 'failed':
                                results['summary']['steps']['failed'] += 1
                                if not json_output:
                                    print_colored(f"    ✖ {step_keyword} {step_text}", Colors.RED)
                                    if step_result.get('stderr'):
                                        print_colored(f"      Error: {step_result['stderr']}", Colors.RED, file=sys.stderr)
                            elif step_result['status'] == 'undefined':
                                results['summary']['steps']['undefined'] += 1
                                if not json_output:
                                    print_colored(f"    ? {step_keyword} {step_text}", Colors.MAGENTA)
                                    if step_result.get('output'):
                                        print_colored(f"      {step_result['output']}", Colors.MAGENTA, file=sys.stderr)
                    
                    scenario_result['steps'].append(step_result)
                
                if scenario_result['status'] == 'passed':
                    results['summary']['scenarios']['passed'] += 1
                else:
                    results['summary']['scenarios']['failed'] += 1
                
                results['scenarios'].append(scenario_result)
        
        return results
        
    except Exception as e:
        if not json_output:
            print_colored(f"Error processing feature file {feature_file}: {e}", Colors.RED, file=sys.stderr)
        return {'error': str(e), 'summary': {}}


def print_summary(results):
    """Print a summary of test results."""
    if 'summary' not in results:
        return
    summary = results['summary']
    
    print_colored("\n" + "-" * 50)
    print_colored("Run Summary:", Colors.BOLD)
    
    scenarios = summary.get('scenarios', {})
    print_colored(f"  Scenarios: {scenarios.get('total', 0)} total, " +
                 f"{Colors.GREEN}{scenarios.get('passed', 0)} passed{Colors.RESET}, {Colors.RED}{scenarios.get('failed', 0)} failed{Colors.RESET}")
    
    steps = summary.get('steps', {})
    print_colored(f"  Steps:     {steps.get('total', 0)} total, " +
                 f"{Colors.GREEN}{steps.get('passed', 0)} passed{Colors.RESET}, {Colors.RED}{steps.get('failed', 0)} failed{Colors.RESET}, " +
                 f"{Colors.YELLOW}{steps.get('skipped', 0)} skipped{Colors.RESET}, {Colors.MAGENTA}{steps.get('undefined', 0)} undefined{Colors.RESET}")
    
    print_colored("-" * 50)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Gherkin Test Runner with Shell Script Implementations')
    parser.add_argument('feature_file', help='Path to the .gherkin feature file')
    parser.add_argument('--impl-dir', default='../gherkin-implements', 
                       help='Directory containing implementation files (default: ../gherkin-implements)')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('implementation_files', nargs='*', help='Specific implementation files to use (overrides --impl-dir)')
    
    args = parser.parse_args()
    
    if not args.json:
        print_colored("--- Gherkin Test Runner ---", Colors.CYAN + Colors.BOLD)
    
    if args.implementation_files:
        impl_files = args.implementation_files
    else:
        impl_files = find_implementation_files(args.impl_dir, args.debug)
    
    if not impl_files:
        print_colored(f"No implementation files found in {args.impl_dir}", Colors.RED, file=sys.stderr)
        sys.exit(1)
    
    implementations = load_all_implementations(impl_files, args.debug)
    
    if not implementations:
        print_colored("No step implementations found", Colors.RED, file=sys.stderr)
        sys.exit(1)
    
    results = run_gherkin_file(args.feature_file, implementations, args.debug, args.json)
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_summary(results)
    
    if 'error' in results or results.get('summary', {}).get('scenarios', {}).get('failed', 0) > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()

