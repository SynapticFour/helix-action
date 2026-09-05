# Changelog

## [Unreleased]

### Breaking

- Compare is Helix `VerificationRun` at stable check **id**, not HelixTest `OverallReport` test names. PR comment leads with new regressions / fixed failures / existing failures. Removed `current-score` / `previous-score` outputs (a score is not the signal).

### Added

- Pins: HelixTest SHA `1832c043e1679ec283cb2113510ee33684317cce` (`v0.1.3`); Helix `helix-ref` still defaults to `main` with a warning until a Helix release exists. [VERSIONS.lock](VERSIONS.lock).
- Prefers `helix compare --format json` when the pinned CLI has it; `scripts/compare_reports.py` mirrors Helix `src/compare.rs` for this repo’s CI and as fallback.
- Job stays green for known failures, skips, SKIP→PASS, bench warnings, missing/stale baseline, OverallReport previous artifacts, all-unreachable infra, and PR comment 403.
- Job may go red for `NEW_FAIL` or explicit runtime errors (verify exit >1, missing binary, JSON that is not a VerificationRun).
- `docs/PERMISSIONS.md`: least-privilege tokens, `persist-credentials: false`, `source-token` only for private Helix/HelixTest, no broad PAT.
- Example caller: [examples/helix-verify-pilot.yml](examples/helix-verify-pilot.yml) (`ci/helix-verify-pilot` only, not a required Ferrum check).
- `profile` input (`generic` / `ferrum`). Outputs `new-fail`, `fixed`, `unchanged-fail`, `infra-unreachable`.

### Security

- `github-token` is no longer passed into Helix/HelixTest checkouts. Checkouts set `persist-credentials: false`.
