# Establish Milestone 3 Performance Baseline

## Problem

Milestone 3 had already been activated in roadmap and control-surface docs, but the repo still lacked the thing the milestone actually needed:

- one durable benchmark contract
- one reproducible measurement command
- one first hotspot ranked by evidence instead of intuition

Without that, any “performance work” would have reopened the same old problem: tuning whichever path happened to feel slow.

## Key Thinking

The first goal was not broad optimization.

It was measurement closure:

- define a repo-local benchmark surface first
- keep fixtures controlled so host-install drift and other accidental host state do not pollute the first budgets
- capture a real baseline and only then optimize the hottest measured path

That meant the first benchmark surface had to stay narrow enough to be reproducible, but still representative enough to cover runtime, same-session routing, control-plane projection, and repo-local operator entrypoints.

## Solution

Opened Milestone 3 in three layers:

1. benchmark contract
- added `scripts/runtime/performance_baseline.py` as the first benchmark / profile entrypoint
- documented the first benchmark surface, fixtures, budgets, and reviewed results in `docs/reference/openclaw-task-system/performance-baseline*.md`
- exposed the new reference in `README*` and linked it from the Milestone 3 development plan

2. baseline capture
- captured the first repo-local baseline for `hooks-cycle`, `same-session-routing-rule`, `same-session-routing-classifier`, `system-overview`, `growware-preflight`, and `plugin-smoke`
- identified `system-overview` as the first clear hotspot
- confirmed from profile output that `build_system_overview -> build_status_summary -> build_queue_snapshot -> _build_base_status_summary` was expanding the same inflight set repeatedly

3. first optimization and regression gate
- changed `task_status.py` so inflight base status is loaded once and one queue snapshot is reused across overview / list paths
- reduced the reviewed `system-overview` fixture from roughly `484ms` median to about `18ms` median
- added structural regression tests so `list_inflight_statuses` and `build_system_overview` load each inflight task only once

## Validation

- `python3 scripts/runtime/performance_baseline.py --profile-scenario hooks-cycle --profile-scenario same-session-routing-classifier --profile-scenario system-overview --profile-top 8 --enforce-budgets --json`
- `PYTHONPATH="$PWD:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}" python3 -m unittest tests.test_task_status tests.test_health_report tests.test_main_ops tests.test_performance_baseline -v`
- `python3 scripts/runtime/growware_preflight.py --json`
- `python3 scripts/runtime/growware_openclaw_binding.py --json`
- `python3 scripts/runtime/runtime_mirror.py --write`
- `bash scripts/run_tests.sh`
- `python3 scripts/runtime/plugin_doctor.py --json`
- `python3 scripts/runtime/plugin_smoke.py --json`

## Follow-Up

The first benchmark contract is now real and green, so the next performance slice should stay measured:

- rank the next hotspot between `task_state.find_inflight_tasks` / `list_inflight_tasks` and the same-session classifier subprocess path
- expand the benchmark surface toward repo-local `main_ops` / `plugin_doctor` slices only after host-state noise is isolated
- keep the installed OpenClaw runtime drift separate from repo-local baseline work unless a deliberate local deploy is requested
