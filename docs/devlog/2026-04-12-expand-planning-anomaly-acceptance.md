# Expand Planning Anomaly Acceptance

- Date: 2026-04-12
- Status: resolved

## Problem

The runtime already knew how to project planning anomalies such as:

- `promise-without-task`
- `planner-timeout`
- `followup-task-missing`

But the contract-level acceptance path still mainly proved the happy path:

- structured follow-up creation
- future-first output control
- compound requests not silently creating hidden follow-up state

That meant anomaly regressions could slip past the release-facing acceptance line as long as unit tests stayed green.

## Thinking

The gap was not missing anomaly logic. It was missing cross-layer proof.

For these failure states, the important contract is that runtime stays honest in two places at once:

- operator-facing planning summaries and recovery actions
- user-facing short follow-up projection when a task is still active

If acceptance only checks one layer, drift between those projections becomes a release risk.

## Solution

Expand `scripts/runtime/planning_acceptance.py` with three representative anomaly scenarios:

- finalize a planned promise without a materialized follow-up task and verify `inspect-promise-without-task`
- simulate planner timeout state and verify `inspect-planner-timeout`
- simulate a missing scheduled follow-up task record and verify `inspect-missing-followup-task`

Each scenario now validates both:

- planning summary / recovery-action projection
- short follow-up control-plane metadata and recovery hint

Then update `tests/test_planning_acceptance.py` so the step inventory and rendered markdown stay pinned to the expanded contract.

## Validation

- `python3 scripts/runtime/planning_acceptance.py --json`
- `python3 -m unittest discover -s tests -p 'test_*planning_acceptance*.py' -v`

Both passed after the acceptance expansion.

## Follow-Ups

- Keep `stable_acceptance.py` and planning acceptance aligned if new anomaly classes are added.
- Treat any future mismatch between operator planning summaries and short follow-up recovery hints as a contract regression, not a copy tweak.

## Related Files

- scripts/runtime/planning_acceptance.py
- tests/test_planning_acceptance.py
- .codex/status.md
- .codex/plan.md
