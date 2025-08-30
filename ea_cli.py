#!/usr/bin/env python3
import typer
import yaml
import re
from pathlib import Path
from typing import List, Optional, Dict, Set
import textwrap

# --- Configuration ---

# Defines the artifact types, their directory names, and filename prefixes.
ARTIFACT_CONFIG = {
    "principle": {"dir": "principles", "prefix": "AP"},
    "rule": {"dir": "rules", "prefix": "AR"},
    "domain": {"dir": "domains", "prefix": "D"},
    "verification": {"dir": "verifications", "prefix": "V"},
}
SPEC_FILENAME = "spec.yaml"
VALID_MOSCOW = ["Must", "Should", "Could", "Wont"]

# Defines the valid relationships between artifacts. This controls the 'link' command.
# Key: source artifact type, Value: dict of relationship names and target artifact types.
RELATIONSHIP_MAP = {
    "principle": {
        "supported_by_rules": "rule",
        "verified_by": "verification"
    },
    "rule": {
        "supports_principles": "principle",
        "verified_by": "verification"
    },
    "domain": {
        "governed_by_principles": "principle"
    }
}

# --- Typer App Initialization ---
app = typer.Typer(
    help="A CLI tool to manage Enterprise Architecture artifacts (Principles, Rules, etc.)"
)
validate_app = typer.Typer(
    help="Tools to validate the compliance and integrity of EA artifacts."
)
app.add_typer(validate_app, name="validate")


# --- Helper Functions ---
def get_artifact_config(artifact_type: str):
    """Gets the configuration for a given artifact type, handling errors."""
    config = ARTIFACT_CONFIG.get(artifact_type.lower())
    if not config:
        typer.secho(f"Error: Unknown artifact type '{artifact_type}'. Valid types are: {list(ARTIFACT_CONFIG.keys())}", fg=typer.colors.RED)
        raise typer.Exit(1)
    return config

def load_spec(artifact_dir: Path) -> dict:
    """Loads and returns the spec.yaml file from a directory."""
    spec_file = artifact_dir / SPEC_FILENAME
    if not spec_file.exists():
        return {}
    # Specify UTF-8 encoding for cross-platform compatibility.
    with open(spec_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}

def save_spec(artifact_dir: Path, data: dict):
    """Saves data to the spec.yaml file in a sorted, readable format."""
    spec_file = artifact_dir / SPEC_FILENAME
    # Specify UTF-8 encoding and dump the entire dictionary at once for safety.
    with open(spec_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, sort_keys=True, indent=2, default_flow_style=False)


def generate_filename(artifact_dir: Path, prefix: str, title: str) -> str:
    """Generates a standardized filename like 'AP-001-my-title.md'."""
    # Create a URL-friendly "slug" from the title.
    slug = re.sub(r'[^\w-]', '', title.lower().replace(' ', '-'))
    
    # Find the highest existing ID number in the directory to determine the next one.
    max_id = 0
    for f in artifact_dir.glob(f"{prefix}-*.md"):
        match = re.match(rf"{prefix}-(\d+)-.*\.md", f.name)
        if match:
            max_id = max(max_id, int(match.group(1)))
            
    new_id = max_id + 1
    return f"{prefix}-{new_id:03d}-{slug}.md"

def get_artifact_path(path_str: str) -> Optional[Path]:
    """Resolves a string like 'principles/AP-001.md' to a Path object if valid."""
    try:
        # Allow plural forms like 'principles'
        dir_name, filename = path_str.split('/', 1)
        artifact_type = dir_name.rstrip('s') 
        config = ARTIFACT_CONFIG.get(artifact_type)
        if not config: return None
        return Path(config["dir"]) / filename
    except (ValueError, KeyError):
        return None

def build_reverse_link_map(root_dir: Path) -> Dict[str, List[str]]:
    """Scans all spec files to build a map of incoming links for each artifact."""
    reverse_map = {}
    for source_config in ARTIFACT_CONFIG.values():
        source_dir = root_dir / source_config['dir']
        if not source_dir.exists():
            continue
        spec_data = load_spec(source_dir)
        for source_filename, metadata in spec_data.items():
            if source_filename == '__config__':
                continue
            source_path_str = str((source_dir / source_filename).as_posix())
            for key, links in metadata.items():
                if key != 'moscow' and isinstance(links, list):
                    for target_path_str in links:
                        reverse_map.setdefault(target_path_str, []).append(source_path_str)
    return reverse_map

