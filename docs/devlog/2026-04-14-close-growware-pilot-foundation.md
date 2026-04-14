# Close Growware Pilot Foundation

## Problem

Milestone 2 had already moved the Growware pilot onto repo-owned docs, policy compilation, validation, and host-audit bootstrap, but one structural gap still remained:

- preflight still treated legacy `.growware/policies/*.json` as required files
- docs still described those JSON files as part of the live control surface
- the compiled `.policy/` layer was already the real runtime truth, so the repo was carrying two policy stories at once

That meant the milestone looked half-migrated even though the runtime had already switched.

## Key Thinking

The remaining fix was not another policy feature.

It was source-of-truth closure:

- remove the last runtime/preflight requirement on legacy Growware policy JSON
- retire those files from the live control surface instead of keeping them as ambiguous “compatibility inputs”
- close the milestone only after the reviewed activation baseline stayed green on the compiled `.policy/` path

## Solution

Closed Milestone 2 in three layers:

1. policy truth
- removed legacy `.growware/policies/*.json` from the required Growware file set
- updated tests so preflight and project summary pass without those files
- retired the legacy JSON files from the repo's live control surface

2. activation baseline
- reran preflight, runtime mirror, targeted Growware tests, binding preview, plugin doctor, plugin smoke, and the full testsuite on the compiled `.policy/` path
- kept `openclaw_runtime_audit.py` as read-only bootstrap evidence instead of promoting it into a repair milestone

3. control surface
- roadmap, development plan, status, plan, strategy, program board, supervision docs, and host resume views now treat Milestone 2 as complete
- `Milestone 3: system performance testing and optimization` is now the active next-phase execution line

## Validation

- `python3 scripts/runtime/growware_preflight.py --json`
- `python3 scripts/runtime/growware_openclaw_binding.py --json`
- `python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_policy_sync tests.test_growware_preflight tests.test_growware_project tests.test_openclaw_runtime_audit -v`
- `bash scripts/run_tests.sh`
- `python3 scripts/runtime/runtime_mirror.py --write`
- `python3 scripts/runtime/plugin_doctor.py --json`
- `python3 scripts/runtime/plugin_smoke.py --json`

## Follow-Up

Do not reopen Growware pilot foundation as a partial migration line.

The next phase should start with reproducible performance measurement, not with intuition-driven tuning or by reintroducing alternate policy truth sources.
