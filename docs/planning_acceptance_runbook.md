[English](planning_acceptance_runbook.md) | [中文](planning_acceptance_runbook.zh-CN.md)

# Planning Acceptance Runbook

## Purpose

This runbook explains how to run real or semi-real planning acceptance and capture evidence back into the repository.

For full Chinese detail, see [planning_acceptance_runbook.zh-CN.md](planning_acceptance_runbook.zh-CN.md).

## Minimum Sequence

1. validate the base runtime and plugin health
2. run the planning acceptance helpers or bundle
3. capture artifacts
4. fill an acceptance record under `docs/archive/`
5. write back conclusions and next steps

## Main Entry Points

```bash
python3 scripts/runtime/prepare_planning_acceptance.py --json
python3 scripts/runtime/run_planning_acceptance_bundle.py --json
python3 scripts/runtime/capture_planning_acceptance_artifacts.py --json
```

To rehearse the same workflow without writing under `docs/archive/` or `docs/artifacts/`, add `--dry-run`.

```bash
python3 scripts/runtime/prepare_planning_acceptance.py --dry-run --json
python3 scripts/runtime/run_planning_acceptance_bundle.py --dry-run --json
python3 scripts/runtime/planning_acceptance_suite.py --dry-run --json
```

The dry-run flow writes the record and artifacts into a temporary workspace and returns that workspace path in JSON output.

## Promotion Policy

Treat `--dry-run` as rehearsal, not as final dated evidence.

Promote a dry-run into `docs/archive/` only when all of the following are true:

1. the full bundle is green
2. the run was not label-filtered
3. the current change touches planning/runtime contracts, release-facing acceptance coverage, or the planning evidence workflow itself

When those conditions hold, rerun:

```bash
python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date YYYY-MM-DD
```

This promotion refreshes repo-side artifacts and preserves an existing dated archive record instead of replacing it with the template again.

Interpret the structured policy fields this way:

- `promotion_status=ready-for-archive`: the dry-run is strong enough to promote when formal dated evidence is needed
- `promotion_status=insufficient-signal`: partial dry-run only; do not archive from it
- `promotion_status=blocked`: fix the failing dry-run first
- `promotion_status=already-archived`: this run already wrote repo-side evidence

The bundle and suite commands now emit that promotion policy directly in JSON and markdown output.

Template and example:

- [planning_acceptance_record_template.md](planning_acceptance_record_template.md)
- [archive/planning_acceptance_record_2026-04-09.md](archive/planning_acceptance_record_2026-04-09.md)
