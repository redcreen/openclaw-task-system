# Add Main Ops Acceptance Samples

- Date: 2026-04-12
- Status: resolved

## Problem

The repo already had rich `main_ops.py` unit coverage, but release-facing acceptance still did not prove the operator path itself.

That left a gap:

- `dashboard`, `triage`, and `continuity` could drift on the primary recovery action for the same risk state
- watchdog auto-resume could remain unit-tested without becoming a release-facing contract
- maintainers still had to trust local test density and ad hoc CLI inspection for operator UX depth

## Thinking

The missing piece was not another summary helper.

It was a sample-based acceptance entry that proves representative operator workflows from one runtime-owned truth source.

The important contract is not only that each view renders. It is that the operator path stays coherent across:

- session-focused dashboard navigation
- planning anomaly recovery
- planner-timeout recovery
- watchdog-blocked auto-resume guidance

If those samples are not pinned together, operator-facing recovery depth can regress while unit tests still look healthy in isolation.

## Solution

Add `scripts/runtime/main_ops_acceptance.py` as a standalone acceptance helper with four representative checks:

- session-focused dashboard navigation
- `promise-without-task` projected across dashboard, triage, and continuity
- `planner-timeout` projected as operator recovery guidance
- watchdog-blocked auto-resume projected across dashboard and triage

Then wire that helper into `stable_acceptance.py`, add dedicated tests, and update test-plan / testsuite docs so operator recovery acceptance becomes explicit release-facing coverage.

## Validation

- `python3 scripts/runtime/main_ops_acceptance.py --json`
- `python3 -m unittest discover -s tests -p 'test_main_ops_acceptance.py' -v`
- `python3 -m unittest discover -s tests -p 'test_stable_acceptance.py' -v`
- `python3 scripts/runtime/stable_acceptance.py --json`

All passed after the acceptance expansion.

## Follow-Ups

- Keep `main_ops_acceptance.py`, `main_ops.py`, and `stable_acceptance.py` aligned if operator action priority or watchdog guidance changes.
- Treat any future mismatch between `dashboard`, `triage`, and `continuity` primary recovery guidance as a contract regression, not just a rendering tweak.

## Related Files

- scripts/runtime/main_ops_acceptance.py
- scripts/runtime/main_ops.py
- scripts/runtime/stable_acceptance.py
- tests/test_main_ops_acceptance.py
- tests/test_stable_acceptance.py
- .codex/status.md
- .codex/plan.md
