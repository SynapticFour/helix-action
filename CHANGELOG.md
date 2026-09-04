# Changelog

## [Unreleased]

### Added

- Composite action that builds `helix verify` from Helix + sibling HelixTest, compares HelixTest-shaped JSON to the last successful workflow run, upserts a PR comment, and fails the job **only** on PASS → FAIL regressions. Does not start servers. Not GA4GH certification. Not HELIOS.
