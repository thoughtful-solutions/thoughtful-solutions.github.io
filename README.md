# **Enterprise Architecture CLI Manager**

ea\_cli.py is a command-line tool for managing Enterprise Architecture (EA) artifacts like Principles, Rules, Domains, and Verifications. It helps maintain a structured, version-controlled repository of your architecture documentation.

## **Features**

* **CRUD Operations**: Create, show, update, and delete artifacts.  
* **Linkage Management**: Link and unlink artifacts to define relationships.  
* **Validation**: A powerful validator checks for untracked files, broken links, and content compliance.  
* **Scaffolding**: An init command to create a fully populated repository with best-practice examples.  
* **Visualization**: Automatically generate relationship diagrams in Mermaid (graphical) or Markdown (text) format.  
* **Configurable**: Use spec.yaml files to define artifact templates and content validation rules.

## **Setup**

1. **Prerequisites**: Python 3.7+  
2. Install Dependencies:  
   Create a requirements.txt file with the content below and run: 
``` 
   pip install -r requirements.txt
```
3. **Make the script executable**:  
```
   chmod +x ea_cli.py
```

## **Step-by-Step Demo: Adding a New Verification**

This tutorial demonstrates the end-to-end workflow for adding a new verification to an existing principle.

### **Step 1: Initialize the Repository**

If you haven't already, start by creating the complete directory structure and populating it with the default artifacts.

```
./ea_cli.py init
```

### **Step 2: Create a New Verification Artifact**

Let's create a verification for the "Simplicity" principle. The goal of this verification is to ensure that the architecture is not overly complex by limiting the number of rules.

```
./ea_cli.py create verification "Simplicity principle is verified by a low rule count" --moscow Must
```

The tool will create a new file, for example: 
```
verifications/V-001-simplicity-principle-is-verified-by-a-low-rule-count.md.
```

### **Step 3: Add Content to the Artifact**

Open the newly created file `(verifications/V-001-...md)` in a text editor and add the specific Gherkin syntax for the verification test.

```gherkin

Feature: Verification for Simplicity Principle (AP-001)  
  As an Enterprise Architect  
  I want to ensure the number of architectural rules is minimal  
  So that the architecture remains simple and easy to understand.

  Scenario: Count the number of active architectural rules  
    GIVEN I have access to the architecture repository  
    WHEN I count the number of files in the 'rules' directory  
    THEN the total number should be less than 10

```

### **Step 4: Link the Verification to the Principle**

Now, we need to formally link our new verification to the "Simplicity" principle it supports.
```
./ea_cli.py link "principles/AP-001-simplicity.md" "verifications/V-001-simplicity-principle-is-verified-by-a-low-rule-count.md"
```
**Output:**
```
Successfully linked 'principles/AP-001-simplicity.md' to 'verifications/V-001-...' (relation: verified\_by). 
```
### **Step 5: Confirm the Linkage**

You can immediately see the result of your linkage by listing the principles. Notice that the LINKS TO count for AP-001-simplicity.md has increased.

```
./ea_cli.py list principle
```
This confirms the relationship is now tracked in the principles/spec.yaml file.

## **Visualizing the Architecture**

The visualize command is a powerful feature for understanding the relationships between your artifacts. You can generate diagrams for a single artifact, a whole category, or the entire repository.

### **Example 1: Visualize a Single Domain (Mermaid Graph)**

To see a graphical representation of the Business Architecture domain and its direct relationships, run:

```
./ea_cli.py visualize domains/D-001-business-architecture.md
```

This will output a Mermaid code block that you can paste into any Markdown viewer that supports it (like GitHub, GitLab, or VS Code with a Mermaid extension).

### **Example 2: Visualize a Principle (Markdown List)**

To get a text-based, hierarchical list for the "Simplicity" principle, use the \--format markdown flag. This is useful for quick navigation as the output contains clickable links.

```
./ea_cli.py visualize principles/AP-001-simplicity.md --format markdown
```

**Output:**
```
* **Principle:** [AP-001-simplicity.md](principles/AP-001-simplicity.md)
    * *Supported By Rules:*
        * **Rule:** [AR-002-modular.md](rules/AR-002-modular.md)

```

### **Example 3: Visualize All Principles**

You can generate a single diagram showing all principles and their connections by using the `--type` option.
```
./ea_cli.py visualize --type principle
```

### **Example 4: Visualize the Entire Architecture**

To get a complete, top-down view of your entire architecture, use \--type all. This starts from the domains and maps out all their descendant principles and rules.

```
./ea_cli.py visualize \-type all --depth 3
```

## **How Validation Works**

The validate all command is a crucial tool for maintaining the integrity of your repository. It performs a series of checks in order:

