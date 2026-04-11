# OpenClaw Task System Plugin

This package is the plugin-first integration layer for the OpenClaw Task System.

It is designed to keep OpenClaw core untouched:

- install the plugin
- enable it in OpenClaw config
- let the plugin call the task-system runtime hooks

Current first-stage hook behavior:

- registers long-task candidates during `before_dispatch`
- syncs active-task progress during `message_sending`
- finalizes active tasks during `agent_end`
- polls `data/send-instructions/` and host-delivers `feishu` notifications in-process
- includes tool-assisted planning runtime hooks, planning ops views, and planning acceptance helpers for Phase 6 minimum closure

This package now bundles its runtime and config assets directly:

- `scripts/runtime/`
- `config/`
- generated runtime state under `data/`

Useful bundled runtime entrypoints now include:

- `python3 scripts/runtime/main_ops.py planning --json`
- `python3 scripts/runtime/main_ops.py dashboard --only-issues`
- `python3 scripts/runtime/main_ops.py triage --json`
- `python3 scripts/runtime/check_task_user_content_leaks.py --json`
- `python3 scripts/runtime/check_task_user_content_leaks.py --since 2026-04-11T12:18:34+08:00 --json`
- `python3 scripts/runtime/planning_acceptance.py --json`
- `python3 scripts/runtime/create_planning_acceptance_record.py --json`
- `python3 scripts/runtime/prepare_planning_acceptance.py --json`
- `python3 scripts/runtime/capture_planning_acceptance_artifacts.py --json`
- `python3 scripts/runtime/run_planning_acceptance_bundle.py --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --json`
- `python3 scripts/runtime/plugin_install_drift.py --json`
- `python3 scripts/runtime/main_ops.py plugin-install-drift --json`
- `python3 scripts/runtime/stable_acceptance.py --json`

That means the installed extension directory can act as a self-contained runtime root,
without hard-coding a local project path in OpenClaw config.

Install drift is no longer only a standalone diagnostic:

- `dashboard --only-issues` now surfaces drift counts directly
- drift-only install problems now also mark `dashboard` as `warn`
- `triage --json` can prioritize install drift when no higher-priority blocked/planning action exists
