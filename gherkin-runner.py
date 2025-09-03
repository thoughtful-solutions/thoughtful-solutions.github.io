import re
import os
import sys
import subprocess
import argparse
import glob
import json
import shutil 
from gherkin.parser import Parser

# ANSI color codes for terminal output
class colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_color(text, color, quiet=False):
    """Prints text in a given color, unless in quiet mode."""
    if not quiet:
        print(f"{color}{text}{colors.ENDC}")

def parse_implementation_files(implementation_files, quiet=False):
    """
    Parses the implementation files to extract step implementations.
    The files can be any text file (e.g., .gherkin) as long as they contain IMPLEMENTS blocks.

    Args:
        implementation_files (list): A list of paths to implementation files.
        quiet (bool): Suppress warning messages.

    Returns:
        list: A list of dictionaries, each representing a step implementation
              with its regex pattern and shell script.
    """
    implementations = []
    implementation_pattern = re.compile(r"^\s*IMPLEMENTS\s+(.+)$")

    for file_path in implementation_files:
        if not os.path.exists(file_path):
            print_color(f"Warning: Implementation file not found: {file_path}", colors.WARNING, quiet=quiet)
            continue
            
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        current_script = []
        in_implementation_block = False
        
        current_pattern_str = None

        for i, line in enumerate(lines):
            match = implementation_pattern.match(line)
            
            if (match or i == len(lines) - 1) and in_implementation_block and current_script:
                if i == len(lines) - 1 and not match and line.strip() != '':
                     current_script.append(line)

                if current_pattern_str:
                    pattern = re.sub(r"'([^']*)'", r"'(.*?)'", current_pattern_str)
                    implementations.append({
                        'pattern': re.compile(pattern),
                        'script': "".join(current_script)
                    })
                current_script = []
                in_implementation_block = False

            if match:
                in_implementation_block = True
                current_pattern_str = match.group(1).strip()
                current_script = []
            elif in_implementation_block and line.strip() != "":
                current_script.append(line)
                
    return implementations

def find_implementation(step, implementations):
    """
    Finds a matching implementation for a given Gherkin step.

    Args:
        step (dict): The Gherkin step object.
        implementations (list): The list of available step implementations.

    Returns:
        tuple: A tuple containing the matched implementation and the regex match groups,
               or (None, None) if no match is found.
    """
    step_text = f"{step['keyword'].strip()} {step['text'].strip()}"
    for impl in implementations:
        match = impl['pattern'].match(step_text)
        if match:
            return impl, match.groups()
    return None, None

def execute_step(implementation, args, debug=False, quiet=False):
    """
    Executes the shell script for a step implementation.

    Args:
        implementation (dict): The step implementation dictionary.
        args (tuple): The regex match groups to substitute into the script.
        debug (bool): If True, prints detailed execution info.
        quiet (bool): Suppress printed output.

    Returns:
        subprocess.CompletedProcess: The result of the subprocess run.
    """
    script_to_execute = implementation['script']
    for i, arg in enumerate(args, 1):
        script_to_execute = script_to_execute.replace(f"$MATCH_{i}", arg)

    if debug:
        print_color("--- DEBUG: Executing Script ---", colors.OKBLUE, quiet=quiet)
        print_color(script_to_execute.strip(), colors.OKCYAN, quiet=quiet)
        print_color("-------------------------------", colors.OKBLUE, quiet=quiet)
    
    # MODIFIED: Run bash directly, passing the script via standard input.
    # This is a more reliable method on Windows than using shell=True with executable='bash'.
    bash_path = shutil.which('bash')
    result = subprocess.run(
        [bash_path],             # The command is the full path to bash
        input=script_to_execute, # Pass the script string to stdin
        shell=False,             # We are calling the executable directly
        capture_output=True,
        text=True
    )

    if debug:
        print_color(f"--- DEBUG: Result (Exit Code: {result.returncode}) ---", colors.OKBLUE, quiet=quiet)
        if result.stdout.strip():
            print_color("  stdout:", colors.HEADER, quiet=quiet)
            print_color(result.stdout.strip(), colors.OKCYAN, quiet=quiet)
        if result.stderr.strip():
            print_color("  stderr:", colors.HEADER, quiet=quiet)
            print_color(result.stderr.strip(), colors.FAIL, quiet=quiet)
        print_color("---------------------------------", colors.OKBLUE, quiet=quiet)
        
    return result

