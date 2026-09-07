#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare two helix verify VerificationRun JSON files at stable check id.

Regression = NEW_FAIL (previous pass, current fail or error).
Skip is never pass. SKIP→PASS is FIXED_SKIP, never UNCHANGED_PASS.
Known failures (UNCHANGED_FAIL) are not regressions.
Not a score drop. Not GA4GH certification. Not HELIOS evidence.

This script does not parse HelixTest OverallReport (services[]). That shape is
helix security / pre-freeze helix verify JSON, not the current verify contract
(schema_version helix-verification-v1, executed[] / skipped[]).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "helix-verification-v1"
BLOCKING = frozenset({"fail", "error"})
EXECUTED = frozenset({"pass", "fail", "error"})


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"{path} is not readable JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    return data


def is_verification_run(data: dict[str, Any]) -> bool:
    if not isinstance(data.get("executed"), list) or not isinstance(
        data.get("skipped"), list
    ):
        return False
    sv = data.get("schema_version")
    if sv is None:
        # Helix SCHEMA.md: files produced before the freeze omit it; Helix
        # deserializes missing as helix-verification-v1. Do not treat that as
        # OverallReport.
        return True
    return sv == SCHEMA_VERSION


def is_overall_report(data: dict[str, Any]) -> bool:
    return "services" in data and not is_verification_run(data)


def shape_error(path: Path, data: dict[str, Any]) -> str:
    if is_overall_report(data):
        return (
            f"{path} is HelixTest OverallReport (services[]). "
            "helix verify JSON is Helix VerificationRun "
            f"(schema_version {SCHEMA_VERSION}, executed[]/skipped[]). "
            "This action no longer compares OverallReport. "
            "helix security still emits OverallReport — that is a different CLI."
        )
    sv = data.get("schema_version")
    if sv is not None and sv != SCHEMA_VERSION:
        return (
            f"{path} has schema_version {sv!r}; "
            f"this action compares {SCHEMA_VERSION} only "
            "(VerificationRun executed[]/skipped[])."
        )
    return (
        f"{path} is not a Helix VerificationRun "
        f"(need executed[] and skipped[] lists; schema_version {SCHEMA_VERSION} "
        "when present). Not HelixTest OverallReport, not HELIOS."
    )


def load_report(path: Path) -> dict[str, Any]:
    """Load VerificationRun JSON. Raises ValueError on OverallReport or unknown shape."""
    data = load_json(path)
    if not is_verification_run(data):
        raise ValueError(shape_error(path, data))
    return data


def try_load_json(path: Path) -> dict[str, Any] | None:
    """Best-effort load for a baseline artifact. Corrupt previous is infra, not a fail."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


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
    """Same table as Helix `compare::classify` / docs/REGRESSION.md."""
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
        return _report("", _target_url(current), rows)

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
    return _report(_target_url(previous), _target_url(current), rows)


def _target_url(run: dict[str, Any]) -> str:
    target = run.get("target") or {}
    if isinstance(target, dict):
        return str(target.get("url") or "")
    return ""


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


def executed_score(run: dict[str, Any] | None) -> tuple[int, int]:
    """Executed pass count / executed total (pass+fail+error). Skips omitted."""
    if not run:
        return (0, 0)
    passed = total = 0
    for row in run.get("executed") or []:
        if not isinstance(row, dict):
            continue
        st = str(row.get("status") or "").lower()
        if st not in EXECUTED:
            continue
        total += 1
        if st == "pass":
            passed += 1
    return passed, total


def regressions(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    report = compare_runs(previous, current)
    return [r for r in report["rows"] if r.get("kind") == "NEW_FAIL"]


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

    skip_pass = [r for r in report.get("rows") or [] if r.get("skip_became_pass")]
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
        "Job fails only on new regressions (PASS → FAIL/ERROR at stable Helix id). "
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


def load_bench(path: Path) -> dict[str, Any]:
    data = load_json(path)
    if "warning" not in data or "diff" not in data:
        raise ValueError(f"{path} is not a Helix BenchOutcome (missing warning/diff)")
    return data


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


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--current", required=True, type=Path)
    p.add_argument("--previous", type=Path, default=None)
    p.add_argument("--comment-out", type=Path, default=None)
    p.add_argument("--github-output", type=Path, default=None)
    p.add_argument(
        "--bench-json",
        type=Path,
        default=None,
        help="Optional helix bench JSON. Appended to the comment; never changes the exit code.",
    )
    args = p.parse_args(argv)

    notes: list[str] = []
    try:
        current = load_report(args.current)
    except ValueError as e:
        die(str(e), 2)

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
            notes.append(
                "Previous artifact is not a Helix VerificationRun; ignored "
                f"({shape_error(args.previous, prev_data)}). This run becomes the new baseline."
            )

    if previous is None:
        notes.append(
            "No previous VerificationRun on the baseline branch — nothing to regress against."
        )

    report = compare_runs(previous, current)

    bench = None
    if args.bench_json is not None:
        try:
            bench = load_bench(args.bench_json)
        except ValueError as e:
            die(str(e), 2)

    comment = render_comment(report, bench=bench, notes=notes)
    if args.comment_out:
        args.comment_out.write_text(comment, encoding="utf-8")
    print(headline(report))

    regs = [r for r in report["rows"] if r.get("kind") == "NEW_FAIL"]
    if args.github_output:
        go = args.github_output
        with go.open("a", encoding="utf-8") as fh:
            fh.write(f"has_previous={'true' if previous is not None else 'false'}\n")
            fh.write(f"regression={'true' if regs else 'false'}\n")
            fh.write(f"regression_count={len(regs)}\n")
            px, py = executed_score(previous)
            cx, cy = executed_score(current)
            fh.write(f"previous_score={px}/{py}\n")
            fh.write(f"current_score={cx}/{cy}\n")
            s = report.get("summary") or {}
            fh.write(f"new_fail={int(s.get('new_fail') or 0)}\n")
            fh.write(f"fixed={int(s.get('fixed') or 0)}\n")
            fh.write(f"unchanged_fail={int(s.get('unchanged_fail') or 0)}\n")
            if bench is not None:
                fh.write(
                    f"bench_warning={'true' if bench.get('warning') else 'false'}\n"
                )

    return 1 if regs else 0


if __name__ == "__main__":
    sys.exit(main())
