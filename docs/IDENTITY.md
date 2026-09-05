# Who helix-action is for

A **thin GitHub Action** so Ferrum (or any) CI can run **`helix verify`** against a stack the job already started, compare `VerificationRun` JSON at stable Helix **id** to the last successful run on the target branch, and comment **new regressions / fixed failures / existing failures**. Optional `helix bench` warnings may be appended; they never fail the job. Apache-2.0. Not sold.

Helix productizes HelixTest (separate git root). This Action is the Stage 2 CI wrapper, parallel to [helixtest-action](https://github.com/SynapticFour/helixtest-action) (which downloads HelixTest release binaries and does not compare/comment).

**Not for:** deploying Ferrum, issuing Passports, proving a stack you did not start in the same job, HELIOS evidence packs, treating green CI as GA4GH certification, or a required Ferrum `main` gate. Pilot branch `ci/helix-verify-pilot` only.

Helix tests behavior against the GA4GH spec, independent of implementation. Ferrum is a reference target, not a dependency. There is no real Ferrum clinical pilot (DIZ / genomDE) to cite.

Permissions: [PERMISSIONS.md](PERMISSIONS.md).
