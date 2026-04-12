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

Template and example:

- [planning_acceptance_record_template.md](planning_acceptance_record_template.md)
- [archive/planning_acceptance_record_2026-04-09.md](archive/planning_acceptance_record_2026-04-09.md)
