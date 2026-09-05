#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Prefer `helix compare --format json` when the pinned CLI has it; otherwise
# classify with compare_reports.py (mirrors Helix src/compare.rs).
#
# Exit 0: no job-failing regression
# Exit 1: NEW_FAIL (PASS → FAIL/ERROR at stable id)
# Exit 2+: runtime (unreadable current JSON, usage, missing helix)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPARE_PY="${SCRIPT_DIR}/compare_reports.py"

CURRENT="${HELIX_VERIFY_JSON:?HELIX_VERIFY_JSON is required}"
COMMENT="${HELIX_COMMENT_FILE:?HELIX_COMMENT_FILE is required}"
GITHUB_OUTPUT_PATH="${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"

if [[ ! -f "$CURRENT" ]]; then
  echo "current VerificationRun missing: ${CURRENT}" >&2
  exit 2
fi

if [[ -z "${HELIX:-}" || ! -x "${HELIX}" ]]; then
  if [[ -n "${HELIX:-}" && -f "${HELIX}" ]]; then
    chmod +x "$HELIX" || true
  fi
fi

args=(
  --current "$CURRENT"
  --comment-out "$COMMENT"
  --github-output "$GITHUB_OUTPUT_PATH"
)

if [[ -n "${HELIX_VERIFY_PREVIOUS:-}" && -f "${HELIX_VERIFY_PREVIOUS}" ]]; then
  args+=(--previous "${HELIX_VERIFY_PREVIOUS}")
fi
if [[ -n "${HELIX_BENCH_JSON:-}" && -f "${HELIX_BENCH_JSON}" ]]; then
  args+=(--bench-json "${HELIX_BENCH_JSON}")
fi

COMPARE_JSON="${RUNNER_TEMP:-/tmp}/helix-compare.json"
used_helix_compare=0

if [[ -n "${HELIX_VERIFY_PREVIOUS:-}" && -f "${HELIX_VERIFY_PREVIOUS}" && -n "${HELIX:-}" ]]; then
  if "$HELIX" compare --help >/dev/null 2>&1; then
    # Only feed helix compare when previous is a VerificationRun. OverallReport
    # is stale baseline / infra — Python will ignore it without failing.
    if python3 -c '
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
ok = isinstance(p.get("executed"), list) and isinstance(p.get("skipped"), list)
sys.exit(0 if ok else 1)
' "${HELIX_VERIFY_PREVIOUS}"; then
      set +e
      "$HELIX" compare "${HELIX_VERIFY_PREVIOUS}" "$CURRENT" --format json \
        >"$COMPARE_JSON" 2>"${COMPARE_JSON}.stderr"
      hx_ec=$?
      set -e
      if [[ "$hx_ec" -eq 2 ]]; then
        echo "helix compare usage error (exit 2)" >&2
        cat "${COMPARE_JSON}.stderr" >&2 || true
        exit 2
      fi
      if python3 -c '
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
ok = "has_regression" in d and isinstance(d.get("rows"), list)
sys.exit(0 if ok else 1)
' "$COMPARE_JSON"; then
        args+=(--compare-json "$COMPARE_JSON")
        used_helix_compare=1
        args+=(--note "Classified with \`helix compare\` (pinned CLI).")
      else
        echo "helix compare did not emit CompareReport; falling back to compare_reports.py" >&2
        cat "${COMPARE_JSON}.stderr" >&2 || true
        # Unreadable current as VerificationRun is a runtime error (helix exit 1, no JSON).
        if ! python3 -c '
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
ok = isinstance(d.get("executed"), list) and isinstance(d.get("skipped"), list)
sys.exit(0 if ok else 1)
' "$CURRENT"; then
          echo "current JSON is not a Helix VerificationRun" >&2
          exit 2
        fi
      fi
    else
      args+=(--note "Previous artifact is not a VerificationRun; \`helix compare\` skipped.")
    fi
  else
    echo "pinned helix has no compare subcommand; using compare_reports.py" >&2
    args+=(--note "Pinned helix has no \`compare\` yet; classified with compare_reports.py (same table as Helix docs/REGRESSION.md).")
  fi
fi

set +e
python3 "$COMPARE_PY" "${args[@]}"
ec=$?
set -e
if [[ "$ec" -gt 1 ]]; then
  exit "$ec"
fi
echo "HELIX_USED_COMPARE=${used_helix_compare}" >> "${GITHUB_ENV:-/dev/null}"
exit "$ec"
