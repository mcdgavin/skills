#!/usr/bin/env python3
# /// script
# dependencies = [
#   "rich>=13.0.0",
#   "pyyaml>=6.0.0",
# ]
# ///
"""
Validate SKILL.md files against the Agent Skills spec.

Usage:
    uv run tools/check-skills.py [--skills-dir skills/]
"""

import re
import sys
import argparse
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()

# Agent Skills spec constraints
REQUIRED_FIELDS = {"name", "description"}
SUPPORTED_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
EXTENSION_FIELDS = {"argument-hint"}  # intentional client extensions — warn but don't error
UNSUPPORTED_FIELDS = {"model"}  # fields we've seen misused

NAME_RE = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
FILE_REF_RE = re.compile(r'\[.*?\]\(((?!https?://)[^)]+)\)')

MAX_DESCRIPTION_LEN = 1024
MAX_SKILL_LINES = 500
WARN_SKILL_LINES = 400


def parse_frontmatter(content: str) -> tuple[dict | None, str, str]:
    """Return (frontmatter_dict, body, error). frontmatter_dict is None on parse error."""
    if not content.startswith("---"):
        return None, content, "No YAML frontmatter found (file must start with ---)"
    end = content.find("\n---", 3)
    if end == -1:
        return None, content, "Frontmatter not closed (missing closing ---)"
    raw = content[3:end].strip()
    body = content[end + 4:].strip()
    try:
        data = yaml.safe_load(raw) or {}
        return data, body, ""
    except yaml.YAMLError as e:
        return None, body, f"YAML parse error: {e}"


def check_skill(skill_dir: Path, skills_root: Path) -> list[tuple[str, str]]:
    """Return list of (severity, message) issues. severity: error | warning."""
    issues = []
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return [("error", "SKILL.md not found")]

    content = skill_md.read_text(errors="replace")
    lines = content.splitlines()

    # Line count
    if len(lines) > MAX_SKILL_LINES:
        issues.append(("warning", f"SKILL.md is {len(lines)} lines (spec recommends ≤{MAX_SKILL_LINES})"))
    elif len(lines) > WARN_SKILL_LINES:
        issues.append(("warning", f"SKILL.md is {len(lines)} lines (approaching {MAX_SKILL_LINES} line limit)"))

    # Frontmatter
    fm, body, err = parse_frontmatter(content)
    if err:
        return issues + [("error", err)]

    # Required fields
    for field in REQUIRED_FIELDS:
        if field not in fm:
            issues.append(("error", f"Missing required field: '{field}'"))

    # Unsupported fields
    for field in UNSUPPORTED_FIELDS:
        if field in fm:
            issues.append(("error", f"Unsupported field '{field}' — not in Agent Skills spec"))

    # Known extensions (warn but allow)
    for field in EXTENSION_FIELDS:
        if field in fm:
            issues.append(("warning", f"'{field}' is not in the Agent Skills spec but is an accepted extension"))

    # Unknown fields (warn, not error — could be client extensions)
    for field in fm:
        if field not in SUPPORTED_FIELDS and field not in UNSUPPORTED_FIELDS and field not in EXTENSION_FIELDS:
            issues.append(("warning", f"Unknown frontmatter field: '{field}'"))

    # Name field validation
    name = fm.get("name", "")
    if name:
        # Must match directory name
        if name != skill_dir.name:
            issues.append(("error", f"'name' field '{name}' does not match directory name '{skill_dir.name}'"))

        # Naming conventions
        if not NAME_RE.match(name):
            issues.append(("error", f"'name' field '{name}' must be lowercase alphanumeric and hyphens only, no consecutive hyphens"))
        if len(name) > 64:
            issues.append(("error", f"'name' field is {len(name)} chars (max 64)"))

    # Description validation
    desc = fm.get("description", "")
    if desc:
        if len(desc) > MAX_DESCRIPTION_LEN:
            issues.append(("error", f"'description' is {len(desc)} chars (max {MAX_DESCRIPTION_LEN})"))
        if len(desc) < 20:
            issues.append(("warning", "description is very short — should describe what skill does and when to use it"))

    # File references
    for match in FILE_REF_RE.finditer(content):
        ref_path = match.group(1)
        full_path = skill_dir / ref_path
        if not full_path.exists():
            issues.append(("error", f"Referenced file not found: '{ref_path}'"))

    return issues


def main():
    parser = argparse.ArgumentParser(description="Validate SKILL.md files against Agent Skills spec")
    parser.add_argument("--skills-dir", default="skills", help="Root skills directory")
    parser.add_argument("--errors-only", action="store_true", help="Only show errors, not warnings")
    args = parser.parse_args()

    skills_root = Path(args.skills_dir)
    if not skills_root.exists():
        console.print(f"[red]Directory not found: {skills_root}[/red]")
        sys.exit(1)

    # Find all skill directories (contain a SKILL.md or are direct children)
    skill_dirs = sorted([
        d for d in skills_root.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    ])

    if not skill_dirs:
        console.print("[yellow]No skill directories found.[/yellow]")
        sys.exit(0)

    all_issues: list[tuple[Path, str, str]] = []  # dir, severity, message
    for skill_dir in skill_dirs:
        issues = check_skill(skill_dir, skills_root)
        for severity, msg in issues:
            if args.errors_only and severity != "error":
                continue
            all_issues.append((skill_dir, severity, msg))

    if all_issues:
        table = Table(title="Skill Validation Issues", show_lines=True)
        table.add_column("Skill", style="cyan", no_wrap=True)
        table.add_column("Level", no_wrap=True)
        table.add_column("Issue")

        for skill_dir, severity, msg in all_issues:
            level_str = f"[red]error[/red]" if severity == "error" else "[yellow]warning[/yellow]"
            table.add_row(skill_dir.name, level_str, msg)

        console.print(table)
    else:
        rprint("[green]✓ All skills are valid[/green]")

    # Summary
    errors = sum(1 for _, s, _ in all_issues if s == "error")
    warnings = sum(1 for _, s, _ in all_issues if s == "warning")
    checked = len(skill_dirs)

    console.print(
        f"\n[bold]Summary:[/bold] {checked} skills checked · "
        f"[red]{errors} errors[/red] · "
        f"[yellow]{warnings} warnings[/yellow]\n"
    )

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