def run_feature_file(feature_file_path, implementations, json_output=False, debug=False):
    """
    Parses and runs a .gherkin feature file.

    Args:
        feature_file_path (str): The path to the feature file.
        implementations (list): The list of available step implementations.
        json_output (bool): If True, returns a dict with results instead of printing.
        debug (bool): If True, enables detailed execution logs for each step.

    Returns:
        tuple or dict: If json_output is True, returns a dictionary of results.
                       Otherwise, returns a tuple of (scenarios_failed, steps_undefined).
    """
    stats = {
        'scenarios': 0, 'scenarios_passed': 0, 'scenarios_failed': 0,
        'steps': 0, 'passed': 0, 'failed': 0, 'skipped': 0, 'undefined': 0
    }
    
    results_json = {
        'feature': {},
        'summary': {},
        'scenarios': []
    }

    try:
        with open(feature_file_path, 'r') as f:
            feature_data = Parser().parse(f.read())
    except FileNotFoundError:
        print_color(f"Error: Feature file not found at '{feature_file_path}'", colors.FAIL, quiet=json_output)
        if json_output:
            return {'error': f"Feature file not found at '{feature_file_path}'"}
        return 1, 0

    feature = feature_data['feature']
    
    results_json['feature'] = {
        'name': feature.get('name', 'Untitled Feature'),
        'file': feature_file_path
    }
    
    if not json_output:
        print(f"\nFeature: {feature.get('name', 'Untitled Feature')}")

    for scenario in feature.get('children', []):
        if 'scenario' not in scenario: continue
        scenario = scenario['scenario']

        stats['scenarios'] += 1
        scenario_failed = False
        scenario_result_json = {
            'name': scenario.get('name', 'Untitled Scenario'),
            'status': 'passed',
            'steps': []
        }

        if not json_output:
            print(f"\n  Scenario: {scenario.get('name', 'Untitled Scenario')}")

        for step in scenario.get('steps', []):
            stats['steps'] += 1
            step_text = f"{step['keyword'].strip()} {step['text'].strip()}"
            step_result_json = {
                'keyword': step['keyword'].strip(),
                'text': step['text'].strip(),
                'status': '',
                'output': None
            }

            if scenario_failed:
                stats['skipped'] += 1
                step_result_json['status'] = 'skipped'
                print_color(f"    - {step_text}", colors.OKCYAN, quiet=json_output)
            else:
                impl, args = find_implementation(step, implementations)
                if impl:
                    result = execute_step(impl, args, debug=debug, quiet=json_output)
                    if result.returncode == 0:
                        stats['passed'] += 1
                        step_result_json['status'] = 'passed'
                        print_color(f"    ✔ {step_text}", colors.OKGREEN, quiet=json_output)
                    else:
                        stats['failed'] += 1
                        scenario_failed = True
                        scenario_result_json['status'] = 'failed'
                        step_result_json['status'] = 'failed'
                        step_result_json['output'] = {
                            'stdout': result.stdout.strip(),
                            'stderr': result.stderr.strip()
                        }
                        print_color(f"    ✖ {step_text}", colors.FAIL, quiet=json_output)
                        if not json_output and not debug: 
                            if result.stdout: print(f"      stdout: {result.stdout.strip()}")
                            if result.stderr: print(f"      stderr: {result.stderr.strip()}")
                else:
                    stats['undefined'] += 1
                    scenario_failed = True 
                    scenario_result_json['status'] = 'failed'
                    step_result_json['status'] = 'undefined'
                    print_color(f"    ? {step_text}", colors.WARNING, quiet=json_output)
            
            scenario_result_json['steps'].append(step_result_json)
        
        results_json['scenarios'].append(scenario_result_json)
        if scenario_failed:
            stats['scenarios_failed'] += 1
        else:
            stats['scenarios_passed'] += 1
            
    if json_output:
        results_json['summary'] = {
            'scenarios': {
                'total': stats['scenarios'],
                'passed': stats['scenarios_passed'],
                'failed': stats['scenarios_failed']
            },
            'steps': {
                'total': stats['steps'],
                'passed': stats['passed'],
                'failed': stats['failed'],
                'skipped': stats['skipped'],
                'undefined': stats['undefined']
            }
        }
        return results_json

    print("\n" + "-"*50)
    print("Run Summary:")
    print(f"  Scenarios: {stats['scenarios']} total, {colors.OKGREEN}{stats['scenarios_passed']} passed{colors.ENDC}, {colors.FAIL}{stats['scenarios_failed']} failed{colors.ENDC}")
    print(f"  Steps:     {stats['steps']} total, {colors.OKGREEN}{stats['passed']} passed{colors.ENDC}, {colors.FAIL}{stats['failed']} failed{colors.ENDC}, {colors.OKCYAN}{stats['skipped']} skipped{colors.ENDC}, {colors.WARNING}{stats['undefined']} undefined{colors.ENDC}")
    print("-"*50)

    return stats['scenarios_failed'], stats['undefined']


