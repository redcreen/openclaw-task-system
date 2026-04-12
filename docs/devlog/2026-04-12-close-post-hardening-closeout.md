# Close Post-Hardening Closeout

## Problem

The repo had already done most of the hardening and docs retrofit work, but the last post-hardening closeout debt still lived in three different places:

- boundary docs still used old wording such as `open design boundary`, `minimum implementation`, or `not yet`
- release-facing acceptance still had thin spots around control-plane summary proof, bounded-channel sample depth, and missing-followup operator recovery
- roadmap and control-surface docs still described the closeout milestone as active

That made the repo look half-closed even though the runtime behavior was already mostly converged.

## Key Thinking

The right fix was not more runtime behavior.

The remaining gap was convergence:

- make the docs say exactly what the shipped runtime now does
- add one more layer of runnable evidence where the docs were still carrying too much explanatory weight
- then explicitly close the milestone instead of leaving a fake active long task behind

## Solution

Closed the post-hardening closeout line in three layers:

1. boundary docs
- compound follow-up now describes the shipped runtime boundary
- output-channel separation now matches the current runtime contract
- same-session routing now treats `collect-more` as a shipped non-task path

2. release-facing evidence
- planning acceptance now proves scheduled follow-up summaries stay in control-plane projection
- channel acceptance now includes a bounded-focus `webchat` sample
- main-ops acceptance now includes `followup-task-missing` recovery projection

3. control surface
- roadmap, development plan, README, todo intake, and `.codex/*` now describe Milestone 1 as complete
- future work must re-enter as a named roadmap candidate instead of generic closeout debt

## Validation

- `python3 -m unittest discover -s tests -p 'test_*acceptance*.py' -v`
- `python3 scripts/runtime/planning_acceptance.py --json`
- `python3 scripts/runtime/channel_acceptance.py --json`
- `python3 scripts/runtime/main_ops_acceptance.py --json`
- `bash scripts/run_tests.sh`
- `python3 scripts/runtime/release_gate.py --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --json`

## Follow-Up

Do not reopen post-hardening closeout as ambient maintenance.

If broader planning, steering, or higher-fidelity evidence work resumes, promote it to a new named roadmap candidate first.
