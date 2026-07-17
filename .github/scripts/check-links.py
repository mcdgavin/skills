#!/usr/bin/env python3
# /// script
# dependencies = [
#   "httpx>=0.27.0",
#   "rich>=13.0.0",
# ]
# ///
"""
Check all URLs in skill markdown files.

Usage:
    uv run tools/check-links.py [--skills-dir skills/]
"""

import re
import sys
import argparse
from pathlib import Path
from collections import defaultdict

import httpx
from rich.console import Console
from rich.table import Table
from rich import print as rprint

console = Console()

URL_RE = re.compile(r'https?://[^\s\)\]>"\']+')

TIMEOUT = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; skill-link-checker/1.0)"}


def find_urls(path: Path) -> list[tuple[int, str]]:
    """Return list of (line_number, url) from a file."""
    results = []
    for i, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        for url in URL_RE.findall(line):
            # Strip trailing punctuation that's not part of the URL
            url = url.rstrip(".,;:!?)")
            results.append((i, url))
    return results


def check_url(url: str, client: httpx.Client) -> tuple[str, str]:
    """Return (status, detail). Status: ok | redirect | error | timeout."""
    try:
        r = client.head(url, follow_redirects=False, timeout=TIMEOUT, headers=HEADERS)
        if r.status_code in (301, 302, 307, 308):
            location = r.headers.get("location", "")
            return "redirect", f"{r.status_code} → {location}"
        if r.status_code == 405:
            # HEAD not allowed, try GET
            r = client.get(url, follow_redirects=True, timeout=TIMEOUT, headers=HEADERS)
        if 200 <= r.status_code < 300:
            return "ok", str(r.status_code)
        return "error", str(r.status_code)
    except httpx.TimeoutException:
        return "timeout", "timed out"
    except httpx.RequestError as e:
        return "error", str(e)


def main():
    parser = argparse.ArgumentParser(description="Check links in skill markdown files")
    parser.add_argument("--skills-dir", default="skills", help="Root skills directory")
    parser.add_argument("--ignore-redirects", action="store_true", help="Don't report redirects")
    args = parser.parse_args()

    skills_dir = Path(args.skills_dir)
    if not skills_dir.exists():
        console.print(f"[red]Directory not found: {skills_dir}[/red]")
        sys.exit(1)

    md_files = sorted(skills_dir.rglob("*.md"))
    if not md_files:
        console.print("[yellow]No markdown files found.[/yellow]")
        sys.exit(0)

    # Collect all URLs
    file_urls: dict[Path, list[tuple[int, str]]] = {}
    all_urls: set[str] = set()
    for f in md_files:
        urls = find_urls(f)
        if urls:
            file_urls[f] = urls
            all_urls.update(u for _, u in urls)

    console.print(f"\nFound [bold]{len(all_urls)}[/bold] unique URLs across [bold]{len(file_urls)}[/bold] files\n")

    # Check all unique URLs
    url_results: dict[str, tuple[str, str]] = {}
    with httpx.Client(follow_redirects=False) as client:
        for i, url in enumerate(sorted(all_urls), 1):
            console.print(f"  [{i}/{len(all_urls)}] Checking {url[:80]}...", end="\r")
            url_results[url] = check_url(url, client)
    console.print(" " * 100, end="\r")  # clear progress line

    # Report results grouped by file
    errors: list[tuple[Path, int, str, str, str]] = []  # file, line, url, status, detail
    redirects: list[tuple[Path, int, str, str, str]] = []

    for f, urls in sorted(file_urls.items()):
        for line_no, url in urls:
            status, detail = url_results[url]
            if status == "error" or status == "timeout":
                errors.append((f, line_no, url, status, detail))
            elif status == "redirect" and not args.ignore_redirects:
                redirects.append((f, line_no, url, status, detail))

    # Errors table
    if errors:
        table = Table(title="Broken Links", show_lines=True)
        table.add_column("File", style="cyan", no_wrap=True)
        table.add_column("Line", justify="right", style="dim")
        table.add_column("URL")
        table.add_column("Issue", style="red")
        for f, line_no, url, status, detail in errors:
            rel = f.relative_to(skills_dir)
            table.add_row(str(rel), str(line_no), url, f"{status}: {detail}")
        console.print(table)
    else:
        rprint("[green]✓ No broken links found[/green]")

    # Redirects table
    if redirects:
        table = Table(title="Redirects (consider updating)", show_lines=True)
        table.add_column("File", style="cyan", no_wrap=True)
        table.add_column("Line", justify="right", style="dim")
        table.add_column("URL")
        table.add_column("Detail", style="yellow")
        for f, line_no, url, status, detail in redirects:
            rel = f.relative_to(skills_dir)
            table.add_row(str(rel), str(line_no), url, detail)
        console.print(table)

    # Summary
    ok_count = sum(1 for s, _ in url_results.values() if s == "ok")
    console.print(
        f"\n[bold]Summary:[/bold] {ok_count} ok · "
        f"[red]{len(errors)} broken[/red] · "
        f"[yellow]{len(redirects)} redirects[/yellow]\n"
    )

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