# --- Visualization Helper Functions ---
def _traverse_graph(start_path: Path, max_depth: int, current_depth: int = 0) -> Dict:
    """Recursively traverses the artifact graph to build a tree for visualization."""
    if current_depth >= max_depth or not start_path.exists():
        return {}

    spec = load_spec(start_path.parent)
    metadata = spec.get(start_path.name, {})
    
    node = {"children": {}}
    for rel_name, links in metadata.items():
        if rel_name == 'moscow' or not isinstance(links, list):
            continue
        
        child_nodes = {}
        for link_path_str in links:
            child_path = Path(link_path_str)
            child_nodes[link_path_str] = _traverse_graph(child_path, max_depth, current_depth + 1)
        
        if child_nodes:
            node["children"][rel_name] = child_nodes
            
    return node

def _generate_mermaid_output(start_path: Path, graph: Dict, nodes_seen: Set) -> str:
    """Recursively generates Mermaid flowchart syntax from the graph."""
    output = []
    start_path_str = start_path.as_posix()
    start_id = re.sub(r'[^a-zA-Z0-9]', '', start_path_str)
    start_type = start_path.parent.name.rstrip('s')

    if start_path_str not in nodes_seen:
        nodes_seen.add(start_path_str)
        output.append(f'    {start_id}["<b>{start_path.name}</b>"]:::artifact_{start_type};')

    for rel_name, children in graph.get("children", {}).items():
        rel_text = rel_name.replace("_", " ").title()
        for child_path_str, child_graph in children.items():
            child_path = Path(child_path_str)
            child_id = re.sub(r'[^a-zA-Z0-9]', '', child_path_str)
            output.append(f'    {start_id} -- {rel_text} --> {child_id};')
            output.append(_generate_mermaid_output(child_path, child_graph, nodes_seen))
            
    return "\n".join(filter(None, output))

def _generate_markdown_output(start_path: Path, graph: Dict, indent_level: int = 0) -> str:
    """Recursively generates a Markdown nested list from the graph."""
    indent = "    " * indent_level
    # For markdown links, relative paths are more robust
    relative_path = Path(start_path.parent.name) / start_path.name
    output = [f'{indent}* **{start_path.parent.name.rstrip("s").title()}:** [{start_path.name}]({relative_path.as_posix()})']
    
    for rel_name, children in graph.get("children", {}).items():
        rel_text = rel_name.replace("_", " ").title()
        output.append(f'{indent}    * *{rel_text}:*')
        for child_path_str, child_graph in children.items():
            # For nested items, the path needs to be adjusted to be relative from the CWD
            child_path = Path(child_path_str)
            output.append(_generate_markdown_output(child_path, child_graph, indent_level + 2))
            
    return "\n".join(output)

# --- CRUD and Linkage Commands ---

