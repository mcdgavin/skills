#!/usr/bin/env python3
"""
Summarize a cultivar `grades.json` for CI: per-task majority verdicts, the
with-skill-vs-baseline delta, and (on failure) the grader's reasoning + fix.

`grades.json` is a flat JSON list of records (one per task × variant × repeat),
each with at least: pass (bool), reasoning (str), suggestions ([{cause, fix}]),
task_id, runner, variant ("with-skill" | "without-skill" | "with-docs"), run_num.

Stdlib only — no third-party deps, so CI can run it with bare `python3`.

Usage:
    python3 check_grades.py <grades.json> [--md OUT.md] [--json OUT.json]
                            [--skill NAME] [--runner NAME]

Exit code:
    0  every with-skill task reached a majority PASS (or there was nothing to judge)
    1  at least one with-skill task reached a majority FAIL
    2  the grades file was missing or unreadable

The caller decides whether a non-zero exit blocks a merge (see report-gate job);
this script only reports the with-skill verdict.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

WITH_SKILL = "with-skill"
# Order variants deliberately so the delta table reads with-skill first.
VARIANT_ORDER = [WITH_SKILL, "without-skill", "with-docs"]


def load_grades(path: Path) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} is not a JSON list (got {type(data).__name__})")
    return data


def majority_pass(records: list[dict]) -> tuple[bool, int, int]:
    """Return (is_majority_pass, n_pass, n_total) for a set of repeat records."""
    total = len(records)
    passed = sum(1 for r in records if bool(r.get("pass")))
    # Strict majority of the repeats must pass.
    return (passed * 2 > total, passed, total)


def summarize(grades: list[dict]) -> dict:
    """Group by (task_id, variant) → majority verdict + repeat counts."""
    by_task_variant: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in grades:
        by_task_variant[(r.get("task_id", "?"), r.get("variant", "?"))].append(r)

    tasks: dict[str, dict] = {}
    for (task_id, variant), recs in by_task_variant.items():
        ok, n_pass, n_total = majority_pass(recs)
        tasks.setdefault(task_id, {})[variant] = {
            "pass": ok,
            "n_pass": n_pass,
            "n_total": n_total,
            # Keep the first failing record's grader notes for the report.
            "fail_record": next((r for r in recs if not bool(r.get("pass"))), None),
        }
    return tasks


def variant_cell(v: dict | None) -> str:
    if not v:
        return "—"
    mark = "✅" if v["pass"] else "❌"
    return f"{mark} {v['n_pass']}/{v['n_total']}"


def delta_cell(tdata: dict) -> str:
    """with-skill vs the best available baseline, as a short verdict."""
    ws = tdata.get(WITH_SKILL)
    if not ws:
        return "—"
    baselines = [tdata[b] for b in ("without-skill", "with-docs") if b in tdata]
    if not baselines:
        return "no baseline"
    ws_rate = ws["n_pass"] / ws["n_total"] if ws["n_total"] else 0
    base_rate = max(b["n_pass"] / b["n_total"] if b["n_total"] else 0 for b in baselines)
    if ws_rate > base_rate:
        return "▲ skill better"
    if ws_rate < base_rate:
        return "▼ skill worse"
    return "= no diff"


def build_markdown(tasks: dict, skill: str | None, runner: str | None) -> str:
    label = " · ".join(p for p in (skill, runner) if p)
    out: list[str] = []
    header = f"#### `{label}`" if label else "#### eval"
    out.append(header)

    if not tasks:
        out.append("\n_No graded tasks found._\n")
        return "\n".join(out)

    out.append("")
    out.append("| Task | with-skill | without-skill | with-docs | delta |")
    out.append("|---|---|---|---|---|")
    for task_id in sorted(tasks):
        t = tasks[task_id]
        out.append(
            f"| `{task_id}` | {variant_cell(t.get(WITH_SKILL))} "
            f"| {variant_cell(t.get('without-skill'))} "
            f"| {variant_cell(t.get('with-docs'))} | {delta_cell(t)} |"
        )

    # Failure detail: grader reasoning + remediation for with-skill FAILs.
    fails = [
        (tid, t[WITH_SKILL]["fail_record"])
        for tid, t in sorted(tasks.items())
        if t.get(WITH_SKILL) and not t[WITH_SKILL]["pass"] and t[WITH_SKILL].get("fail_record")
    ]
    for tid, rec in fails:
        out.append("")
        out.append(f"<details><summary>❌ <code>{tid}</code> — why it failed</summary>")
        out.append("")
        reasoning = (rec.get("reasoning") or "").strip()
        if reasoning:
            out.append(f"**Grader:** {reasoning}")
            out.append("")
        for s in rec.get("suggestions") or []:
            cause = (s.get("cause") or "").strip()
            fix = (s.get("fix") or "").strip()
            if cause and fix:
                out.append(f"- _{cause}_ → {fix}")
            elif fix:
                out.append(f"- {fix}")
        out.append("")
        out.append("</details>")
    out.append("")
    return "\n".join(out)


def build_scores(tasks: dict, skill: str | None, runner: str | None) -> list[dict]:
    """Flat rows for the weekly trend (date stamped by the caller)."""
    rows = []
    for task_id, t in sorted(tasks.items()):
        row = {"skill": skill, "runner": runner, "task_id": task_id}
        for variant in VARIANT_ORDER:
            v = t.get(variant)
            if v:
                row[variant] = round(v["n_pass"] / v["n_total"], 3) if v["n_total"] else None
        rows.append(row)
    return rows


def any_with_skill_fail(tasks: dict) -> bool:
    return any(
        t.get(WITH_SKILL) and not t[WITH_SKILL]["pass"] for t in tasks.values()
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Summarize cultivar grades.json for CI")
    ap.add_argument("grades", help="Path to grades.json")
    ap.add_argument("--md", help="Write a Markdown report fragment here")
    ap.add_argument("--json", dest="json_out", help="Write flat score rows here")
    ap.add_argument("--skill", help="Skill label for the report header")
    ap.add_argument("--runner", help="Runner label for the report header")
    args = ap.parse_args()

    path = Path(args.grades)
    if not path.exists():
        print(f"check_grades: grades file not found: {path}", file=sys.stderr)
        return 2
    try:
        grades = load_grades(path)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"check_grades: could not read {path}: {e}", file=sys.stderr)
        return 2

    # Infer labels from the records when not supplied.
    skill = args.skill
    runner = args.runner or (grades[0].get("runner") if grades else None)

    tasks = summarize(grades)

    md = build_markdown(tasks, skill, runner)
    if args.md:
        Path(args.md).write_text(md)
    else:
        print(md)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(build_scores(tasks, skill, runner), indent=2))

    failed = any_with_skill_fail(tasks)
    n_tasks = len(tasks)
    print(
        f"check_grades: {n_tasks} task(s); with-skill verdict: "
        f"{'FAIL' if failed else 'PASS'}",
        file=sys.stderr,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
