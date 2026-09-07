# Changelog

## [Unreleased]

### Breaking

- `scripts/compare_reports.py` compares **Helix `VerificationRun`** only (`schema_version` `helix-verification-v1`, `executed[]` / `skipped[]`) at stable check **id** (example `drs.object.checksum` / `HLX-DRS-003`). It **rejects** HelixTest `OverallReport` (`services[]`) from `helix verify`. That was the pre-freeze verify JSON and is still the `helix security` shape — a different CLI. Dual-schema parsing was not added.
- Current OverallReport or unknown JSON exits **2** with a message naming the expected discriminator. A previous OverallReport artifact is **not** compared (not dual-schema): it is ignored so a VerificationRun can become the new baseline.
- Skip is never pass. `PASS → ERROR` is `NEW_FAIL`. `SKIP → FAIL` is not a regression. Score drop from pass→skip is not a regression. The PR comment is kind counts at stable id, not `Previous: X/Y`.
- The default `helix-ref` freeze `1304d92daa80f6c9b8b164a543c2210bab391863` is still Helix **origin/main**. That tree has **no** `schemas/helix-verification-v1.json`. The pin was **not** moved to unpublished Helix WIP. `run: true` with the default pin fails at build (schema file missing), not after a verify. Override `helix-ref` or `helix-bin` only with a **published** Helix commit/binary that emits VerificationRun.

### Changed

- Default `helix-ref` is Helix origin/main SHA `1304d92daa80f6c9b8b164a543c2210bab391863` (not `main`). Default `helixtest-ref` is HelixTest SHA `1832c043e1679ec283cb2113510ee33684317cce` (tag v0.1.3). Floating `main` logs a warning.

### Added

- Composite action that builds `helix verify` from Helix + sibling HelixTest, compares VerificationRun JSON to the last successful workflow run, upserts a PR comment, and fails the job **only** on PASS → FAIL/ERROR regressions at stable id. Does not start servers. Not GA4GH certification. Not HELIOS.
- Optional `helix bench` (two origins, 3 GETs). Threshold warnings are appended to the same PR comment and **never** change the job result.
