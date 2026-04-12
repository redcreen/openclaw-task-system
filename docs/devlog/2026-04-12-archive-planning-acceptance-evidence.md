# Archive Planning Acceptance Evidence

- Date: 2026-04-12
- Status: resolved

## Problem

The repo already had a planning acceptance bundle and an archive policy, but the dated record generator still defaulted records into `docs/` root.

That left two problems:

- the tooling path disagreed with the docs contract that historical acceptance evidence belongs in `docs/archive/`
- the acceptance helper expansion now covered planning anomalies, channels, and operator recovery, but there was no fresh dated semi-real record proving that widened surface

## Thinking

The right fix was not another one-off manual move.

The reusable boundary is the record workflow itself:

- `create_planning_acceptance_record.py`
- `prepare_planning_acceptance.py`
- `run_planning_acceptance_bundle.py`

If those scripts keep pointing at the active docs stack, maintainers will keep generating dated evidence in the wrong place and cleaning it up later by hand.

The evidence refresh also needed to reflect the current release-facing surface, not the older pre-expansion helper set.

## Solution

Switch the planning acceptance record path to `docs/archive/`, update the runbook wording and archive index to match, then rerun the planning bundle for `2026-04-12`.

After the bundle succeeded, replace the generated stub with a filled archived record that captures:

- the green broader release gate
- the expanded `planning_acceptance.py` anomaly steps
- the widened `stable_acceptance.py` step inventory
- the difference between temporary acceptance-scenario ops projection and clean repo-local `main_ops.py` captures

## Validation

- `bash scripts/run_tests.sh`
- `python3 -m unittest discover -s tests -p 'test_create_planning_acceptance_record.py' -v`
- `python3 -m unittest discover -s tests -p 'test_prepare_planning_acceptance.py' -v`
- `python3 -m unittest discover -s tests -p 'test_capture_planning_acceptance_artifacts.py' -v`
- `python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date 2026-04-12 --force`

## Follow-Ups

- Use a new dated archive record whenever future runtime or delivery changes need fresh semi-real evidence.
- Keep archive-first record generation, runbook wording, and control-surface expectations aligned if the evidence workflow expands again.
- Treat real Feishu / Telegram channel evidence as the next higher-fidelity slice, not as a substitute for keeping the semi-real archive current.

## Related Files

- scripts/runtime/create_planning_acceptance_record.py
- scripts/runtime/prepare_planning_acceptance.py
- tests/test_create_planning_acceptance_record.py
- tests/test_prepare_planning_acceptance.py
- tests/test_capture_planning_acceptance_artifacts.py
- docs/planning_acceptance_runbook.md
- docs/planning_acceptance_runbook.zh-CN.md
- docs/archive/README.md
- docs/archive/planning_acceptance_record_2026-04-12.md
- .codex/status.md
- .codex/plan.md
