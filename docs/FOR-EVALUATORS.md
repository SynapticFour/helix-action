# For evaluators

What a run of this action is evidence of. Not a sales brief. Not GA4GH certification. Not HELIOS.

## What a green run means

With `fail-on-regression` left at its default `true`, the job fails only when a check went from PASS to FAIL or from PASS to ERROR at a stable Helix check id. `scripts/compare_reports.py` is that rule.

A green run means that comparison found no such regression. It also stays green when:

- the previous run had the same FAIL (a known failure is not a regression);
- there is no previous successful artifact yet;
- a check moved from SKIP to FAIL, or a score dropped because a check was skipped;
- `helix bench` warned that a candidate was slower than `bench-threshold`.

Skip is never pass. The score `X/Y` omits skips. It is not a certification score.

## What a green run does not mean

- It does not mean the target conforms to a GA4GH specification.
- It does not mean every check passed. Known FAILs stay green.
- It does not mean this action started Ferrum, ga4gh-infra, or any other server. `endpoint` has to be a stack the job already started.
- It does not mean the Helix pin is the tip of Helix's default branch. The default `helix-ref` is `7ae2acac5d50238ad36f6c2ddb5ae6695dd97ff7`, an ancestor of that branch.
- It does not mean signed evidence. That stays in [HELIOS](https://github.com/SynapticFour/HELIOS).
- A red run means a new regression at a stable id, or that the action could not build or could not read a VerificationRun. An OverallReport as the current JSON exits 2. That shape is not this action's contract.

The claims registry has no stage for this action.

## Contact

[contact@synapticfour.com](mailto:contact@synapticfour.com)
