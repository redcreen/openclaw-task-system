# Add Planning Bundle Dry-Run

## Problem

The repo already had a planning evidence workflow, but every main entrypoint wrote directly into `docs/archive/` and `docs/artifacts/`.

That made the workflow awkward to rehearse:

- maintainers could not safely exercise the full bundle before deciding whether to refresh repo evidence
- docs had to describe a repo-writing workflow even when the user only wanted a local confidence pass
- the only practical workaround was an ad hoc manual temp-directory routine outside the shipped commands

## Key Thinking

The right fix was not to build a second "preview" tool.

The existing entrypoints already defined the workflow:

- `prepare_planning_acceptance.py`
- `capture_planning_acceptance_artifacts.py`
- `run_planning_acceptance_bundle.py`
- `planning_acceptance_suite.py`

So the missing piece was execution mode, not another layer of control.

That meant the maintainable solution was:

1. keep the repo-writing path unchanged
2. add `--dry-run` to the existing commands
3. move dry-run writes into a temporary workspace while preserving the same record / artifact layout

## Solution

Added temporary-workspace `--dry-run` support across the planning evidence workflow.

Now:

- `prepare_planning_acceptance.py --dry-run --json` seeds a temporary workspace
- `capture_planning_acceptance_artifacts.py --dry-run --json` captures outputs there
- `run_planning_acceptance_bundle.py --dry-run --json` writes its bundle summary there
- `planning_acceptance_suite.py --dry-run --json` combines tests with that same temporary bundle flow

The dry-run workspace keeps the familiar structure:

- `archive/planning_acceptance_record_<date>.md`
- `artifacts/planning_acceptance_<date>/...`

and the JSON payload now exposes the workspace root so maintainers can inspect the outputs.

## Validation

- `python3 -m unittest discover -s tests -p 'test_prepare_planning_acceptance.py' -v`
- `python3 -m unittest discover -s tests -p 'test_capture_planning_acceptance_artifacts.py' -v`
- `python3 -m unittest discover -s tests -p 'test_run_planning_acceptance_bundle.py' -v`
- `python3 -m unittest discover -s tests -p 'test_planning_acceptance_suite.py' -v`
- `python3 scripts/runtime/run_planning_acceptance_bundle.py --dry-run --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --dry-run --json`

## Follow-Up

The next post-hardening slice should move from safe rehearsal into deeper evidence:

- real or semi-real Feishu / Telegram evidence capture
- or a stricter policy for when dry-run evidence must be promoted into archived repo evidence
