#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare two Helix / HelixTest OverallReport JSON files.

Regression = a check that was status=pass previously and status=fail now.
Skip is never pass. Known FAILs (fail→fail) are not regressions.
Not GA4GH certification. Not HELIOS evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

API_ORDER = ("Drs", "Wes", "Tes", "Trs", "Htsget", "Beacon", "Auth")
API_LABEL = {
    "Drs": "DRS",
    "Wes": "WES",
    "Tes": "TES",
    "Trs": "TRS",
    "Htsget": "htsget",
    "Beacon": "Beacon",
    "Auth": "Auth",
    "Age": "Age",
    "Crypt4gh": "Crypt4GH",
    "E2e": "E2E",
    "Africa": "Africa",
    "Infra": "Infra",
}

EXECUTED = {"pass", "fail"}


def load_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "services" not in data:
        raise ValueError(f"{path} is not a HelixTest OverallReport (missing services)")
    return data


def _service_name(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    return str(raw)


def iter_tests(report: dict[str, Any]) -> Iterable[tuple[str, str, str]]:
    for svc in report.get("services") or []:
        service = _service_name(svc.get("service", ""))
        for t in svc.get("tests") or []:
            name = str(t.get("name") or "")
            status = str(t.get("status") or "").lower()
            if not name:
                continue
            yield service, name, status


def test_index(report: dict[str, Any]) -> dict[tuple[str, str], str]:
    return {(s, n): st for s, n, st in iter_tests(report)}


def score(report: dict[str, Any] | None) -> tuple[int, int]:
    if not report:
        return (0, 0)
    passed = failed = 0
    for _s, _n, status in iter_tests(report):
        if status == "pass":
            passed += 1
        elif status == "fail":
            failed += 1
    return passed, passed + failed


def service_verdict(report: dict[str, Any], service: str) -> str:
    tests = [
        st
        for s, _n, st in iter_tests(report)
        if s == service
    ]
    executed = [st for st in tests if st in EXECUTED]
    if executed:
        return "FAIL" if any(st == "fail" for st in executed) else "PASS"
    for skipped in report.get("skipped_services") or []:
        if _service_name(skipped.get("service")) == service:
            return "SKIP"
    if tests:
        return "SKIP"
    return "SKIP"


def api_list(report: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    for svc in report.get("services") or []:
        name = _service_name(svc.get("service", ""))
        if name and name not in seen:
            seen.append(name)
    for skipped in report.get("skipped_services") or []:
        name = _service_name(skipped.get("service"))
        if name and name not in seen:
            seen.append(name)

    def sort_key(name: str) -> tuple[int, str]:
        try:
            return (API_ORDER.index(name), name)
        except ValueError:
            return (len(API_ORDER), name)

    seen.sort(key=sort_key)
    parts = []
    for name in seen:
        label = API_LABEL.get(name, name.upper() if name else name)
        parts.append(f"{label}: {service_verdict(report, name)}")
    return parts


def regressions(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, str]]:
    if previous is None:
        return []
    prev = test_index(previous)
    cur = test_index(current)
    out = []
    for key, prev_status in prev.items():
        if prev_status != "pass":
            continue
        now = cur.get(key)
        if now == "fail":
            service, name = key
            out.append(
                {
                    "service": API_LABEL.get(service, service),
                    "name": name,
                    "previous": prev_status,
                    "current": now,
                }
            )
    out.sort(key=lambda r: (r["service"], r["name"]))
    return out


def comment_line(previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    px, py = score(previous)
    cx, cy = score(current)
    prev_s = "n/a" if previous is None else f"{px}/{py}"
    apis = ", ".join(api_list(current)) or "(no APIs)"
    return f"Helix Verification — Previous: {prev_s} | Current: {cx}/{cy} | {apis}"


def render_comment(previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    regs = regressions(previous, current)
    lines = [
        "<!-- helix-verification -->",
        comment_line(previous, current),
        "",
        "Helix tests behavior against the GA4GH spec, independent of implementation. "
        "Ferrum is used as a reference target, not a dependency. Not GA4GH certification. "
        "The job fails only on real regressions (PASS → FAIL), not on already-known FAILs. "
        "Skips are not passes. Not HELIOS.",
    ]
    if previous is None:
        lines += ["", "_No previous successful run on the baseline branch — nothing to regress against._"]
    if regs:
        lines += ["", "**Regressions (PASS → FAIL)**"]
        for r in regs:
            lines.append(f"- {r['service']} / {r['name']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--current", required=True, type=Path)
    p.add_argument("--previous", type=Path, default=None)
    p.add_argument("--comment-out", type=Path, default=None)
    p.add_argument("--github-output", type=Path, default=None)
    args = p.parse_args(argv)

    current = load_report(args.current)
    previous = None
    if args.previous is not None and args.previous.is_file():
        previous = load_report(args.previous)

    regs = regressions(previous, current)
    comment = render_comment(previous, current)
    if args.comment_out:
        args.comment_out.write_text(comment, encoding="utf-8")
    print(comment_line(previous, current))

    if args.github_output:
        go = args.github_output
        with go.open("a", encoding="utf-8") as fh:
            fh.write(f"has_previous={'true' if previous is not None else 'false'}\n")
            fh.write(f"regression={'true' if regs else 'false'}\n")
            fh.write(f"regression_count={len(regs)}\n")
            px, py = score(previous)
            cx, cy = score(current)
            fh.write(f"previous_score={px}/{py}\n")
            fh.write(f"current_score={cx}/{cy}\n")

    return 1 if regs else 0


if __name__ == "__main__":
    sys.exit(main())
