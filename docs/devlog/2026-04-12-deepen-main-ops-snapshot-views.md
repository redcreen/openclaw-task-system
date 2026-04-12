# Deepen Main Ops Snapshot Views

## Problem

`main_ops.py` already exposed a usable operator dashboard, but the deeper operator entrypoints were asymmetric:

- `dashboard` had `--compact` and `--only-issues`
- `continuity` only had the full verbose report
- `triage` only had the full action list

That mismatch made day-to-day operator duty slower than it needed to be. The same truth source existed, but operators still had to read the long forms for continuity and triage even when they only wanted a quick snapshot.

## Key Thinking

The right fix was not to invent another helper script. The existing operator entrypoints already owned the truth and the recovery recommendations.

The gap was projection depth:

- continuity needed a short snapshot and an issue-focused view
- triage needed a short snapshot
- release-facing acceptance needed to prove these shorter projections, not just the full reports

Keeping the new views inside `main_ops.py` preserved one source of truth for the underlying runbook logic.

## Solution

Updated `scripts/runtime/main_ops.py` so that:

- `continuity` now accepts `--compact` and `--only-issues`
- `triage` now accepts `--compact`
- `get_main_continuity_summary()` returns `status`, `compact_summary`, and `issue_summary`
- `get_main_triage_summary()` returns `compact_summary`
- the markdown renderers project the shorter snapshots without duplicating runbook logic

Extended acceptance so `main_ops_acceptance.py` now proves the new snapshot surface on top of the watchdog auto-resume scenario, including:

- compact continuity output
- issue-only continuity output
- compact triage output

Updated operator-facing docs so the new commands appear in the usage guide and test documents.

## Validation

- `python3 -m unittest discover -s tests -p 'test_main_ops.py' -v`
- `python3 -m unittest discover -s tests -p 'test_main_ops_acceptance.py' -v`

## Follow-Up

The next operator-facing depth slice should move from shorter snapshots to evidence quality:

- real or semi-real Feishu / Telegram operator captures
- broader release-gate checks that exercise the new snapshot entrypoints end to end
