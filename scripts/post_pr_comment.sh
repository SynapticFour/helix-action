#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Upsert the PR comment whose body contains <!-- helix-verification -->.
# Missing gh, missing permissions, and fork-PR 403 do not fail the job.
set -euo pipefail
BODY_FILE="${1:?usage: post_pr_comment.sh BODY_FILE}"

if [[ ! -f "$BODY_FILE" ]]; then
  echo "Comment file missing (${BODY_FILE}); skip comment." >&2
  exit 0
fi
if [[ -z "${PR_NUMBER:-}" ]]; then
  echo "No PR_NUMBER; skip comment (push/dispatch)." >&2
  exit 0
fi
if [[ -z "${GITHUB_REPOSITORY:-}" ]]; then
  echo "GITHUB_REPOSITORY unset; skip comment." >&2
  exit 0
fi
if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not available; skip comment" >&2
  exit 0
fi
if [[ -z "${GH_TOKEN:-${GITHUB_TOKEN:-}}" ]]; then
  echo "No GH_TOKEN; skip comment" >&2
  exit 0
fi

MARKER="<!-- helix-verification -->"
CID="$(gh api "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments" --paginate \
  --jq ".[] | select(.body | contains(\"${MARKER}\")) | .id" | head -n 1 || true)"

PAYLOAD="$(python3 -c 'import json,sys; print(json.dumps({"body": open(sys.argv[1], encoding="utf-8").read()}))' "$BODY_FILE")"

post_ok=0
if [[ -n "$CID" ]]; then
  echo "Updating comment ${CID}" >&2
  if printf '%s' "$PAYLOAD" | gh api -X PATCH "repos/${GITHUB_REPOSITORY}/issues/comments/${CID}" --input -; then
    post_ok=1
  fi
else
  echo "Creating PR comment on #${PR_NUMBER}" >&2
  if printf '%s' "$PAYLOAD" | gh api -X POST "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments" --input -; then
    post_ok=1
  fi
fi

if [[ "$post_ok" -ne 1 ]]; then
  echo "Warning: could not write PR comment (403 on fork PRs, missing pull-requests:write, or API error). Not failing the job." >&2
  exit 0
fi
