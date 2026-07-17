#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Enforce that skills have cultivar tests attached.

A skill `skills/<name>/` "has tests" iff `tasks/<name>.yaml` exists. To keep
adoption incremental, this only enforces the rule on skills you ask it to check
(typically the ones touched in a PR) — pre-existing untested skills are
grandfathered until they're next modified. Pass `--all` to audit every skill.

Stdlib only, so CI can run it with bare `python3` or `uv run`.

Usage:
    # Enforce on specific (changed) skills:
    python3 check-has-tests.py --changed pinecone-cli pinecone-query
    # Audit the whole repo:
    python3 check-has-tests.py --all

Exit code: 0 if every enforced skill has a task file, 1 otherwise.
"""

import argparse
import sys
from pathlib import Path


def discover_skills(skills_dir: Path) -> set[str]:
    """Skill names = subdirs of skills_dir containing a SKILL.md."""
    if not skills_dir.exists():
        return set()
    return {
        d.name
        for d in skills_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / "SKILL.md").exists()
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Check that skills have cultivar test files")
    ap.add_argument("--skills-dir", default="skills", type=Path)
    ap.add_argument("--tasks-dir", default="tasks", type=Path)
    ap.add_argument(
        "--changed",
        nargs="*",
        default=[],
        help="Skill names to enforce (e.g. the skills touched in this PR)",
    )
    ap.add_argument("--all", action="store_true", help="Enforce on every skill in --skills-dir")
    args = ap.parse_args()

    known = discover_skills(args.skills_dir)

    if args.all:
        enforce = sorted(known)
    else:
        # Only enforce on changed names that are actually skills (ignore deletes
        # and non-skill paths the caller may have passed through).
        enforce = sorted(set(args.changed) & known)

    if not enforce:
        print("check-has-tests: no skills to enforce (nothing changed, or none matched).")
        return 0

    missing = [name for name in enforce if not (args.tasks_dir / f"{name}.yaml").exists()]

    for name in enforce:
        status = "MISSING" if name in missing else "ok"
        print(f"  [{status:>7}] {name}  ->  {args.tasks_dir}/{name}.yaml")

    if missing:
        sys.stdout.flush()
        print(
            f"\ncheck-has-tests: ERROR — {len(missing)} changed skill(s) lack a test file:\n"
            + "\n".join(f"  - create {args.tasks_dir}/{n}.yaml (try: cultivar init {n} --skills-dir {args.skills_dir})" for n in missing),
            file=sys.stderr,
        )
        return 1

    print(f"\ncheck-has-tests: ok — all {len(enforce)} enforced skill(s) have a test file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
