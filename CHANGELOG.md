# Changelog

## [Unreleased]

### Changed

- Default `helix-ref` is the Helix origin/main freeze SHA `26a3209bdbde8ea48d9e6024658fdfb8213d7258` (not `main`). Default `helixtest-ref` is HelixTest SHA `1832c043e1679ec283cb2113510ee33684317cce` (tag v0.1.3). Floating `main` logs a warning.

### Added

- Composite action that builds `helix verify` from Helix + sibling HelixTest, compares HelixTest-shaped JSON to the last successful workflow run, upserts a PR comment, and fails the job **only** on PASS → FAIL regressions. Does not start servers. Not GA4GH certification. Not HELIOS.
- Optional `helix bench` (two origins, 3 GETs). Threshold warnings are appended to the same PR comment and **never** change the job result.
