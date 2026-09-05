#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare Helix VerificationRun JSON at stable check id.

Regression = NEW_FAIL (previous pass, current fail or error).
Not a score drop. Skip is never pass. SKIP→PASS is FIXED_SKIP.
Known failures (UNCHANGED_FAIL) are not regressions.
Not GA4GH certification. Not HELIOS evidence.

Mirrors Helix `src/compare.rs` / `docs/REGRESSION.md` so this repo's CI can
test comments without compiling Helix. The GitHub Action prefers
`helix compare --format json` when the pinned CLI has that subcommand.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BLOCKING = frozenset({"fail", "error"})
EXECUTED = frozenset({"pass", "fail", "error"})


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        die(f"{path} is not readable JSON: {e}", 2)
    if not isinstance(data, dict):
        die(f"{path} is not a JSON object", 2)
    return data


def try_load_json(path: Path) -> dict[str, Any] | None:
    """Best-effort load for a baseline artifact. Corrupt previous is infra, not a fail."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def is_verification_run(data: dict[str, Any]) -> bool:
    return isinstance(data.get("executed"), list) and isinstance(
        data.get("skipped"), list
    )


def is_overall_report(data: dict[str, Any]) -> bool:
    return "services" in data and not is_verification_run(data)


def is_compare_report(data: dict[str, Any]) -> bool:
    return "has_regression" in data and isinstance(data.get("rows"), list)


def is_bench_outcome(data: dict[str, Any]) -> bool:
    return "warning" in data and "diff" in data


def iter_results(run: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for key in ("executed", "skipped"):
        for row in run.get(key) or []:
            if isinstance(row, dict) and row.get("id"):
                out.append(row)
    return out


def index_by_id(run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for row in iter_results(run):
        i = str(row["id"])
        if i in idx:
            raise ValueError(f"duplicate check id `{i}`")
        idx[i] = row
    return idx


def classify(previous: str | None, current: str | None) -> str:
    """Same table as Helix `compare::classify`."""
    prev = (previous or "").lower() or None
    curr = (current or "").lower() or None
    if prev == "pass" and curr == "pass":
        return "UNCHANGED_PASS"
    if prev == "pass" and curr in BLOCKING:
        return "NEW_FAIL"
    if prev == "pass" and curr in (None, "skip"):
        return "NEW_SKIP"
    if prev in BLOCKING and curr == "pass":
        return "FIXED"
    if prev in BLOCKING and curr in BLOCKING:
        return "UNCHANGED_FAIL"
    if prev in BLOCKING and curr in (None, "skip"):
        return "NEW_SKIP"
    if prev == "skip" and curr in EXECUTED:
        return "FIXED_SKIP"
    if prev == "skip" and curr in (None, "skip"):
        return "UNCHANGED_SKIP"
    if prev is None:
        return "ADDED"
    return "ADDED"


def compare_runs(
    previous: dict[str, Any] | None, current: dict[str, Any]
) -> dict[str, Any]:
    if previous is None:
        rows: list[dict[str, Any]] = []
        for row in iter_results(current):
            st = str(row.get("status") or "").lower()
            rows.append(
                {
                    "id": row["id"],
                    "code": row.get("code") or "",
                    "kind": "ADDED",
                    "previous": None,
                    "current": st,
                    "regression": False,
                    "skip_became_pass": False,
                }
            )
        rows.sort(key=lambda r: r["id"])
        return _report("", current.get("target", {}).get("url", ""), rows)

    prev_idx = index_by_id(previous)
    curr_idx = index_by_id(current)
    ids = sorted(set(prev_idx) | set(curr_idx))
    rows = []
    for i in ids:
        prev = prev_idx.get(i)
        curr = curr_idx.get(i)
        prev_st = str(prev["status"]).lower() if prev else None
        curr_st = str(curr["status"]).lower() if curr else None
        kind = classify(prev_st, curr_st)
        src = curr or prev or {}
        skip_became_pass = prev_st == "skip" and curr_st == "pass"
        rows.append(
            {
                "id": i,
                "code": src.get("code") or "",
                "kind": kind,
                "previous": prev_st,
                "current": curr_st,
                "regression": kind == "NEW_FAIL",
                "skip_became_pass": skip_became_pass,
            }
        )
    prev_url = previous.get("target", {}).get("url", "")
    curr_url = current.get("target", {}).get("url", "")
    return _report(prev_url, curr_url, rows)


def _report(prev_url: str, curr_url: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "new_fail": 0,
        "fixed": 0,
        "unchanged_fail": 0,
        "unchanged_pass": 0,
        "new_skip": 0,
        "fixed_skip": 0,
        "unchanged_skip": 0,
        "added": 0,
        "skip_became_pass": 0,
    }
    key = {
        "NEW_FAIL": "new_fail",
        "FIXED": "fixed",
        "UNCHANGED_FAIL": "unchanged_fail",
        "UNCHANGED_PASS": "unchanged_pass",
        "NEW_SKIP": "new_skip",
        "FIXED_SKIP": "fixed_skip",
        "UNCHANGED_SKIP": "unchanged_skip",
        "ADDED": "added",
    }
    for row in rows:
        summary[key[row["kind"]]] += 1
        if row.get("skip_became_pass"):
            summary["skip_became_pass"] += 1
    return {
        "helix_version": "action",
        "previous_target": prev_url,
        "current_target": curr_url,
        "has_regression": summary["new_fail"] > 0,
        "summary": summary,
        "rows": rows,
    }


def all_unreachable(run: dict[str, Any]) -> bool:
    """True when every executed row is error mentioning unreachable (infra)."""
    executed = [r for r in (run.get("executed") or []) if isinstance(r, dict)]
    if not executed:
        return False
    for row in executed:
        if str(row.get("status") or "").lower() != "error":
            return False
        msg = str(row.get("message") or "").lower()
        if "unreachable" not in msg:
            return False
    return True


def render_comment(
    report: dict[str, Any],
    *,
    bench: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> str:
    s = report.get("summary") or {}
    new_fail = int(s.get("new_fail") or 0)
    fixed = int(s.get("fixed") or 0)
    existing = int(s.get("unchanged_fail") or 0)
    lines = [
        "<!-- helix-verification -->",
        "# Helix verification",
        "",
        "Stable check **id** (not a score). Ferrum is a reference target, not a dependency. "
        "Not GA4GH certification. Skips are not passes. Not HELIOS.",
        "",
        f"**New regressions:** {new_fail}  ",
        f"**Fixed failures:** {fixed}  ",
        f"**Existing failures:** {existing}",
        "",
    ]
    if new_fail:
        lines += ["## New regressions", ""]
        for row in report.get("rows") or []:
            if row.get("kind") != "NEW_FAIL":
                continue
            lines.append(_row_line(row))
        lines.append("")
    else:
        lines += ["_No new regressions (PASS → FAIL/ERROR at stable id)._", ""]

    lines += ["## Fixed failures", ""]
    fixed_rows = [r for r in report.get("rows") or [] if r.get("kind") == "FIXED"]
    if fixed_rows:
        for row in fixed_rows:
            lines.append(_row_line(row))
    else:
        lines.append("_None._")
    lines.append("")

    lines += ["## Existing failures", ""]
    exist_rows = [
        r for r in report.get("rows") or [] if r.get("kind") == "UNCHANGED_FAIL"
    ]
    if exist_rows:
        for row in exist_rows:
            lines.append(_row_line(row))
    else:
        lines.append("_None._")
    lines.append("")

    skip_pass = [
        r for r in report.get("rows") or [] if r.get("skip_became_pass")
    ]
    if skip_pass:
        lines += [
            "## SKIP became PASS",
            "",
            "Not a silent pass (`FIXED_SKIP`, never `UNCHANGED_PASS`).",
            "",
        ]
        for row in skip_pass:
            lines.append(_row_line(row))
        lines.append("")

    if notes:
        lines += ["## Notes", ""]
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")

    if bench is not None:
        lines.extend(render_bench_section(bench))

    lines.append(
        "Job fails only on new regressions or explicit runtime errors. "
        "Known failures, skips, and bench warnings do not fail the job. "
        "Not a required Ferrum check."
    )
    return "\n".join(lines) + "\n"


def _row_line(row: dict[str, Any]) -> str:
    prev = row.get("previous") or "absent"
    curr = row.get("current") or "absent"
    code = row.get("code") or ""
    ident = row.get("id") or ""
    extra = f" (`{code}`)" if code else ""
    return f"- `{ident}`{extra} {prev} → {curr}"


def _fmt_pct(pct: Any) -> str:
    if pct is None:
        return "n/a"
    try:
        return f"{float(pct):+.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def render_bench_section(bench: dict[str, Any]) -> list[str]:
    threshold = bench.get("threshold_pct", 10)
    baseline = bench.get("baseline") or {}
    candidate = bench.get("candidate") or {}
    lines = [
        "## Helix bench (warn only — does not fail this job)",
        "",
        "3 small GETs (not Demo hap.py / GIAB, not HELIOS). "
        f"Threshold {threshold}%. Performance noise is expected; humans decide.",
        "",
        f"- Baseline **{baseline.get('label', 'baseline')}** "
        f"wall_ms={baseline.get('wall_ms', 'n/a')} "
        f"error_rate={baseline.get('error_rate', 'n/a')}",
        f"- Candidate **{candidate.get('label', 'candidate')}** "
        f"wall_ms={candidate.get('wall_ms', 'n/a')} "
        f"error_rate={candidate.get('error_rate', 'n/a')}",
    ]
    diffs = bench.get("diff") or []
    if diffs:
        lines += ["", "| Metric | Change |"]
        lines.append("|---|---|")
        for d in diffs:
            name = d.get("name", "")
            mark = " WARN" if d.get("worse") else ""
            lines.append(f"| {name} | {_fmt_pct(d.get('pct'))}{mark} |")
    if bench.get("warning"):
        lines += ["", "**Warnings (not a red X)**"]
        for w in bench.get("warnings") or []:
            lines.append(f"- {w}")
    else:
        lines += ["", "_No metric exceeded the warning threshold._"]
    lines.append("")
    return lines


def headline(report: dict[str, Any]) -> str:
    s = report.get("summary") or {}
    return (
        f"Helix verification — new regressions: {s.get('new_fail', 0)}; "
        f"fixed: {s.get('fixed', 0)}; existing failures: {s.get('unchanged_fail', 0)}"
    )


def write_github_output(
    path: Path,
    report: dict[str, Any],
    bench: dict[str, Any] | None,
    *,
    job_regression: bool,
    infra_unreachable: bool,
) -> None:
    s = report.get("summary") or {}
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"regression={'true' if job_regression else 'false'}\n")
        fh.write(f"new_fail={int(s.get('new_fail') or 0)}\n")
        fh.write(f"fixed={int(s.get('fixed') or 0)}\n")
        fh.write(f"unchanged_fail={int(s.get('unchanged_fail') or 0)}\n")
        fh.write(f"infra_unreachable={'true' if infra_unreachable else 'false'}\n")
        fh.write(
            f"bench_warning={'true' if bench is not None and bench.get('warning') else 'false'}\n"
        )


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--current", type=Path, default=None)
    p.add_argument("--previous", type=Path, default=None)
    p.add_argument(
        "--compare-json",
        type=Path,
        default=None,
        help="Precomputed helix compare JSON (preferred).",
    )
    p.add_argument("--comment-out", type=Path, default=None)
    p.add_argument("--github-output", type=Path, default=None)
    p.add_argument("--bench-json", type=Path, default=None)
    p.add_argument(
        "--note",
        action="append",
        default=[],
        help="Extra comment note (repeatable). Used by the Action wrapper.",
    )
    args = p.parse_args(argv)

    notes: list[str] = list(args.note)
    report: dict[str, Any]
    current: dict[str, Any] | None = None

    if args.current is not None:
        current = load_json(args.current)
        if is_overall_report(current):
            die(
                f"{args.current} is HelixTest OverallReport; "
                "helix-action needs helix verify VerificationRun JSON"
            )
        if not is_verification_run(current):
            die(f"{args.current} is not a Helix VerificationRun")

    if args.compare_json is not None:
        report = load_json(args.compare_json)
        if not is_compare_report(report):
            die(f"{args.compare_json} is not a Helix CompareReport")
    else:
        if current is None:
            die("--current or --compare-json is required")

        previous = None
        if args.previous is not None and args.previous.is_file():
            prev_data = try_load_json(args.previous)
            if prev_data is None:
                notes.append(
                    "Previous artifact is not readable JSON; ignored "
                    "(infrastructure). This run becomes the new baseline."
                )
            elif is_overall_report(prev_data):
                notes.append(
                    "Previous artifact is HelixTest OverallReport; ignored "
                    "(not comparable at stable Helix id). This run becomes the new baseline."
                )
            elif is_verification_run(prev_data):
                previous = prev_data
            else:
                notes.append("Previous artifact is not a VerificationRun; ignored.")

        if previous is None and not any("No previous VerificationRun" in n for n in notes):
            notes.append(
                "No previous VerificationRun on the baseline branch — nothing to regress against."
            )

        report = compare_runs(previous, current)

    bench = None
    if args.bench_json is not None:
        bench = load_json(args.bench_json)
        if not is_bench_outcome(bench):
            die(f"{args.bench_json} is not a Helix BenchOutcome")

    infra = bool(current is not None and all_unreachable(current))
    if infra:
        notes.insert(
            0,
            "All executed checks are ERROR unreachable. Treated as infrastructure "
            "(stack not reachable from the runner), not a job-failing verification regression.",
        )

    comment = render_comment(report, bench=bench, notes=notes)
    if args.comment_out:
        args.comment_out.write_text(comment, encoding="utf-8")
    print(headline(report))

    # Job-failing regression = NEW_FAIL, except clearly identified unreachable infra.
    job_regression = bool(report.get("has_regression")) and not infra
    if args.github_output:
        write_github_output(
            args.github_output,
            report,
            bench,
            job_regression=job_regression,
            infra_unreachable=infra,
        )

    # Exit 1 only on NEW_FAIL that is not unreachable infra.
    # Bench, skips, existing fails, missing/stale baseline: 0. Bad JSON: 2.
    return 1 if job_regression else 0


if __name__ == "__main__":
    sys.exit(main())
