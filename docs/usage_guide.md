[English](usage_guide.md) | [中文](usage_guide.zh-CN.md)

# Usage Guide

This guide covers two things:

- how to operate the system after installation
- which commands to use for the most common runtime and operator questions

For project scope and shipped status, start with:

- [../README.md](../README.md)
- [roadmap.md](roadmap.md)

## Daily Runtime Model

The normal flow is:

1. a user message enters task-system control
2. runtime registers or reuses a task
3. runtime returns `[wd]`
4. execution continues through the underlying agent path
5. runtime may send progress, follow-up, or recovery control-plane messages
6. the task closes as `done`, `failed`, `blocked`, `paused`, or another managed terminal state

This now covers:

- normal long tasks
- delayed reply and continuation
- same-session routing
- watchdog and continuity recovery
- future-first planning contracts

## Operator Commands

### Health and Overview

```bash
python3 scripts/runtime/main_ops.py health
python3 scripts/runtime/main_ops.py dashboard
python3 scripts/runtime/main_ops.py dashboard --compact
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/main_ops.py dashboard --only-issues
python3 scripts/runtime/main_ops.py triage
python3 scripts/runtime/main_ops.py triage --compact
python3 scripts/runtime/main_ops.py triage --json
python3 scripts/runtime/openclaw_runtime_audit.py
python3 scripts/runtime/openclaw_runtime_audit.py --json
python3 scripts/runtime/openclaw_runtime_audit.py --lookback-hours 48 --recent-limit 20
```

Use `openclaw_runtime_audit.py` when you need a host-side reality check from real OpenClaw data under `~/.openclaw` instead of repo-local tests. It summarizes:

- operator health from recent task runs, failed deliveries, cron errors, and config health
- user-visible history from recent requests and terminal summaries
- explicit remediation suggestions for stale running tasks and delivery residue

### Queues and Lanes

```bash
python3 scripts/runtime/main_ops.py queues
python3 scripts/runtime/main_ops.py queues --json
python3 scripts/runtime/main_ops.py lanes
python3 scripts/runtime/main_ops.py lanes --json
```

### Continuity and Recovery

```bash
python3 scripts/runtime/main_ops.py continuity
python3 scripts/runtime/main_ops.py continuity --compact
python3 scripts/runtime/main_ops.py continuity --only-issues
python3 scripts/runtime/main_ops.py continuity --json
python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe --dry-run --json
python3 scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --dry-run
```

Use the snapshot flags for day-to-day operator duty:

- `--compact` keeps the view short enough for routine queue checks
- `--only-issues` hides clean-state continuity detail and shows only actionable findings

### Planning and Phase 6 Operations

```bash
python3 scripts/runtime/runtime_mirror.py --check
python3 scripts/runtime/main_ops.py planning
python3 scripts/runtime/main_ops.py planning --json
python3 scripts/runtime/planning_acceptance.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
python3 scripts/runtime/planning_acceptance_suite.py --dry-run --json
python3 scripts/runtime/run_planning_acceptance_bundle.py --dry-run --json
python3 scripts/runtime/main_ops.py plugin-install-drift --json
```

Use the `--dry-run` variants when you want to exercise the planning evidence workflow without writing records or artifacts back into the repo docs tree.

If the full dry-run bundle is green and the change touches planning/runtime contracts, release-facing acceptance coverage, or the evidence workflow itself, promote it with:

```bash
python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date YYYY-MM-DD
```

Acceptance and historical records:

- [planning_acceptance_runbook.md](planning_acceptance_runbook.md)
- [planning_acceptance_record_template.md](planning_acceptance_record_template.md)
- [archive/planning_acceptance_record_2026-04-09.md](archive/planning_acceptance_record_2026-04-09.md)

### Same-Session Routing

```bash
python3 scripts/runtime/same_session_routing_acceptance.py --json
python3 scripts/runtime/stable_acceptance.py --json
```

### Task Lookup and Control

```bash
python3 scripts/runtime/task_cli.py tasks
python3 scripts/runtime/task_cli.py task <task_id>
python3 scripts/runtime/task_cli.py session '<session_key>'
python3 scripts/runtime/main_ops.py list
python3 scripts/runtime/main_ops.py show <task_id>
python3 scripts/runtime/main_ops.py cancel --task-id <task_id>
python3 scripts/runtime/main_ops.py stop
python3 scripts/runtime/main_ops.py stop-all
python3 scripts/runtime/main_ops.py purge --session-key '<session_key>'
```

## Validation Shortcuts

Full regression:

```bash
bash scripts/run_tests.sh
```

Stable acceptance:

```bash
python3 scripts/runtime/stable_acceptance.py --json
```

Broader release gate:

```bash
python3 scripts/runtime/release_gate.py --json
```

`release_gate.py` keeps the release-facing verification line explicit by running the base testsuite, operator acceptance, stable acceptance, runtime mirror, and install-drift checks in one report.