1. **Scans Directories**: It iterates through each artifact directory (domains/, principles/, etc.).  
2. **Compares Files to Spec**: It compares the list of .md files on the disk with the entries in that directory's spec.yaml file to find:  
   * **Untracked files**: Files that exist on disk but are not registered in spec.yaml.  
   * **Missing files**: Files that are registered in spec.yaml but have been deleted from the disk.  
3. **Checks Links**: It goes through every link in every spec.yaml file and verifies that the target file actually exists, flagging any **broken links**.  
4. **Validates Content (If Configured)**: If a \_\_config\_\_ section with validation\_rules is found in a spec.yaml, it reads the content of each markdown file in that directory and tests it against the specified rules.

### **Demonstrating a Validation Failure**

To see how the validator catches errors, let's intentionally introduce a few problems:

1. **Create an untracked file**:  
  ```
   touch rules/AR-999-untracked-rule.md
  ```

2. **Break a link**: The "Agility" principle (AP-003) is linked to the "Scaleable" rule (AR-004). Let's delete the rule file without unlinking it first.  
```
   rm rules/AR-004-scaleable.md
```

3. **Violate a content rule**: Edit the domains/D-001-business-architecture.md file and remove the text from the \#\# Purpose section, leaving it blank.

Now, run the validator:
```
./ea_cli.py validate all
```

**Expected Error Output:**
```
Running all validation checks...

--- Validating Directory: 'principles' ---  
  [ERROR] Broken link: 'AP-003-agility.md' points to non-existent file 'rules/AR-004-scaleable.md'.

--- Validating Directory: 'rules' ---  
  [ERROR] Untracked file: 'rules/AR-999-untracked-rule.md' is on disk but not in spec.yaml.

--- Validating Directory: 'domains' ---  
  [ERROR] Content error in 'D-001-business-architecture.md': The '## Purpose' section must contain at least one bullet point.

--- Validating Directory: 'verifications' ---

Validation complete. Found 3 error(s). ❌
```

This output clearly identifies each problem, telling you exactly what needs to be fixed to bring the repository back into a compliant state.

## **Extending Validation with spec.yaml**

You can enforce content standards for your artifacts by adding custom rules to the spec.yaml file. This is done inside a special ```__config__``` block.

Each rule requires two properties:

* pattern: A Python-compatible regular expression (regex) to test against the file's content.  
* description: The error message to display if the pattern is not found.

### **Example: Enforcing the 'Purpose' Section in Domains**

Let's ensure that every domain's markdown file has a non-empty "Purpose" section.

1. **Open domains/spec.yaml**.  
2. **Add a validation\_rules block** inside the ```__config__``` section.

```
__config__:  
  template: |  
    # {prefix}: {title}  
      
    ## Purpose  
    - {description}

    ## Scope  
    - <...>

    ## Stakeholders  
    - <...>  

  # Add this new section  
  validation_rules:  
    purpose_exists:  
      description: The '## Purpose' section must contain at least one bullet point.  
      pattern: '## Purpose\n\n- .+'

```

**How this regex works:**

* ```## Purpose\n\n```: Matches the heading ```## Purpose``` followed by two newlines.  
* ```- .+```: Matches a line that starts with a hyphen and a space ```(- )```, followed by one or more characters ```.+```.

Now, if you create or edit a domain file and leave the Purpose section empty, running ```./ea\_cli.py validate all``` will produce a specific, actionable error message.

## **Command Reference**

For detailed help on any command, use the ```--help``` flag. Example: 

```
./ea_cli.py create --help

 Usage: ea_cli.py [OPTIONS] COMMAND [ARGS]...

 A CLI tool to manage Enterprise Architecture artifacts (Principles, Rules, etc.)

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.                                              │
│ --show-completion             Show completion for the current shell, to copy it or customize the installation.       │
│ --help                        Show this message and exit.                                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ init        Initializes a populated repository with sample Principles, Rules, Domains, and their linkages.           │
│ create      Creates a new EA artifact markdown file and registers it in the spec.                                    │
│ list        Lists all artifacts of a given type, showing priority and linkage counts.                                │
│ show        Displays the metadata and content of a single EA artifact.                                               │
│ link        Links two EA artifacts together based on the predefined RELATIONSHIP_MAP.                                │
│ update      Updates the metadata of an existing EA artifact.                                                         │
│ delete      Deletes an EA artifact file and removes it from the spec.                                                │
│ unlink      Removes a link between two EA artifacts.                                                                 │
│ visualize   Generates a relationship visualization for a specific artifact, a type, or all artifacts.                │
│ validate    Tools to validate the compliance and integrity of EA artifacts.                                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
