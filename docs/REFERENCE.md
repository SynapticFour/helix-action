# Reference

Details that the README points at. The inputs and the usage example stay in the README. The defaults below are the `default:` lines in `action.yml` on this branch.

## Pin

Until this repository has a tag, pin the action at a commit SHA.

| What | Default in `action.yml` |
|------|-------------------------|
| Helix source | `helix-ref`: `7ae2acac5d50238ad36f6c2ddb5ae6695dd97ff7`. That commit is an ancestor of Helix's default branch. It is not the tip. Floating `main` logs a warning. That tree includes `schemas/helix-verification-v1.json`. This action compares VerificationRun only and invokes Helix's technical verification path. |
| HelixTest source | `helixtest-ref`: `1baddfd3d75f01dc7c149074a785616fa014c725`. Helix's `Cargo.toml` path-depends on a sibling checkout. HelixTest lineage `v0.1.3`. Not the tagged tag commit `1832c043e1679ec283cb2113510ee33684317cce`. |
| Helix release binaries | None in this action. The action builds from source (Rust 1.91.1) unless `helix-bin` is set. |

HelixTest stays a separate git root. This action checks out Helix and HelixTest as siblings to build the CLI. Do not merge HelixTest into Helix for this action to work.

## Secrets and token permissions

No extra repository secrets are required for a public Ferrum or Helix job.

The caller workflow must grant the default `GITHUB_TOKEN` enough permission:

```yaml
permissions:
  contents: read
  actions: read
  pull-requests: write
```

| Need | Secret or token | Notes |
|------|-----------------|-------|
| Clone public Helix and HelixTest | `github-token` (default `GITHUB_TOKEN`) | Fine for public repositories. For private forks, a token with `contents: read` on those repositories. |
| Previous JSON | same token, `actions: read` | Looks up the last successful run of this workflow name on `baseline-branch`. The first run has no baseline. The comment says there is no previous run. The job stays green. |
| Pull request comment | same token, `pull-requests: write` | Fork pull requests from outsiders may not be able to comment. That is a GitHub limitation. |
| Helix container registry or Ferrum registry | none in this action | Bring the stack up in the job. |

Do not put Ferrum credentials, JWT secrets, or HELIOS signing keys in this action.

## Outputs

| Output | Meaning |
|--------|---------|
| `json-path` | Current `helix verify --format json` file |
| `regression` | `true` if any check went PASS to FAIL or ERROR at a stable id |
| `current-score` | `X/Y` executed checks from VerificationRun (`pass` / `pass+fail+error`; skips omitted). Not a certification score. |
| `previous-score` | Baseline `X/Y`, or `0/0` when none, or when the previous file was an OverallReport |
| `bench-warning` | `true` if bench ran and a metric exceeded the threshold. It never fails the job by itself. |

`helix verify` itself exits 1 when the report contains FAILs. The action captures the JSON anyway. The job result is the regression comparison, not that exit code. `scripts/compare_reports.py` exits 0 when there is no regression, including a known FAIL and a first run with no baseline. It exits 1 on a new regression. An OverallReport or unknown JSON as the current file exits 2.

## JSON shape

`helix verify --format json` is a Helix VerificationRun (`schema_version`: `helix-verification-v1`, `executed[]` / `skipped[]`). Compare is at a stable check id (example `drs.object.not_found` / `HLX-DRS-005`). A HelixTest OverallReport (`services[]`) is rejected for the current JSON (exit 2). That shape is still `helix security`, not this action. A previous OverallReport artifact is ignored so a new VerificationRun can become the baseline. It is not parsed. This is not HELIOS.

## Pull request comment

```
Helix verification — new regressions: 1; fixed: 0; existing failures: 0
```

If `bench-baseline` and `bench-candidate` are set, the same comment grows a Helix bench section. A candidate slower than the threshold is a warning. It does not fail the job. One comment per pull request is updated in place. The marker is `<!-- helix-verification -->`.

## Runners

Build from source on `ubuntu-latest` (x86_64). HelixTest crates, including crypt4gh, must compile on the runner. That is the same limit as compiling Helix locally.

## What this is not

- Not a Ferrum installer
- Not [helixtest-action](https://github.com/SynapticFour/helixtest-action), which downloads `helixtest` release binaries
- Not a merge of HelixTest into Helix
- Not HELIOS pipeline evidence
- Not GA4GH certification
