# helix-action

helix-action runs `helix verify` in a GitHub job and fails that job only when a check goes from pass to fail.

For someone who already starts a genomics HTTP service in the job and wants a comment when a previously passing check breaks.

**Status: No public status is recorded.** The claims registry has no stage for this action.

It does not start Ferrum. Results are not GA4GH certification. Skips are not passes. Signed evidence stays in [HELIOS](https://github.com/SynapticFour/HELIOS). The suite itself is [HelixTest](https://github.com/SynapticFour/HelixTest). The command is [Helix](https://github.com/SynapticFour/Helix).

## What it does

- It checks out Helix and HelixTest, builds `helix`, and runs `helix verify` against `endpoint`.
- It compares the VerificationRun JSON with the last successful run of the same workflow, at a stable check id.
- It updates one pull request comment. With `fail-on-regression` at its default, the job fails only on PASS to FAIL or PASS to ERROR.
- Optional `helix bench` can add a warning. That warning does not fail the job.

## Limits

- A green run means no new regression of that kind. It does not mean every check passed, and it does not mean the target conforms to a GA4GH specification. Known failures stay green. The first run has no baseline and stays green. See [docs/FOR-EVALUATORS.md](docs/FOR-EVALUATORS.md).
- The action does not start a server. Point `endpoint` at a stack the job already brought up.
- The default `helix-ref` is `7ae2acac5d50238ad36f6c2ddb5ae6695dd97ff7`, an ancestor of Helix's default branch, not the tip. The default `helixtest-ref` is `1baddfd3d75f01dc7c149074a785616fa014c725`. Pin this action at a commit SHA until it has a tag.
- This is not helixtest-action, not a merge of HelixTest into Helix, and not HELIOS.
- Do not add this as a required status check on Ferrum `main` until a week of pilot runs is boring. Known failures must not block merges.

## Quick start

The caller workflow needs `contents: read`, `actions: read`, and `pull-requests: write`.

```yaml
permissions:
  contents: read
  actions: read
  pull-requests: write

jobs:
  helix:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # Start the service in this job. This action does not start it.
      - uses: SynapticFour/helix-action@SHA
        with:
          endpoint: http://127.0.0.1:8080
```

Replace `SHA` with the 40-character commit you have read. Do not use `@main` as the pin. A green job means no new PASS to FAIL or PASS to ERROR at a stable id. It does not mean GA4GH certification.

You should see a pull request comment that counts new regressions, fixes, and existing failures. On a run with no new regression the compare script exits 0.

## Inputs

| Input | Required | Default | What it does |
|-------|----------|---------|--------------|
| `endpoint` | when `run` is true | empty | Gateway-style URL, for example `http://127.0.0.1:8080` |
| `helix-ref` | no | `7ae2acac5d50238ad36f6c2ddb5ae6695dd97ff7` | Git ref of SynapticFour/Helix. Pin a 40-character SHA. |
| `helixtest-ref` | no | `1baddfd3d75f01dc7c149074a785616fa014c725` | Git ref of SynapticFour/HelixTest |
| `helix-bin` | no | empty | Absolute path to a pre-built `helix` binary. Skips the two checkouts and the compile. |
| `baseline-branch` | no | pull request base, else the default branch | Branch used to find the last successful workflow run |
| `artifact-name` | no | `helix-verify-json` | Artifact holding `helix-verify.json` |
| `comment` | no | `true` | Update a pull request comment |
| `fail-on-regression` | no | `true` | Fail only on PASS to FAIL or ERROR at a stable id |
| `bench-baseline` | no | empty | Origin for `helix bench --baseline`. Set with `bench-candidate`, or leave both empty. |
| `bench-candidate` | no | empty | Origin for `helix bench --candidate` |
| `bench-threshold` | no | `10` | Percent worse than baseline. A comment warning only. |
| `bench-baseline-label` | no | `baseline` | Label in the bench JSON and the comment |
| `bench-candidate-label` | no | `candidate` | Label in the bench JSON and the comment |
| `run` | no | `true` | `false` skips verify. This repository's own CI uses that. |
| `github-token` | no | `${{ github.token }}` | Checkout, baseline artifact, and the comment. See [docs/REFERENCE.md](docs/REFERENCE.md). |

## Documentation

Every file under `docs/` is listed in [docs/README.md](docs/README.md).

### Tutorial

The usage example above is the tutorial. There is no separate getting-started page.

### How-to guides

No separate how-to page. The caller permissions are in the reference below.

### Reference

- [Pins, tokens, outputs, and the comment](docs/REFERENCE.md)
- [For evaluators](docs/FOR-EVALUATORS.md)
- [Who it is for](docs/IDENTITY.md)
- [Changelog](CHANGELOG.md)
- [Security](SECURITY.md)

### Explanation

This action is a thin wrapper. The design of the checks is in [Helix](https://github.com/SynapticFour/Helix).

## Licence

Apache License 2.0. The file is [LICENSE](LICENSE). There is no separate licence claim for this action in the registry.

## Cite

Use [CITATION.cff](CITATION.cff). Prefer that file over a hand-copied line.

## Website

- Open tools: [https://synapticfour.com/en/offene-werkzeuge/](https://synapticfour.com/en/offene-werkzeuge/)
- Technical profile: [https://synapticfour.com/en/technical/code/](https://synapticfour.com/en/technical/code/)

The same pages exist in German (`/de/offene-werkzeuge/`, `/de/technik/code/`) and in French (`/fr/offene-werkzeuge/`, `/fr/technique/code/`).

The map of repositories: [profile/README.md](https://github.com/SynapticFour/.github/blob/main/profile/README.md).

Contact: [contact@synapticfour.com](mailto:contact@synapticfour.com)
