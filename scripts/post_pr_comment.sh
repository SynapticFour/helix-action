#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Upsert the PR comment whose body contains <!-- helix-verification -->.
set -euo pipefail
BODY_FILE="${1:?usage: post_pr_comment.sh BODY_FILE}"

if [[ -z "${PR_NUMBER:-}" ]]; then
  echo "No PR_NUMBER; skip comment (push/dispatch)." >&2
  exit 0
fi
if [[ -z "${GITHUB_REPOSITORY:-}" ]]; then
  echo "GITHUB_REPOSITORY unset" >&2
  exit 1
fi
if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not available; skip comment" >&2
  exit 0
fi

MARKER="<!-- helix-verification -->"
CID="$(gh api "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments" --paginate \
  --jq ".[] | select(.body | contains(\"${MARKER}\")) | .id" | head -n 1 || true)"

PAYLOAD="$(python3 -c 'import json,sys; print(json.dumps({"body": open(sys.argv[1], encoding="utf-8").read()}))' "$BODY_FILE")"

if [[ -n "$CID" ]]; then
  echo "Updating comment ${CID}" >&2
  printf '%s' "$PAYLOAD" | gh api -X PATCH "repos/${GITHUB_REPOSITORY}/issues/comments/${CID}" --input -
else
  echo "Creating PR comment on #${PR_NUMBER}" >&2
  printf '%s' "$PAYLOAD" | gh api -X POST "repos/${GITHUB_REPOSITORY}/issues/${PR_NUMBER}/comments" --input -
fi
