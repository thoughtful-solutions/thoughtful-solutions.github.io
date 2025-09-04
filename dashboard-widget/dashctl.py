#!/usr/bin/env python
import sys
import argparse
import json
import textwrap

def generate_html_output(mermaid_code, title):
    """
    Generates a full HTML document that renders a Mermaid.js chart.

    Args:
        mermaid_code (str): The Mermaid syntax for the chart.
        title (str): The title for the HTML page and widget.

    Returns:
        str: A complete HTML document as a string.
    """
    # Use a modern ESM import for Mermaid.js from a CDN
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title or 'DashCtl Widget'}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background-color: #f0f2f5;
            }}
            .widget-container {{
                padding: 24px;
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                min-width: 400px;
                max-width: 800px;
            }}
        </style>
    </head>
    <body>
        <div class="widget-container">
            <pre class="mermaid">
                {mermaid_code}
            </pre>
        </div>
        <script type="module">
            import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
            mermaid.initialize({{ startOnLoad: true }});
        </script>
    </body>
    </html>
    """
    return textwrap.dedent(html_template).strip()

def handle_category_breakdown(data, args):
    """
    Generates Mermaid syntax for the 'category-breakdown' widget.

    Args:
        data (list): Parsed JSON data, expecting a list of objects.
        args (argparse.Namespace): The parsed command-line arguments.

    Returns:
        str: The full HTML page for the pie chart widget.
    """
    if not isinstance(data, list):
        print("Error: Input data for category-breakdown must be a JSON array.", file=sys.stderr)
        sys.exit(1)

    # Start building the Mermaid pie chart syntax
    mermaid_lines = ["pie"]
    if args.title:
        # Add the title inside the Mermaid syntax for rendering
        mermaid_lines.append(f'    title {args.title}')

    for item in data:
        # Ensure item is a dictionary with the required keys
        if isinstance(item, dict) and 'category' in item and 'value' in item:
            # Mermaid labels with spaces or special characters need to be quoted
            category_label = f'"{item["category"]}"'
            mermaid_lines.append(f'    {category_label} : {item["value"]}')
        else:
            print(f"Warning: Skipping invalid item in data stream: {item}", file=sys.stderr)

    mermaid_code = "\n".join(mermaid_lines)
    # The page title is also set from the command-line argument
    return generate_html_output(mermaid_code, args.title)

def main():
    """
    Main function to parse arguments, handle data input, and generate the widget.
    """
    parser = argparse.ArgumentParser(
        description="DashCtl - A simple CLI to transform data into dashboard widgets.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Core Philosophy:
- Pure data transformation. No external dependencies. No file I/O.
- Data in via STDIN or --data flag. Widget out via STDOUT.

Example:
echo '[{"category": "Malware", "value": 35}]' | python dashctl.py category-breakdown --title "Incidents"
"""
    )

    # Global options applicable to all widgets
    parser.add_argument(
        '--data',
        help='Inline JSON data as a string.'
    )
    parser.add_argument(
        '--output',
        choices=['html'],
        default='html',
        help='Output format (default: html).'
    )

    # --- Widget Subparsers ---
    # This structure allows adding more widgets like 'metric-card', 'trend-chart', etc.
    subparsers = parser.add_subparsers(dest='widget_type', required=True, help='The type of widget to generate.')

    # CategoryBreakdown Widget Parser
    parser_category = subparsers.add_parser('category-breakdown', help='Display a category distribution as a pie chart.')
    parser_category.add_argument('--title', help='Title for the widget.')
    parser_category.add_argument('--chart-type', choices=['pie', 'donut'], default='pie', help='Type of chart (Note: Mermaid renders both as pie charts).')
    # Link the subparser to its handler function
    parser_category.set_defaults(func=handle_category_breakdown)

    args = parser.parse_args()

    # --- Data Input Handling ---
    # Prefer --data flag, otherwise read from STDIN if available.
    input_data_str = None
    if args.data:
        input_data_str = args.data
    elif not sys.stdin.isatty():
        input_data_str = sys.stdin.read()

    if not input_data_str:
        parser.error("No data provided. Pipe data via STDIN or use the --data argument.")

    # --- Data Parsing and Processing ---
    try:
        data = json.loads(input_data_str)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON provided. {e}", file=sys.stderr)
        sys.exit(1)

    # --- Dispatch to the correct widget handler ---
    # The 'func' attribute was set by 'set_defaults' above
    if hasattr(args, 'func'):
        output_content = args.func(data, args)
        print(output_content)
    else:
        # This case is a fallback, but argparse 'required=True' should prevent it
        print(f"Error: Widget type '{args.widget_type}' is not implemented.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()