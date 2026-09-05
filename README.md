# helix-action

Freeze status (2026-09): [STATUS.md](STATUS.md).


GitHub Action wrapper around **`helix verify`** ([Helix](https://github.com/SynapticFour/Helix) / HelixTest heritage). Apache-2.0. **Not a product SKU.** Parallel to [helixtest-action](https://github.com/SynapticFour/helixtest-action); this one posts a PR score comment and fails **only** on regressions (PASS → FAIL).

The action **does not start Ferrum**. Point `endpoint` at a stack you already brought up in the job. Results are **not** official GA4GH certification. Skips are not passes. Not HELIOS (no RO-Crate / PDF / signatures).

HelixTest stays a **separate git root**. This action checks out Helix and HelixTest as siblings to build the CLI (Helix `Cargo.toml` path-depends on `../HelixTest`). Do not merge HelixTest into Helix for this Action to work.

## Pin

Until this repo has a tag, pin the action at a **commit SHA**.

| What | Default |
|------|---------|
| Helix source | `helix-ref`: `26a3209bdbde8ea48d9e6024658fdfb8213d7258` (Helix 2026-09 freeze; **no Helix release tag**. Floating `main` logs a warning.) |
| HelixTest source | `helixtest-ref`: `1832c043e1679ec283cb2113510ee33684317cce` (tag `v0.1.3`, same pin as Ferrum / Helix `VERSIONS.lock`) |
| Helix release binaries | **None yet.** The action builds from source (Rust 1.91.1). |

## Inputs

| Input | Required | Default | What it does |
|-------|----------|---------|--------------|
| `endpoint` | when `run` is true | empty | Gateway-style URL, e.g. `http://127.0.0.1:8080` |
| `helix-ref` | no | `26a3209bdbde8ea48d9e6024658fdfb8213d7258` | Git ref of `SynapticFour/Helix` (pin a 40-character SHA) |
| `helixtest-ref` | no | `1832c043e1679ec283cb2113510ee33684317cce` | Git ref of `SynapticFour/HelixTest` |
| `helix-bin` | no | empty | Absolute path to a pre-built `helix` binary (skips the two checkouts + compile) |
| `baseline-branch` | no | PR base, else default branch | Branch used to find the last **successful** workflow run |
| `artifact-name` | no | `helix-verify-json` | Artifact holding `helix-verify.json` |
| `comment` | no | `true` | Upsert a PR comment (`<!-- helix-verification -->`) |
| `fail-on-regression` | no | `true` | Job fails only on PASS → FAIL. Known FAILs stay green. Bench warnings never fail the job. |
| `bench-baseline` | no | empty | Origin for `helix bench --baseline`. Set together with `bench-candidate`, or leave both empty. |
| `bench-candidate` | no | empty | Origin for `helix bench --candidate`. |
| `bench-threshold` | no | `10` | Percent worse than baseline → comment warning only. |
| `bench-baseline-label` | no | `baseline` | Label in bench JSON / comment. |
| `bench-candidate-label` | no | `candidate` | Label in bench JSON / comment. |
| `run` | no | `true` | `false` = skip verify (used by this repo’s CI) |
| `github-token` | no | `${{ github.token }}` | See secrets below |

## Secrets and token permissions

No extra repository secrets are required for a public Ferrum / Helix job.

The **caller workflow** must grant the default `GITHUB_TOKEN` enough permission:

```yaml
permissions:
  contents: read          # checkout Helix / HelixTest (public)
  actions: read           # download the previous run’s artifact
  pull-requests: write    # post or update the PR comment
```

| Need | Secret / token | Notes |
|------|----------------|-------|
| Clone public Helix + HelixTest | `github-token` (default `GITHUB_TOKEN`) | Fine for public repos. For private forks, a PAT with `contents:read` on those repos. |
| Previous JSON | same token, `actions: read` | Looks up the last **successful** run of **this workflow name** on `baseline-branch`. First run has no baseline (comment says `Previous: n/a`; job stays green). |
| PR comment | same token, `pull-requests: write` | Fork PRs from outsiders may not be able to comment; that is a GitHub limitation, not a Helix secret. |
| Helix GHCR / Ferrum registry | **none in this Action** | Bring the stack up in the job (Ferrum `make up` / compose). |

Do not put Ferrum credentials, JWT secrets, or HELIOS signing keys in this Action.

## Outputs

| Output | Meaning |
|--------|---------|
| `json-path` | Current `helix verify --format json` file |
| `regression` | `true` if any check went PASS → FAIL |
| `current-score` | `X/Y` executed checks (skips omitted) |
| `previous-score` | Baseline `X/Y` |
| `bench-warning` | `true` if bench ran and a metric exceeded the threshold (never fails the job) |

`helix verify` itself exits 1 when the report contains FAILs. The Action **captures JSON anyway** and does not use that exit code as the job result.

## PR comment

```
Helix Verification — Previous: 5/5 | Current: 4/5 | DRS: FAIL, WES: SKIP
```

If `bench-baseline` and `bench-candidate` are set, the same comment grows a **Helix bench (warn only)** section. A >threshold% slower candidate is a warning for humans. It does **not** fail the job.

One comment per PR is updated in place.

## Usage (Ferrum pilot — not `main`)

```yaml
name: Helix verify pilot
on:
  pull_request:
    branches: [ci/helix-verify-pilot]
  workflow_dispatch:

permissions:
  contents: read
  actions: read
  pull-requests: write

jobs:
  helix:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # start your stack here (Ferrum compose / make up)
      - uses: SynapticFour/helix-action@SHA   # pin a SHA
        with:
          endpoint: http://127.0.0.1:8080
          helix-ref: 26a3209bdbde8ea48d9e6024658fdfb8213d7258
          helixtest-ref: 1832c043e1679ec283cb2113510ee33684317cce
          # optional Stage 4 scaffold (never fails the job):
          # bench-baseline: http://127.0.0.1:8080
          # bench-candidate: http://127.0.0.1:8080
```

Do **not** add this as a required status check on Ferrum `main` until a week of pilot runs is boring (Helix Stage 2). Known FAILs must not block merges.

## Runners

Build from source on `ubuntu-latest` (x86_64). Same limitation as compiling Helix locally: HelixTest crates (including crypt4gh) must compile on the runner.

## What this is not

- Not a Ferrum installer
- Not helixtest-action (that still downloads `helixtest` release binaries)
- Not a merge of HelixTest into Helix
- Not HELIOS pipeline evidence
- Not GA4GH certification
