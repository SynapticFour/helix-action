# helix-action

GitHub Action wrapper around **`helix verify`** ([Helix](https://github.com/SynapticFour/Helix) / HelixTest heritage). Apache-2.0. **Not a product SKU.** Parallel to [helixtest-action](https://github.com/SynapticFour/helixtest-action).

HelixTest already runs; this Action **productizes** that as CI visibility: pin Helix + HelixTest, run `helix verify`, capture `VerificationRun` JSON, compare at stable check **id**, comment on the PR.

A **regression** is PASS → FAIL/ERROR at a Helix `id` (`NEW_FAIL`). It is **not** a score drop. The PR comment leads with **new regressions**, then **fixed failures**, then **existing failures**. Known failures, skips, bench warnings, and identified infrastructure (unreachable target, missing/stale baseline, comment 403) do **not** fail the job.

The action **does not start Ferrum**. Point `endpoint` at a stack you already brought up in the job. Results are **not** official GA4GH certification. Skips are not passes. Not HELIOS (no RO-Crate / PDF / signatures).

HelixTest stays a **separate git root**. This action checks out Helix and HelixTest as siblings to build the CLI (Helix `Cargo.toml` path-depends on `../HelixTest`). Do not merge HelixTest into Helix for this Action to work.

**Not a required Ferrum check.** Do not add this as a required status on Ferrum `main`. Pilot branch only: `ci/helix-verify-pilot`.

## Pin

Until this repo has a tag, pin the action at a **commit SHA**.

| What | Default | Notes |
|------|---------|--------|
| Helix source | `helix-ref`: `main` | **No Helix release tag.** Callers must pin a SHA that emits `VerificationRun` and includes `helix compare`. Floating `main` logs a warning. |
| HelixTest source | `helixtest-ref`: `1832c043e1679ec283cb2113510ee33684317cce` | Tag `v0.1.3`, same pin as Ferrum / Helix `VERSIONS.lock` |
| Helix release binaries | **None** | The action builds from source (Rust 1.91.1) |
| This Action | no floating `main` in callers | `uses: SynapticFour/helix-action@<sha>` |

See [VERSIONS.lock](VERSIONS.lock).

## Inputs

| Input | Required | Default | What it does |
|-------|----------|---------|--------------|
| `endpoint` | when `run` is true | empty | Gateway-style URL, e.g. `http://127.0.0.1:8080` |
| `helix-ref` | no | `main` | Git ref of `SynapticFour/Helix` (pin a SHA in production) |
| `helixtest-ref` | no | `1832c043e1679ec283cb2113510ee33684317cce` | Git ref of `SynapticFour/HelixTest` |
| `helix-bin` | no | empty | Absolute path to a pre-built `helix` binary (skips the two checkouts + compile) |
| `profile` | no | `generic` | `generic` or `ferrum`. Never inferred from the target. |
| `baseline-branch` | no | PR base, else default branch | Branch used to find the last **successful** workflow run |
| `artifact-name` | no | `helix-verify-json` | Artifact holding `helix-verify.json` |
| `comment` | no | `true` | Upsert a PR comment (`<!-- helix-verification -->`). Comment failure never fails the job. |
| `fail-on-regression` | no | `true` | Job fails only on `NEW_FAIL`. Known FAILs stay green. Bench warnings never fail the job. |
| `bench-baseline` | no | empty | Origin for `helix bench --baseline`. Set together with `bench-candidate`, or leave both empty. |
| `bench-candidate` | no | empty | Origin for `helix bench --candidate`. |
| `bench-threshold` | no | `10` | Percent worse than baseline → comment warning only. |
| `bench-baseline-label` | no | `baseline` | Label in bench JSON / comment. |
| `bench-candidate-label` | no | `candidate` | Label in bench JSON / comment. |
| `run` | no | `true` | `false` = skip verify (used by this repo’s CI) |
| `github-token` | no | `${{ github.token }}` | Artifact download + PR comment only. **Not** passed into Helix/HelixTest checkouts. |
| `source-token` | no | empty | Optional `contents:read` token if Helix/HelixTest are private. |

## Secrets and token permissions

Full contract: [docs/PERMISSIONS.md](docs/PERMISSIONS.md).

The **caller workflow** must grant the default `GITHUB_TOKEN`:

```yaml
permissions:
  contents: read
  actions: read
  pull-requests: write
```

Do not put Ferrum credentials, JWT secrets, or HELIOS signing keys in this Action. Do not pass a broad PAT.

## Outputs

| Output | Meaning |
|--------|---------|
| `json-path` | Current `helix verify --format json` file (`VerificationRun`) |
| `regression` | `true` if the job should fail (`NEW_FAIL`, not infra unreachable) |
| `new-fail` | Count of `NEW_FAIL` rows |
| `fixed` | Count of `FIXED` rows |
| `unchanged-fail` | Count of `UNCHANGED_FAIL` rows (existing failures) |
| `bench-warning` | `true` if bench ran and a metric exceeded the threshold (never fails the job) |
| `infra-unreachable` | `true` if every executed check is ERROR unreachable |

There is **no** `current-score` / `previous-score` output. `helix verify` itself exits 1 when the report contains FAILs. The Action **captures JSON anyway** and does not use that exit code as the job result.

## PR comment

```
# Helix verification

Stable check **id** (not a score). …

**New regressions:** N
**Fixed failures:** N
**Existing failures:** N

## New regressions
- `drs.object.checksum` (`HLX-DRS-003`) pass → fail
## Fixed failures
## Existing failures
```

Classification matches Helix `helix compare` / [REGRESSION.md](https://github.com/SynapticFour/Helix/blob/main/docs/REGRESSION.md) when the pinned CLI has `compare`; otherwise `scripts/compare_reports.py` uses the same table.

If `bench-baseline` and `bench-candidate` are set, the same comment grows a **Helix bench (warn only)** section **after** the failure lists. A >threshold% slower candidate is a warning for humans. It does **not** fail the job.

One comment per PR is updated in place. A 403 (typical on fork PRs) does not fail the job.

## Usage (Ferrum pilot — not `main`)

Copy [examples/helix-verify-pilot.yml](examples/helix-verify-pilot.yml). Summary:

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
        with:
          persist-credentials: false
      # start your stack here (Ferrum compose / make up)
      - uses: SynapticFour/helix-action@SHA   # pin a SHA
        with:
          endpoint: http://127.0.0.1:8080
          helix-ref: <Helix SHA with helix compare>
          helixtest-ref: 1832c043e1679ec283cb2113510ee33684317cce
```

## Runners

Build from source on `ubuntu-latest` (x86_64). Same limitation as compiling Helix locally: HelixTest crates (including crypt4gh) must compile on the runner.

## What this is not

- Not a Ferrum installer
- Not a required Ferrum `main` check
- Not helixtest-action (that still downloads `helixtest` release binaries)
- Not a merge of HelixTest into Helix
- Not HELIOS pipeline evidence
- Not GA4GH certification
- Not a scoreboard
