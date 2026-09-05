#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Download helix-verify.json from the last successful run of this workflow on BASELINE_BRANCH.
# Missing gh, token, or artifact is infrastructure: never fail the job.
set -euo pipefail
OUT_DIR="${1:?usage: fetch_baseline.sh OUT_DIR}"
mkdir -p "$OUT_DIR"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not available; no baseline" >&2
  exit 0
fi
if [[ -z "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ]]; then
  echo "No GH_TOKEN; no baseline" >&2
  exit 0
fi

BRANCH="${BASELINE_BRANCH:-main}"
NAME="${ARTIFACT_NAME:-helix-verify-json}"
WORKFLOW="${WORKFLOW_NAME:-}"

if [[ -z "$WORKFLOW" ]]; then
  echo "WORKFLOW_NAME empty; no baseline" >&2
  exit 0
fi

RID="$(gh run list \
  --workflow "$WORKFLOW" \
  --branch "$BRANCH" \
  --status success \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId // empty' || true)"

if [[ -z "$RID" ]]; then
  echo "No successful '$WORKFLOW' run on branch '$BRANCH'" >&2
  exit 0
fi

echo "Baseline GitHub Actions run: ${RID} (branch ${BRANCH})" >&2
if ! gh run download "$RID" --name "$NAME" --dir "$OUT_DIR"; then
  echo "Run ${RID} has no artifact named ${NAME}" >&2
  exit 0
fi
find "$OUT_DIR" -type f -name '*.json' >&2 || true
