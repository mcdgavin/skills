#!/usr/bin/env python3
# /// script
# dependencies = [
#   "rich>=13.0.0",
# ]
# ///
"""
Check all code files for Pinecone client instantiation and verify:
  1. source_tag is present
  2. source_tag value follows naming conventions:
       - lowercase letters, numbers, underscores, and colons only
       - e.g. "pinecone-skills:upsert" is invalid (hyphens not allowed)
       - e.g. "pinecone_skills:upsert" is valid

Usage:
    uv run tools/check-source-tags.py [--dir .]
"""

import re
import sys
import argparse
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()

# File extensions to scan
CODE_EXTENSIONS = {".py", ".js", ".ts", ".mjs", ".cjs", ".jsx", ".tsx", ".go", ".java", ".cs", ".rb"}

# Patterns for Pinecone client instantiation per language family
INSTANTIATION_PATTERNS = [
    re.compile(r'Pinecone\s*\('),          # Python: Pinecone(
    re.compile(r'new\s+Pinecone\s*\('),    # JS/TS: new Pinecone(
    re.compile(r'PineconeClient\s*\('),    # older SDKs
    re.compile(r'new\s+PineconeClient\s*\('),
]

# Patterns to extract source_tag value
SOURCE_TAG_PATTERNS = [
    re.compile(r'source_tag\s*=\s*["\']([^"\']+)["\']'),   # Python: source_tag="value"
    re.compile(r'sourceTag\s*:\s*["\']([^"\']+)["\']'),     # JS/TS: sourceTag: "value"
    re.compile(r'SourceTag\s*:\s*["\']([^"\']+)["\']'),     # Go: SourceTag: "value"
]

# Valid source_tag: lowercase letters, numbers, underscores, colons only
VALID_SOURCE_TAG_RE = re.compile(r'^[a-z0-9_:]+$')

# How many lines after instantiation to look for source_tag
CONTEXT_LINES = 15


def find_code_files(root: Path) -> list[Path]:
    return sorted(
        f for f in root.rglob("*")
        if f.is_file() and f.suffix in CODE_EXTENSIONS
    )


def is_instantiation_line(line: str) -> bool:
    return any(p.search(line) for p in INSTANTIATION_PATTERNS)


def extract_source_tag(window: str) -> str | None:
    """Return the source_tag value found in window, or None."""
    for p in SOURCE_TAG_PATTERNS:
        m = p.search(window)
        if m:
            return m.group(1)
    return None


def check_file(path: Path) -> list[dict]:
    """Return list of findings: {line, type, value?}"""
    findings = []
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return findings

    for i, line in enumerate(lines):
        if not is_instantiation_line(line):
            continue

        # Extract a window: from this line up to CONTEXT_LINES ahead
        window_lines = lines[i: i + CONTEXT_LINES]
        # Stop the window at the likely end of the constructor call
        # (first line that looks like a statement boundary after the call)
        window = "\n".join(window_lines)

        tag_value = extract_source_tag(window)
        lineno = i + 1

        if tag_value is None:
            findings.append({"line": lineno, "type": "missing", "value": None})
        elif not VALID_SOURCE_TAG_RE.match(tag_value):
            findings.append({"line": lineno, "type": "invalid", "value": tag_value})
        else:
            findings.append({"line": lineno, "type": "ok", "value": tag_value})

    return findings


def main():
    parser = argparse.ArgumentParser(description="Check Pinecone source_tag usage in code files")
    parser.add_argument("--dir", default=".", help="Root directory to scan")
    parser.add_argument("--show-ok", action="store_true", help="Also show valid source tags")
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.exists():
        console.print(f"[red]Directory not found: {root}[/red]")
        sys.exit(1)

    files = find_code_files(root)
    if not files:
        console.print("[yellow]No code files found.[/yellow]")
        sys.exit(0)

    all_findings: list[tuple[Path, dict]] = []
    for f in files:
        for finding in check_file(f):
            all_findings.append((f, finding))

    issues = [(f, d) for f, d in all_findings if d["type"] != "ok"]
    ok = [(f, d) for f, d in all_findings if d["type"] == "ok"]

    # Issues table
    if issues:
        table = Table(title="Source Tag Issues", show_lines=True)
        table.add_column("File", style="cyan")
        table.add_column("Line", justify="right", style="dim")
        table.add_column("Issue", style="red")
        table.add_column("Value")

        for path, d in issues:
            rel = path.relative_to(root) if path.is_relative_to(root) else path
            if d["type"] == "missing":
                table.add_row(str(rel), str(d["line"]), "missing source_tag", "")
            else:
                table.add_row(str(rel), str(d["line"]), "invalid source_tag", d["value"])

        console.print(table)
    else:
        rprint("[green]✓ All Pinecone client instantiations have valid source tags[/green]")

    # Valid tags table (optional)
    if args.show_ok and ok:
        table = Table(title="Valid Source Tags", show_lines=True)
        table.add_column("File", style="cyan")
        table.add_column("Line", justify="right", style="dim")
        table.add_column("source_tag", style="green")
        for path, d in ok:
            rel = path.relative_to(root) if path.is_relative_to(root) else path
            table.add_row(str(rel), str(d["line"]), d["value"])
        console.print(table)

    # Summary
    console.print(
        f"\n[bold]Summary:[/bold] {len(files)} files scanned · "
        f"[green]{len(ok)} valid[/green] · "
        f"[red]{len([x for x in issues if x[1]['type'] == 'missing'])} missing[/red] · "
        f"[yellow]{len([x for x in issues if x[1]['type'] == 'invalid'])} invalid[/yellow]\n"
    )

    if issues:
        console.print("[bold]Naming convention:[/bold] lowercase letters, numbers, underscores, and colons only")
        console.print("  [green]✓[/green] pinecone_skills:upsert")
        console.print("  [red]✗[/red] pinecone-skills:upsert  (hyphens not allowed)")
        console.print("  [red]✗[/red] Pinecone_Skills:upsert  (uppercase not allowed)\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