@app.command()
def init(root_dir: Path = typer.Argument(Path("."), help="The root directory for the EA repository.")):
    """
    Initializes a populated repository with sample Principles, Rules, Domains, and their linkages.
    """
    typer.secho(f"Initializing full EA repository in '{root_dir.resolve()}'...", fg=typer.colors.CYAN)
    root_dir.mkdir(exist_ok=True)

    # --- Sample Data Definitions ---
    PRINCIPLES = {
        "Simplicity": "Designs, Guidelines and conventions must be simple",
        "Uniformity": "Common templated design for enterprise services and their supporting infrastructure",
        "Agility": "Must have the ability to respond quickly to demands or opportunities",
        "Efficiency": "Must be efficient in use and operation as well as managed",
        "Proven": "Must be productive, adopted and ideally successful elsewhere",
        "Supportable": "Capable of being supported maintained and defended",
        "Resiliency": "Capable of recovery from effects of adversity"
    }
    RULES = {
        "Reproducible": "One of the main principles of scientific method...",
        "Modular": "Designed with standardised units...",
        "Manageable": "The ability to gather information about the state of environment...",
        "Scaleable": "The ability meet appropriate demands of the systems...",
        "Available": "The ability for resources to be accessible and usable upon demand...",
        "Auditable": "The ability to enquire about what has been provisioned...",
        "Secure": "The environment should be provision in such a manner that it should be protected..."
    }
    DOMAINS = {
        "Business Architecture": "Focuses on business strategy, governance, and key processes.",
        "Data Architecture": "Concerned with the structure of an organization's logical and physical data assets.",
        "Application Architecture": "Provides a blueprint for the individual applications to be deployed.",
        "Technology Architecture": "Describes the logical software and hardware capabilities."
    }
    
    # --- Store generated filenames for later linkage ---
    generated_files = {"principle": {}, "rule": {}, "domain": {}}

    # --- Phase 1: Directory and File Creation ---
    for artifact_type, config in ARTIFACT_CONFIG.items():
        dir_path = root_dir / config['dir']
        dir_path.mkdir(exist_ok=True)
        spec_path = dir_path / SPEC_FILENAME
        
        typer.echo(f"\n--- Setting up '{dir_path}' ---")
        
        if artifact_type == "domain":
            spec_data = yaml.safe_load(textwrap.dedent("""\
                __config__:
                  template: |
                    # {prefix}: {title}
                    
                    ## Purpose
                    - {description}

                    ## Scope
                    - <...>

                    ## Stakeholders
                    - <...>
            """))
            template = spec_data['__config__']['template']
            for title, description in DOMAINS.items():
                filename = generate_filename(dir_path, config['prefix'], title)
                generated_files[artifact_type][title] = filename
                filepath = dir_path / filename
                filepath.write_text(template.format(prefix=config['prefix'], title=title, description=description))
                spec_data[filename] = {'moscow': 'Should', 'governed_by_principles': []}
                typer.echo(f"  Created Domain: {filename}")
            save_spec(dir_path, spec_data)

        elif artifact_type == "principle":
            spec_data = {}
            for title, description in PRINCIPLES.items():
                filename = generate_filename(dir_path, config['prefix'], title)
                generated_files[artifact_type][title] = filename
                filepath = dir_path / filename
                content = f"# {config['prefix']}: {title}\n\n{description}"
                filepath.write_text(content, encoding='utf-8')
                spec_data[filename] = {'moscow': 'Should', 'supported_by_rules': [], 'verified_by': []}
                typer.echo(f"  Created Principle: {filename}")
            save_spec(dir_path, spec_data)

        elif artifact_type == "rule":
            spec_data = {}
            for title, description in RULES.items():
                filename = generate_filename(dir_path, config['prefix'], title)
                generated_files[artifact_type][title] = filename
                filepath = dir_path / filename
                content = f"# {config['prefix']}: {title}\n\n{description}"
                filepath.write_text(content, encoding='utf-8')
                spec_data[filename] = {'moscow': 'Should', 'supports_principles': [], 'verified_by': []}
                typer.echo(f"  Created Rule: {filename}")
            save_spec(dir_path, spec_data)

        else: # Handle verifications and other types
            if not spec_path.exists() or spec_path.stat().st_size == 0:
                spec_path.touch()

    # --- Phase 2: Linkage Creation ---
    typer.echo("\n--- Creating linkages between artifacts ---")

    # Define which Principles govern which Domains
    domain_principle_links = {
        "Business Architecture": ["Agility", "Efficiency", "Simplicity"],
        "Data Architecture": ["Uniformity", "Proven"],
        "Application Architecture": ["Simplicity", "Agility"],
        "Technology Architecture": ["Resiliency", "Supportable", "Proven"]
    }
    
    domain_dir = root_dir / ARTIFACT_CONFIG['domain']['dir']
    domain_spec = load_spec(domain_dir)
    for domain_title, principle_titles in domain_principle_links.items():
        domain_filename = generated_files['domain'].get(domain_title)
        if domain_filename:
            principle_paths = [
                str(Path(ARTIFACT_CONFIG['principle']['dir']) / generated_files['principle'][p_title]).replace('\\', '/')
                for p_title in principle_titles if p_title in generated_files['principle']
            ]
            domain_spec[domain_filename]['governed_by_principles'] = principle_paths
    save_spec(domain_dir, domain_spec)
    typer.echo("  Linked Principles to Domains.")

    # Define which Rules support which Principles
    principle_rule_links = {
        "Simplicity": ["Modular"],
        "Uniformity": ["Modular", "Reproducible"],
        "Agility": ["Scaleable", "Modular"],
        "Efficiency": ["Manageable", "Reproducible"],
        "Resiliency": ["Available", "Secure"],
        "Supportable": ["Manageable"]
    }

    principle_dir = root_dir / ARTIFACT_CONFIG['principle']['dir']
    principle_spec = load_spec(principle_dir)
    for principle_title, rule_titles in principle_rule_links.items():
        principle_filename = generated_files['principle'].get(principle_title)
        if principle_filename:
            rule_paths = [
                str(Path(ARTIFACT_CONFIG['rule']['dir']) / generated_files['rule'][r_title]).replace('\\', '/')
                for r_title in rule_titles if r_title in generated_files['rule']
            ]
            principle_spec[principle_filename]['supported_by_rules'] = rule_paths
    save_spec(principle_dir, principle_spec)
    typer.echo("  Linked Rules to Principles.")

    typer.secho("\nInitialization complete. ✅", fg=typer.colors.GREEN)

