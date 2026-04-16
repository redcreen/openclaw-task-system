# Project Status

## Delivery Tier

- Tier: `large`
- Why this tier: the repo now spans runtime behavior, user-visible task supervision, and runtime-owned control-plane semantics
- Last reviewed: 2026-04-16

## Current Phase

`wd reliability and task usefulness convergence` is active.

Milestone 2 and Milestone 3 stay complete. The active work is back on runtime usefulness rather than performance/doc side-track work.

## Active Slice

`wd receipt truthfulness and terminal usefulness`

## Current Execution Line

- Objective: improve runtime-owned `wd` behavior so the product is materially more useful in real usage, and remove the recent public-doc side track from this project's mainline
- Plan Link: `runtime usefulness / wd`
- Runway: use today's host logs as the source of truth, keep the fixes in runtime-owned hooks/renderers, and validate against targeted tests plus doctor / smoke / local deploy
- Progress: `docs side-track removed; wd wording and terminal usefulness slice in progress`
- Stop Conditions: `wd` still misstates queue reality, terminal messages remain low-value, or the work drifts back into unrelated public-doc governance

## Execution Tasks

- [x] WU-1 remove the public-doc performance side-track from the project's active line
- [ ] WU-2 fix misleading queue/start `wd` receipts
- [ ] WU-3 reduce low-value terminal follow-ups

## Architecture Supervision

- Signal: `yellow`
- Signal Basis: today's host logs still show runtime-owned `wd` messages that are inaccurate or add little user value
- Root Cause Hypothesis: queue receipts still overfit internal counters, and generic terminal messages are allowed through when they do not help the user
- Correct Layer: tighten runtime-owned rendering rules instead of opening another performance or documentation track
- Automatic Review Trigger: any change to receipt wording, queue-state interpretation, terminal control-plane policy, or transcript/user-content sanitization
- Escalation Gate: continue automatically

## Current Escalation State

- Current Gate: continue automatically
- Reason: the current slice stays inside repo-owned runtime behavior and local verification
- Next Review Trigger: review again before any broader product-semantics change beyond `wd` truthfulness and usefulness

## Done

- Phase 0-6 minimum closure and `Milestone 1: post-hardening closeout` remain complete
- `Milestone 2: Growware Project 1 pilot foundation` is now complete
- `.growware/` acts as the durable project-local control surface for Growware `Project 1`
- `docs/policy/*.md` and `.policy/` establish the human-source plus compiled-machine-layer policy model
- `growware_feedback_classifier.py`, `growware_project.py`, `growware_preflight.py`, and `growware_local_deploy.py` consume or enforce the compiled policy layer
- legacy `.growware/policies/*.json` has been retired from live runtime / preflight dependency
- install, usage, roadmap, development-plan, and host resume views now treat Milestone 2 and Milestone 3 as closed, and activation preparation as the active mainline
- `openclaw_runtime_audit.py` remains a read-only host-side audit bootstrap with test coverage for stale tasks, failed deliveries, cron errors, and user-visible noise filtering
- `scripts/run_tests.sh` uses deterministic Python discovery and serial Node plugin tests for the current runtime / plugin suite
- `scripts/runtime/performance_baseline.py` now defines the first repo-local benchmark surface, fixtures, budgets, and profile entrypoint for Milestone 3
- `docs/reference/openclaw-task-system/performance-baseline*.md` now records the benchmark contract, first baseline, hotspot attribution, and first optimization
- `task_status.py` now reuses preloaded inflight state and a shared queue snapshot, moving `system-overview` from roughly `484ms` median to about `18ms` median on the reviewed fixture
- `tests/test_task_status.py` now protects the optimization structurally by asserting one inflight load per task for `list_inflight_statuses` and `build_system_overview`
- `task_state.py` now caches inflight task loads within one store instance and invalidates that cache on write paths
- `openclaw_bridge.py` and `main_task_adapter.py` now register or resume tasks from one inflight snapshot / shared store instead of repeatedly rebuilding active / observed / queue views during the same registration flow
- `tests/test_task_state.py` and `tests/test_openclaw_bridge.py` now protect inflight-cache invalidation and single-snapshot registration behavior structurally
- `openclaw_hooks.py` now runs the repo-owned Growware same-session classifier in-process instead of spawning a subprocess for each natural-language follow-up, while custom classifier commands keep the existing subprocess path
- the reviewed same-session classifier hotspot moved from roughly `90.0957ms` median / `132.2014ms` p95 to about `24.9839ms` median / `38.5312ms` p95 on the focused follow-up fixture
- `tests/test_openclaw_hooks.py` now protects the repo-owned classifier fast path by asserting that it does not fall back to `subprocess.run`
- Milestone 3 is now closed on reviewed benchmark evidence, regression gates, and a green repo-local validation baseline
- the runtime already owns `[wd]`, follow-up, watchdog, continuity, and terminal control-plane projection
- the recent public-doc performance side-track has been removed from the active project line

## In Progress

- fixing queue/start receipts that currently imply the wrong backlog state
- making terminal completion messages stay concise unless they carry real summary value
- validating the installed plugin behavior against today's host-log issue pattern

## Blockers / Open Decisions

- where terminal `wd` should stay generic versus carrying a task-specific summary
- whether any remaining host-log issue points to rendering only, or to deeper scheduler/state mistakes
- how much queue detail is actually useful to users before it turns into noise

## Next 3 Actions

1. Finish the `wd` receipt wording fix and verify it against targeted tests plus host behavior.
2. Keep terminal completions sparse unless they carry a real result summary.
3. Re-check today's log pattern after local deploy to confirm the user-visible behavior actually improved.

## Development Log Capture

- Trigger Level: high
- Pending Capture: yes
- Reason: this turn changes the active mainline, adds reusable latency-audit tooling, and opens a new durable governance topic
- Last Entry: docs/devlog/2026-04-14-close-milestone3-performance-optimization.md
