[English](planning_acceptance_runbook.md) | [中文](planning_acceptance_runbook.zh-CN.md)

# Planning Acceptance Runbook

## Purpose

This runbook explains how to run real or semi-real planning acceptance and capture evidence back into the repository.

## When To Use It

Run this flow when a change touches any of the following:

- planning or future-first contracts
- delayed follow-up materialization
- planning anomaly detection or projection
- release-facing acceptance coverage
- the planning evidence workflow itself

## Minimum Sequence

1. validate the base runtime and plugin health
2. run the planning acceptance helper or the full bundle
3. capture artifacts and summaries
4. create or refresh a dated record under `docs/archive/`
5. write back conclusions, gaps, and follow-up actions

## Main Entry Points

Base preparation:

```bash
python3 scripts/runtime/prepare_planning_acceptance.py --json
```

Repo-writing evidence bundle:

```bash
python3 scripts/runtime/run_planning_acceptance_bundle.py --json
```

Standalone artifact capture:

```bash
python3 scripts/runtime/capture_planning_acceptance_artifacts.py --json
```

Dry-run rehearsal without writing into `docs/archive/` or `docs/artifacts/`:

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

## How To Read Promotion Status

Interpret the structured policy fields this way:

- `promotion_status=ready-for-archive`: the dry-run is strong enough to promote when formal dated evidence is needed
- `promotion_status=insufficient-signal`: partial dry-run only; do not archive from it
- `promotion_status=blocked`: fix the failing dry-run first
- `promotion_status=already-archived`: this run already wrote repo-side evidence

The bundle and suite commands now emit that promotion policy directly in JSON and markdown output.

## Record Update Checklist

After a repo-writing run, update or verify:

- the dated archive record under `docs/archive/`
- artifact links under `docs/artifacts/`
- any follow-up note in `.codex/status.md` if the evidence changes the active slice
- runbook wording if the command flow or promotion contract changed

Template and example:

- [planning_acceptance_record_template.md](planning_acceptance_record_template.md)
- [archive/planning_acceptance_record_2026-04-09.md](archive/planning_acceptance_record_2026-04-09.md)
