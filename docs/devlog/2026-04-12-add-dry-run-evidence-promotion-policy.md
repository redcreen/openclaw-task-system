# Add Dry-Run Evidence Promotion Policy

## Problem

After adding planning bundle `--dry-run`, maintainers could rehearse the evidence workflow safely, but one decision was still implicit:

- when is a green dry-run only a rehearsal
- and when must it be promoted into a dated archive record

Without an explicit rule, two failures were likely:

- partial or filtered dry-runs being mistaken for formal evidence
- green full dry-runs stopping too early, with no archive refresh even though the change touched release-facing planning/runtime behavior

## Key Thinking

The policy needed to live where maintainers already look for the result:

- bundle output
- suite output
- planning runbook
- archive guidance

That is the right layer because promotion is a workflow decision attached to evidence quality, not a new runtime behavior.

The policy also needed explicit states rather than one vague recommendation.

## Solution

Added structured promotion states to `run_planning_acceptance_bundle.py` and surfaced the same policy through `planning_acceptance_suite.py`.

The policy now distinguishes:

- `ready-for-archive`
- `insufficient-signal`
- `blocked`
- `already-archived`

and includes the next repo-writing command when promotion is appropriate.

Updated the planning runbook, usage guide, archive index, and control surface so they all describe the same rule:

- only a full green dry-run can become dated archive evidence
- label-filtered dry-runs cannot
- failed dry-runs cannot
- promotion is required before merge when the change touches planning/runtime contracts, release-facing acceptance coverage, or the evidence workflow itself

## Validation

- `python3 -m unittest discover -s tests -p 'test_run_planning_acceptance_bundle.py' -v`
- `python3 -m unittest discover -s tests -p 'test_planning_acceptance_suite.py' -v`
- `python3 scripts/runtime/run_planning_acceptance_bundle.py --dry-run --json`
- `python3 scripts/runtime/release_gate.py --json`

## Follow-Up

The next higher-fidelity slice is still real or semi-real Feishu / Telegram evidence.

At that point, the current promotion policy should stay aligned with:

- what counts as sufficient dated evidence
- when a new archive record is mandatory
- how real-channel evidence and semi-real archive evidence complement each other
