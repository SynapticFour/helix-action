# Tokens and permissions (helix-action)

Helix-action is a **composite** GitHub Action. It builds a pinned `helix` CLI, runs `helix verify`, captures `VerificationRun` JSON, compares at stable check **id**, and may comment on a pull request.

It is **not** a required Ferrum check. It does **not** start servers. Results are **not** GA4GH certification. Not HELIOS.

This document is the security contract. Prefer the job `GITHUB_TOKEN` with the permissions below. **Never** pass a broad PAT (`repo`, `workflow`, `admin:org`, or classic `repo` scope) into this action unless you are cloning **private** Helix/HelixTest and then only as `source-token` with `contents:read`.

---

## What the action does with tokens

| Step | Token input | Why | Persisted? |
|------|-------------|-----|------------|
| Checkout `SynapticFour/Helix` | `source-token` if set, else the job `GITHUB_TOKEN` | `actions/checkout` default fetch | **No** (`persist-credentials: false`) |
| Checkout `SynapticFour/HelixTest` | same | sibling path dep (D1) | **No** |
| Download previous artifact | `github-token` (`GH_TOKEN`) | last **successful** run of **this workflow name** on the baseline branch | n/a (API) |
| Upsert PR comment | `github-token` (`GH_TOKEN`) | `<!-- helix-verification -->` | n/a (API) |

`github-token` is **not** passed into the Helix/HelixTest checkouts. That split exists so a comment/artifact token cannot linger in those worktrees.

The action never reads Ferrum JWTs, GHCR passwords, HELIOS signing keys, or HMAC secrets. Dummy HelixTest fixtures stay in Helix; this Action does not ship them.

---

## Caller workflow (required)

```yaml
permissions:
  contents: read          # your repo checkout; public Helix/HelixTest clone
  actions: read           # download the previous helix-verify-json artifact
  pull-requests: write    # post or update the PR comment
```

Do **not** add `contents: write`, `actions: write`, `workflows`, `security-events`, or `id-token` for this Action.

This repo’s own CI uses **`contents: read` only** (`run: false`, no comment, no baseline fetch).

---

## Inputs

### `github-token` (default `${{ github.token }}`)

The **job token**, not a PAT. Used only by `gh` for:

1. `actions: read` — `gh run list` / `gh run download` of the baseline artifact
2. `pull-requests: write` — create or PATCH the PR comment

Fork PRs from outsiders often **cannot** comment (`403`). The Action **warns and exits 0**. That is a GitHub limitation, not a Helix secret.

If `gh` or the token is missing, baseline fetch and comments are skipped. **The job does not fail** for that (infrastructure).

### `source-token` (default empty)

Only when Helix and/or HelixTest are **private** to the caller. Grant **`contents: read`** on those two repositories. Leave empty for the public GitHub clones.

Do not reuse a user PAT that can push, change workflows, or read other private repos.

Checkout uses `persist-credentials: false`, so even `source-token` is not left in `.git` for later steps.

---

## What can fail the job

| Event | Job result |
|-------|------------|
| `NEW_FAIL` (previous **pass**, current **fail** or **error** at a stable Helix `id`) | **Fail** if `fail-on-regression: true` (default) |
| `helix verify` exit **>1**, missing binary, JSON that is not a `VerificationRun` | **Fail** (runtime) |
| Known failures (`UNCHANGED_FAIL`) | Green |
| Skips, SKIP→PASS (`FIXED_SKIP`) | Green |
| `summary.passed` dropped because a pass became skip | Green |
| No baseline / first run | Green |
| Previous artifact is HelixTest `OverallReport` (stale) | Green; this run re-baselines |
| All executed rows `error` + message contains `unreachable` | Green (infrastructure) |
| Bench threshold warning or `helix bench` missing/crash | Green |
| PR comment 403 / `gh` missing | Green |

A single X/Y score is **not** a signal and is not an action output.

---

## Artifacts

The current `helix-verify.json` (and optional `helix-bench.json`) upload under `artifact-name` (default `helix-verify-json`). Anyone with `actions: read` on the **caller** repo can download them. Do not put secrets in verify JSON. Helix verify JSON is a `VerificationRun` (ids, statuses, optional dummy-fixture messages) — not an evidence pack.

---

## Supply chain notes

- Pin **this Action** at a commit SHA (`uses: SynapticFour/helix-action@<sha>`).
- Pin **Helix** at a SHA that emits `VerificationRun` and includes `helix compare`. There is **no Helix release tag** yet. The default `helix-ref: main` is a development fallback and logs a warning.
- Pin **HelixTest** at SHA `1832c043e1679ec283cb2113510ee33684317cce` (tag `v0.1.3`), same as Helix/Ferrum `VERSIONS.lock`.
- Rust toolchain is **1.91.1** (same as Helix `rust-toolchain.toml`).
- The Action builds `helix` from source on the runner. That compiles HelixTest crates (including crypt4gh). It does not pull Ferrum images.

---

## Fork and `pull_request` from a fork

`pull_request` from a fork gets a read-only job token. `actions: read` on the **base** repo’s Actions artifacts usually works for public repos. `pull-requests: write` often does **not**. Comment upsert then no-ops. Compare still runs.

Do not switch the caller to `pull_request_target` to “fix” comments. That would run untrusted PR code with a write token.

---

## Out of scope

- Required status check on Ferrum `main`
- HELIOS signing / OIDC to an evidence store
- Minting production JWTs
- Storing a GitHub PAT in this repository