@app.command()
def create(
    artifact_type: str = typer.Argument(..., help=f"Type of artifact. Options: {list(ARTIFACT_CONFIG.keys())}"),
    title: str = typer.Argument(..., help="A descriptive title for the artifact."),
    moscow: str = typer.Option("Should", help=f"MoSCoW priority. Options: {VALID_MOSCOW}", case_sensitive=False)
):
    """
    Creates a new EA artifact markdown file and registers it in the spec.
    """
    moscow_val = moscow.capitalize()
    if moscow_val not in VALID_MOSCOW:
        typer.secho(f"Error: Invalid MoSCoW value '{moscow}'. Must be one of {VALID_MOSCOW}", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    config = get_artifact_config(artifact_type)
    artifact_dir = Path(config['dir'])
    
    if not artifact_dir.exists():
        typer.secho(f"Error: Directory '{artifact_dir}' does not exist. Run 'ea-mgr init' first.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    spec_data = load_spec(artifact_dir)
    filename = generate_filename(artifact_dir, config['prefix'], title)
    filepath = artifact_dir / filename
    
    # Check for a custom template in the spec's __config__ section
    template = spec_data.get('__config__', {}).get('template')
    if template:
        template = template.format(prefix=config['prefix'], title=title, description="<...>")
    else: # Fallback to default generic template
        template = f"# {config['prefix']}: {title}\n\n(Description of the {artifact_type} goes here.)\n"
        if artifact_type == "verification":
            template += textwrap.dedent("""
                ## Gherkin Verification

                ```gherkin
                Feature: Verification for ...
                  As a ...
                  I want to ...
                  So that ...

                  Scenario: ...
                    Given ...
                    When ...
                    Then ...
                ```
                """)
    filepath.write_text(template, encoding='utf-8')
    
    # Update the spec.yaml
    spec_data[filename] = { "moscow": moscow_val }
    
    relationships = RELATIONSHIP_MAP.get(artifact_type, {})
    for rel_name in relationships:
        spec_data[filename][rel_name] = []
        
    save_spec(artifact_dir, spec_data)
    
    typer.secho(f"Successfully created {artifact_type}: '{filepath}' ✨", fg=typer.colors.GREEN)

@app.command("list")
def list_artifacts(
    artifact_type: str = typer.Argument(..., help=f"Type of artifact to list. Options: {list(ARTIFACT_CONFIG.keys())}", case_sensitive=False)
):
    """
    Lists all artifacts of a given type, showing priority and linkage counts.
    """
    config = get_artifact_config(artifact_type)
    artifact_dir = Path(config['dir'])
    
    if not artifact_dir.exists():
        typer.secho(f"Error: Directory '{artifact_dir}' does not exist. Run 'ea-mgr init' first.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    spec_data = load_spec(artifact_dir)
    artifact_entries = {k: v for k, v in spec_data.items() if k != '__config__'}

    typer.secho(f"--- Listing {len(artifact_entries)} {artifact_type.capitalize()}s ---", fg=typer.colors.CYAN, bold=True)
    
    if not artifact_entries:
        typer.echo(f"No {artifact_type}s found in '{artifact_dir}'.")
        return

    # Build a reverse-lookup map of all incoming links in the repository
    reverse_link_map = build_reverse_link_map(Path("."))

    # Table layout with linkages
    header = f"{'MOSCOW':<8}| {'LINKS TO':<10}| {'LINKED FROM':<12}| FILENAME"
    typer.secho(header, bold=True)
    typer.secho("-" * (len(header) + 20), bold=True)

    for filename, metadata in sorted(artifact_entries.items()):
        moscow = metadata.get('moscow', 'N/A')

        # Calculate outgoing links (links from this artifact)
        outgoing_links = 0
        for key, value in metadata.items():
            if key != 'moscow' and isinstance(value, list):
                outgoing_links += len(value)

        # Calculate incoming links (links to this artifact)
        full_path_str = str((artifact_dir / filename).as_posix())
        incoming_links = len(reverse_link_map.get(full_path_str, []))
        
        typer.echo(f"{moscow:<8}| {outgoing_links:<10}| {incoming_links:<12}| {filename}")


@app.command()
def show(
    artifact_type: str = typer.Argument(..., help=f"Type of artifact. Options: {list(ARTIFACT_CONFIG.keys())}"),
    filename: str = typer.Argument(..., help="Filename of the artifact to display (e.g., 'AP-001-simplicity.md').")
):
    """
    Displays the metadata and content of a single EA artifact.
    """
    config = get_artifact_config(artifact_type)
    artifact_dir = Path(config['dir'])
    artifact_path = artifact_dir / filename
    
    if not artifact_path.exists():
        typer.secho(f"Error: Artifact '{artifact_path}' not found.", fg=typer.colors.RED)
        raise typer.Exit(1)

    spec_data = load_spec(artifact_path.parent)
    metadata = spec_data.get(filename)

    if not metadata:
        typer.secho(f"Error: Artifact '{filename}' not found in its spec file. Please run validation.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    # Display Metadata
    typer.secho(f"--- Metadata for {filename} ---", fg=typer.colors.CYAN, bold=True)
    # Use PyYAML to dump the metadata part for nice formatting, ensuring clean output
    metadata_str = yaml.dump(metadata, indent=2, sort_keys=True, default_flow_style=False).strip()
    typer.echo(metadata_str)
    
    # Display Content
    try:
        content = artifact_path.read_text(encoding='utf-8')
        typer.secho(f"\n--- Content ---", fg=typer.colors.CYAN, bold=True)
        typer.echo(content.strip())
    except Exception as e:
        typer.secho(f"Error reading file content: {e}", fg=typer.colors.RED)


@app.command()
def link(
    source: str = typer.Argument(..., help="Source artifact path (e.g., 'principles/AP-001...md')"),
    target: str = typer.Argument(..., help="Target artifact path (e.g., 'rules/AR-002...md')")
):
    """
    Links two EA artifacts together based on the predefined RELATIONSHIP_MAP.
    """
    source_path = get_artifact_path(source)
    target_path = get_artifact_path(target)

    if not source_path or not source_path.exists():
        typer.secho(f"Error: Source artifact '{source}' not found.", fg=typer.colors.RED)
        raise typer.Exit(1)
    if not target_path or not target_path.exists():
        typer.secho(f"Error: Target artifact '{target}' not found.", fg=typer.colors.RED)
        raise typer.Exit(1)

    source_type = source_path.parent.name.rstrip('s')
    target_type = target_path.parent.name.rstrip('s')
    
    # Find the correct relationship key from the map
    relationship_key = None
    valid_relations = RELATIONSHIP_MAP.get(source_type, {})
    for key, value in valid_relations.items():
        if value == target_type:
            relationship_key = key
            break
            
    if not relationship_key:
        typer.secho(f"Error: No valid relationship is defined to link a '{source_type}' to a '{target_type}'.", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Update the source artifact's spec.yaml to add the link
    spec_data = load_spec(source_path.parent)
    if source_path.name not in spec_data:
        typer.secho(f"Error: Source '{source_path.name}' not found in its spec file. Please validate.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    links = spec_data[source_path.name].setdefault(relationship_key, [])
    target_str = str(target_path.as_posix()) # Use forward slashes for consistency
    
    if target_str not in links:
        links.append(target_str)
        save_spec(source_path.parent, spec_data)
        typer.secho(f"Successfully linked '{source}' to '{target}' (relation: {relationship_key}). 🔗", fg=typer.colors.GREEN)
    else:
        typer.secho("Link already exists. No changes made.", fg=typer.colors.YELLOW)

@app.command()
def update(
    artifact_path_str: str = typer.Argument(..., help="Path of the artifact to update (e.g., 'principles/AP-001...md')."),
    moscow: Optional[str] = typer.Option(None, help=f"New MoSCoW priority. Options: {VALID_MOSCOW}", case_sensitive=False)
):
    """
    Updates the metadata of an existing EA artifact.
    """
    if moscow is None:
        typer.echo("No update options provided. Nothing to do.")
        raise typer.Exit()

    artifact_path = get_artifact_path(artifact_path_str)
    if not artifact_path or not artifact_path.exists():
        typer.secho(f"Error: Artifact '{artifact_path_str}' not found.", fg=typer.colors.RED)
        raise typer.Exit(1)
    
    spec_data = load_spec(artifact_path.parent)
    filename = artifact_path.name
    
    if filename not in spec_data:
        typer.secho(f"Error: Artifact '{filename}' not found in its spec file. Please run validation.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    updated = False
    if moscow:
        moscow_val = moscow.capitalize()
        if moscow_val not in VALID_MOSCOW:
            typer.secho(f"Error: Invalid MoSCoW value '{moscow}'. Must be one of {VALID_MOSCOW}", fg=typer.colors.RED)
            raise typer.Exit(1)
        if spec_data[filename].get('moscow') != moscow_val:
            spec_data[filename]['moscow'] = moscow_val
            updated = True
            typer.echo(f"Updated MoSCoW for '{filename}' to '{moscow_val}'.")

    if updated:
        save_spec(artifact_path.parent, spec_data)
        typer.secho(f"\nSuccessfully updated '{filename}'. ✨", fg=typer.colors.GREEN)
    else:
        typer.secho("No changes detected.", fg=typer.colors.YELLOW)

@app.command()
def delete(
    artifact_path_str: str = typer.Argument(..., help="Path of the artifact to delete (e.g., 'principles/AP-001...md')."),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation.")
):
    """
    Deletes an EA artifact file and removes it from the spec.
    """
    artifact_path = get_artifact_path(artifact_path_str)
    if not artifact_path or not artifact_path.exists():
        typer.secho(f"Error: Artifact '{artifact_path_str}' not found.", fg=typer.colors.RED)
        raise typer.Exit(1)

    if not force:
        typer.secho(f"You are about to delete '{artifact_path}'. This cannot be undone.", fg=typer.colors.YELLOW)
        if not typer.confirm("Are you sure you want to proceed?"):
            raise typer.Abort()

    # Remove from spec
    spec_data = load_spec(artifact_path.parent)
    filename = artifact_path.name
    if filename in spec_data:
        del spec_data[filename]
        save_spec(artifact_path.parent, spec_data)
        typer.echo(f"Removed '{filename}' from {SPEC_FILENAME}.")
    
    # Delete the file
    artifact_path.unlink()
    typer.echo(f"Deleted file '{artifact_path}'.")
    
    typer.secho(f"\nSuccessfully deleted '{filename}'. 🗑️", fg=typer.colors.GREEN)
    typer.secho("Warning: This may have created broken links in other artifacts. Run 'validate all' to check.", fg=typer.colors.YELLOW)


@app.command()
def unlink(
    source: str = typer.Argument(..., help="Source artifact path (e.g., 'principles/AP-001...md')"),
    target: str = typer.Argument(..., help="Target artifact path to remove from links (e.g., 'rules/AR-002...md')")
):
    """
    Removes a link between two EA artifacts.
    """
    source_path = get_artifact_path(source)
    target_path = get_artifact_path(target)

    if not source_path or not source_path.exists():
        typer.secho(f"Error: Source artifact '{source}' not found.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    if not target_path:
        # We don't need the target to exist, but the path format must be valid to proceed.
        typer.secho(f"Error: Target path '{target}' is not a valid artifact path format.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    source_type = source_path.parent.name.rstrip('s')
    target_type = target_path.parent.name.rstrip('s')
    
    relationship_key = None
    valid_relations = RELATIONSHIP_MAP.get(source_type, {})
    for key, value in valid_relations.items():
        if value == target_type:
            relationship_key = key
            break
            
    if not relationship_key:
        typer.secho(f"Error: No valid relationship is defined from a '{source_type}' to a '{target_type}'.", fg=typer.colors.RED)
        raise typer.Exit(1)

    spec_data = load_spec(source_path.parent)
    if source_path.name not in spec_data:
        typer.secho(f"Error: Source '{source_path.name}' not found in its spec file.", fg=typer.colors.RED)
        raise typer.Exit(1)
        
    links = spec_data[source_path.name].get(relationship_key, [])
    target_str = str(target_path.as_posix())
    
    if target_str in links:
        links.remove(target_str)
        save_spec(source_path.parent, spec_data)
        typer.secho(f"Successfully unlinked '{target}' from '{source}'. 💔", fg=typer.colors.GREEN)
    else:
        typer.secho(f"Link from '{source}' to '{target}' not found. No changes made.", fg=typer.colors.YELLOW)

@app.command()
def visualize(
    artifact_path_str: Optional[str] = typer.Argument(None, help="Path of the starting artifact (e.g., 'domains/D-001...md')."),
    artifact_type: Optional[str] = typer.Option(None, "--type", "-t", help="Visualize all artifacts of a specific type (e.g., 'domain') or 'all'."),
    format: str = typer.Option("mermaid", "--format", "-f", help="Output format: 'mermaid' or 'markdown'"),
    depth: int = typer.Option(3, "--depth", "-d", help="How many levels of relationships to show.")
):
    """
    Generates a relationship visualization for a specific artifact, a type, or all artifacts.
    """
    if not artifact_path_str and not artifact_type:
        typer.secho("Error: You must provide an artifact path OR an artifact type using --type (e.g., --type domain or --type all).", fg=typer.colors.RED)
        raise typer.Exit(1)

    start_paths = []
    if artifact_path_str:
        start_path = get_artifact_path(artifact_path_str)
        if not start_path or not start_path.exists():
            typer.secho(f"Error: Artifact '{artifact_path_str}' not found.", fg=typer.colors.RED)
            raise typer.Exit(1)
        start_paths.append(start_path)
    
    elif artifact_type:
        if artifact_type.lower() == 'all':
            # For 'all', we typically want to start from the top-level (domains)
            # and traverse down. This makes the graph more readable.
            config = get_artifact_config('domain')
            dir_path = Path(config['dir'])
            if dir_path.exists():
                start_paths.extend(sorted(dir_path.glob("*.md")))
        else:
            config = get_artifact_config(artifact_type)
            dir_path = Path(config['dir'])
            if dir_path.exists():
                start_paths.extend(sorted(dir_path.glob("*.md")))

    if not start_paths:
        typer.secho("No artifacts found to visualize.", fg=typer.colors.YELLOW)
        raise typer.Exit()

    # Build a traversable graph for each starting path
    graphs = {path: _traverse_graph(path, depth) for path in start_paths}

    # --- Generate Output ---
    if format.lower() == "mermaid":
        header = textwrap.dedent("""\
            ```mermaid
            graph TD;
                %% --- Define Node Styles ---
                classDef artifact_domain fill:#87CEEB,stroke:#333,stroke-width:2px;
                classDef artifact_principle fill:#98FB98,stroke:#333,stroke-width:2px;
                classDef artifact_rule fill:#FFDAB9,stroke:#333,stroke-width:2px;
                classDef artifact_verification fill:#D8BFD8,stroke:#333,stroke-width:2px;

                %% --- Define Nodes & Links ---
            """)
        footer = "```"
        
        # Use a single nodes_seen set to avoid defining nodes more than once
        nodes_seen = set()
        mermaid_bodies = [_generate_mermaid_output(path, graph, nodes_seen) for path, graph in graphs.items()]
        # Join bodies and filter out empty strings
        full_body = "\n".join(filter(None, mermaid_bodies))
        output = f"{header}{full_body}\n{footer}"
    
    elif format.lower() == "markdown":
        markdown_outputs = [_generate_markdown_output(path, graph) for path, graph in graphs.items()]
        output = "\n\n---\n\n".join(markdown_outputs)

    else:
        typer.secho(f"Error: Invalid format '{format}'. Choose 'mermaid' or 'markdown'.", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo(output)
    
# --- Validation Functions ---
def validate_content_with_rules(filepath: Path, rules: Dict) -> List[str]:
    """
    Validates the content of a markdown file against a set of regex-based rules.
    Returns a list of error strings for any failed rules.
    """
    errors = []
    if not rules:
        return errors
        
    content = filepath.read_text(encoding='utf-8')
    
    for rule_name, rule_data in rules.items():
        pattern = rule_data.get("pattern")
        description = rule_data.get("description", f"Rule '{rule_name}' failed.")
        if not pattern:
            continue
        
        try:
            # Check if the pattern is found in the content. Add (?s) flag for multiline matching.
            if not re.search(pattern, content, re.MULTILINE):
                errors.append(f"Content error in '{filepath.name}': {description}")
        except re.error as e:
            errors.append(f"Regex error in spec file for rule '{rule_name}': {e}")
            
    return errors

@validate_app.command("all", help="Runs all validation checks across the entire EA repository.")
def validate_all():
    """
    Performs a comprehensive compliance check of the repository.
    """
    typer.secho("Running all validation checks...", fg=typer.colors.CYAN)
    error_count = 0
    
    for artifact_type, config in ARTIFACT_CONFIG.items():
        artifact_dir = Path(config['dir'])
        if not artifact_dir.exists():
            continue
        
        typer.echo(f"\n--- Validating Directory: '{artifact_dir}' ---")
        
        spec_data = load_spec(artifact_dir)
        validation_rules = spec_data.get('__config__', {}).get('validation_rules', {})
        
        # We only care about artifact entries, so remove the config section for validation
        artifact_entries = {k: v for k, v in spec_data.items() if k != '__config__'}
        
        spec_files = set(artifact_entries.keys())
        disk_files = {f.name for f in artifact_dir.glob("*.md")}
        
        # Check 1: Files on disk that are not tracked in spec.yaml
        untracked = disk_files - spec_files
        for f in untracked:
            typer.secho(f"  [ERROR] Untracked file: '{artifact_dir / f}' is on disk but not in {SPEC_FILENAME}.", fg=typer.colors.RED)
            error_count += 1
            
        # Check 2: Files in spec.yaml that are missing from disk
        missing = spec_files - disk_files
        for f in missing:
            typer.secho(f"  [ERROR] Missing file: '{artifact_dir / f}' is in {SPEC_FILENAME} but not on disk.", fg=typer.colors.RED)
            error_count += 1
            
        # Check 3: Individual spec entries for correctness
        for filename, data in artifact_entries.items():
            if filename in missing: continue # Already reported
            
            # Check MoSCoW field
            if 'moscow' not in data or data.get('moscow') not in VALID_MOSCOW:
                typer.secho(f"  [ERROR] Invalid spec: '{filename}' has a missing or invalid MoSCoW value.", fg=typer.colors.RED)
                error_count += 1
            
            # Check that all defined links point to existing files
            for key, links in data.items():
                if key == 'moscow': continue
                if isinstance(links, list):
                    for link_path_str in links:
                        if not Path(link_path_str).exists():
                            typer.secho(f"  [ERROR] Broken link: '{filename}' points to non-existent file '{link_path_str}'.", fg=typer.colors.RED)
                            error_count += 1
            
            # Check 4: Content validation using rules from spec.yaml
            if validation_rules:
                content_errors = validate_content_with_rules(artifact_dir / filename, validation_rules)
                for err in content_errors:
                    typer.secho(f"  [ERROR] {err}", fg=typer.colors.RED)
                    error_count += 1
    
    if error_count == 0:
        typer.secho("\nValidation complete. All checks passed! ✅", fg=typer.colors.GREEN)
    else:
        typer.secho(f"\nValidation complete. Found {error_count} error(s). ❌", fg=typer.colors.RED)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