def main():
    parser = argparse.ArgumentParser(
        description="A Python-based test runner for Gherkin features with shell script implementations.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'feature_file', 
        metavar='FEATURE_FILE',
        help='Path to the .gherkin feature file to execute.'
    )
    parser.add_argument(
        '--impl-dir', 
        metavar='IMPL_DIR',
        default='../gherkin-implements',
        help='Directory to search for implementation files.\nDefaults to ../gherkin-implements'
    )
    parser.add_argument(
        'implementation_files', 
        metavar='IMPL_FILE', 
        nargs='*', 
        help='Optional paths to .gherkin files containing step implementations.\nIf not provided, the script will search the --impl-dir directory.'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output test results in a machine-readable JSON format.'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode to show command execution details.'
    )
    args = parser.parse_args()

    if sys.platform == 'win32':
        if shutil.which('bash') is None:
            print_color("Error: 'bash.exe' was not found in your system's PATH.", colors.FAIL)
            print_color("This script requires a Bash environment to run test steps on Windows.", colors.WARNING)
            print_color("Please install Git for Windows or Windows Subsystem for Linux (WSL) and ensure 'bash.exe' is in your PATH.", colors.WARNING)
            sys.exit(1)

    if not args.json:
        print("--- Gherkin Test Runner ---")
    
    implementation_files_to_load = []
    if args.implementation_files:
        if not args.json:
            print("Loading implementations from command-line arguments.")
        implementation_files_to_load = args.implementation_files
    else:
        impl_path = os.path.join(args.impl_dir, '**', '*.gherkin')
        if not args.json:
            print(f"Searching for implementation files in: {os.path.abspath(args.impl_dir)}")
        implementation_files_to_load = glob.glob(impl_path, recursive=True)

    if not implementation_files_to_load:
        print_color("Error: No implementation files found.", colors.FAIL, quiet=args.json)
        print_color(f"Searched in '{os.path.abspath(args.impl_dir)}' for '*.gherkin' files.", colors.WARNING, quiet=args.json)
        sys.exit(1)

    if not args.json:
        print(f"Loading implementations from {len(implementation_files_to_load)} file(s)...")
    implementations = parse_implementation_files(implementation_files_to_load, quiet=args.json)
    if not args.json:
        print(f"Found {len(implementations)} step implementations.")
    
    results = run_feature_file(args.feature_file, implementations, json_output=args.json, debug=args.debug)

    if args.json:
        print(json.dumps(results, indent=2))
        if 'error' in results or results['summary']['scenarios']['failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
    else:
        scenarios_failed, steps_undefined = results
        if scenarios_failed > 0 or steps_undefined > 0:
            sys.exit(1)
        else:
            sys.exit(0)

if __name__ == "__main__":
    main()