# Who helix-action is for

A **thin GitHub Action** so CI can run **`helix verify`** against a stack the job already started, compare JSON to the last successful run on the target branch, and comment PASS/FAIL counts. Optional `helix bench` warnings may be appended; they never fail the job. Apache-2.0.

Helix is HelixTest becoming a standalone VERIFY CLI (separate git root). This Action is the CI wrapper, parallel to [helixtest-action](https://github.com/SynapticFour/helixtest-action) (which downloads `helixtest` release binaries and does not compare/comment).

Point `endpoint` at a stack you already started in the job. Results are a technical signal, not GA4GH certification. HELIOS (signed evidence / RO-Crate / PDF) is a different tool.

The CLI tests behaviour against the GA4GH spec, independent of implementation. Ferrum is a convenient reference target, not a dependency.
