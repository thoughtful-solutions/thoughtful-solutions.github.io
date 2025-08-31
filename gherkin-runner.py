import re
import os
import sys
import subprocess
import argparse
import glob
import json
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

        for i, line in enumerate(lines):
            match = implementation_pattern.match(line)
            if match:
                # If we were in a block, save the previous one
                if in_implementation_block and current_script:
                    # The pattern was on the previous line in the loop
                    prev_line_match = implementation_pattern.match(lines[i-len(current_script)-1])
                    if prev_line_match:
                        pattern_str = prev_line_match.group(1).strip()
                        # Convert gherkin-style regex to python-style
                        pattern = re.sub(r"'([^']*)'", r"'(.*?)'", pattern_str)
                        implementations.append({
                            'pattern': re.compile(pattern),
                            'script': "".join(current_script)
                        })

                # Start a new block
                in_implementation_block = True
                current_script = []
            elif in_implementation_block and (line.strip() == '' or line.startswith('#')):
                # End of block
                if current_script:
                    prev_line_match = implementation_pattern.match(lines[i-len(current_script)-1])
                    if prev_line_match:
                        pattern_str = prev_line_match.group(1).strip()
                        pattern = re.sub(r"'([^']*)'", r"'(.*?)'", pattern_str)
                        implementations.append({
                            'pattern': re.compile(pattern),
                            'script': "".join(current_script)
                        })
                in_implementation_block = False
                current_script = []
            elif in_implementation_block and line.strip() != "":
                # Collect script lines, preserving indentation
                if line.startswith('    '):
                    current_script.append(line[4:])
                else:
                    current_script.append(line)

        # Add the last implementation if the file doesn't end with a blank line
        if in_implementation_block and current_script:
            last_impl_line_index = len(lines) - len(current_script) - 1
            # Find the last IMPLEMENTS line before the script
            for idx in range(len(lines) - len(current_script), -1, -1):
                last_match = implementation_pattern.match(lines[idx])
                if last_match:
                    pattern_str = last_match.group(1).strip()
                    pattern = re.sub(r"'([^']*)'", r"'(.*?)'", pattern_str)
                    implementations.append({
                        'pattern': re.compile(pattern),
                        'script': "".join(current_script)
                    })
                    break

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
    step_text = step['text']
    for impl in implementations:
        match = impl['pattern'].match(step_text)
        if match:
            return impl, match.groups()
    return None, None

def execute_step(implementation, args):
    """
    Executes the shell script for a step implementation.

    Args:
        implementation (dict): The step implementation dictionary.
        args (tuple): The regex match groups to substitute into the script.

    Returns:
        subprocess.CompletedProcess: The result of the subprocess run.
    """
    script_to_execute = implementation['script']
    for i, arg in enumerate(args, 1):
        script_to_execute = script_to_execute.replace(f"$MATCH_{i}", arg)
    
    # Determine the executable to use (bash, or sh as a fallback)
    executable = 'bash' if sys.platform != 'win32' else None 
    # On windows, shell=True will use the default shell, which when using Git Bash,
    # allows it to use bash if it's in the PATH.
    result = subprocess.run(
        script_to_execute,
        shell=True,
        capture_output=True,
        text=True,
        executable=executable
    )
    return result

def run_feature_file(feature_file_path, implementations, json_output=False):
    """
    Parses and runs a .gherkin feature file.

    Args:
        feature_file_path (str): The path to the feature file.
        implementations (list): The list of available step implementations.
        json_output (bool): If True, returns a dict with results instead of printing.

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
                    result = execute_step(impl, args)
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
                        if not json_output:
                            if result.stdout: print(f"      stdout: {result.stdout.strip()}")
                            if result.stderr: print(f"      stderr: {result.stderr.strip()}")
                else:
                    stats['undefined'] += 1
                    scenario_failed = True # Treat undefined steps as a scenario failure
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

    # Human-readable summary
    print("\n" + "-"*50)
    print("Run Summary:")
    print(f"  Scenarios: {stats['scenarios']} total, {colors.OKGREEN}{stats['scenarios_passed']} passed{colors.ENDC}, {colors.FAIL}{stats['scenarios_failed']} failed{colors.ENDC}")
    print(f"  Steps:     {stats['steps']} total, {colors.OKGREEN}{stats['passed']} passed{colors.ENDC}, {colors.FAIL}{stats['failed']} failed{colors.ENDC}, {colors.OKCYAN}{stats['skipped']} skipped{colors.ENDC}, {colors.WARNING}{stats['undefined']} undefined{colors.ENDC}")
    print("-"*50)

    return stats['scenarios_failed'], stats['undefined']


def main():
    """
    Main entry point for the script.
    """
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
        nargs='*', # 0 or more
        help='Optional paths to .gherkin files containing step implementations.\nIf not provided, the script will search the --impl-dir directory.'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output test results in a machine-readable JSON format.'
    )
    args = parser.parse_args()

    if not args.json:
        print("--- Gherkin Test Runner ---")
    
    # 1. Determine which implementation files to use
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

    # 2. Parse all implementation files
    if not args.json:
        print(f"Loading implementations from {len(implementation_files_to_load)} file(s)...")
    implementations = parse_implementation_files(implementation_files_to_load, quiet=args.json)
    if not args.json:
        print(f"Found {len(implementations)} step implementations.")
    
    # 3. Run the feature file
    results = run_feature_file(args.feature_file, implementations, json_output=args.json)

    # 4. Handle output and exit code
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

