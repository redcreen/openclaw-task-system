# Project Status

## Delivery Tier

- Tier: `large`
- Why this tier: the repo now spans runtime behavior, host-observed session analysis, prompt/context governance, durable public docs, and activation-resume gating
- Last reviewed: 2026-04-16

## Current Phase

`reply-latency and context-weight governance` is active.

Milestone 2 and Milestone 3 stay complete and should not be reopened as partial-migration or open-ended tuning lines. The active work is a measured governance topic on top of those closed milestones.

## Active Slice

`session-latency evidence frozen + prompt-surface governance bootstrap`

## Current Execution Line

- Objective: turn the measured Telegram slowdown into durable repo truth, add repeatable session-level audits, and bound the biggest context contributors before activation prep resumes
- Plan Link: `docs/reference/openclaw-task-system/development-plan.md#reply-latency-and-context-weight-governance`
- Runway: keep `performance_baseline.py` green, use `session_latency_audit.py` for host-observed cases, and avoid mixing provider variance with repo-owned context bloat
- Progress: `1/3` tasks complete
- Stop Conditions: docs disagree on the active topic, session-level evidence is not reproducible, or activation prep quietly returns without explicit resume criteria

## Execution Tasks

- [x] TG-1 add a durable session-latency audit entrypoint and freeze the current slowdown trigger into public/control-surface truth
- [ ] TG-2 rank and reduce the top context contributors: tool schema surface, system prompt weight, per-turn wrapper, and startup transcript carryover
- [ ] TG-3 define activation-resume criteria and the evidence needed to prove reply latency is no longer a mainline blocker

## Architecture Supervision

- Signal: `yellow`
- Signal Basis: repo-local benchmark evidence is still green, but host-observed sessions show user-visible LLM latency under oversized prompt/context surfaces
- Root Cause Hypothesis: the dominant remaining cost sits in static prompt weight, per-turn wrappers, and transcript carryover rather than the repo's hot-path task hooks
- Correct Layer: keep repo-local performance milestone closed, and run a dedicated governance topic for context slimming plus activation-resume criteria
- Automatic Review Trigger: any change to prompt composition, workspace bootstrap files, startup read behavior, tool exposure, session wrappers, or activation-resume gates
- Escalation Gate: continue automatically

## Current Escalation State

- Current Gate: continue automatically
- Reason: the current topic stays inside repo-owned evidence, tooling, and docs governance; it does not by itself launch live rehearsal or change host install state
- Next Review Trigger: review again before any local deploy, live rehearsal, or reduction that intentionally removes safety / memory context

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
- the repo now has a dedicated session-level latency audit entrypoint in `scripts/runtime/session_latency_audit.py`
- `tests/test_session_latency_audit.py` protects turn timing, static prompt summarization, and session metadata lookup
- the repo's active mainline is now reply-latency and context-weight governance rather than immediate activation preparation

## In Progress

- freezing the current Telegram slowdown into durable docs, control-surface truth, and a reusable audit command
- ranking which context contributors are worth cutting first without weakening required safety or memory behavior
- defining what evidence allows activation preparation to return as the next bounded phase

## Blockers / Open Decisions

- how aggressively tool schema exposure can be reduced without breaking main-agent capability
- whether startup reads should stay in transcript, become summarized state, or be removed from later turns entirely
- what concrete latency/context budget is sufficient to declare activation prep unblocked again

## Next 3 Actions

1. Publish the governance topic and session-audit command into development-plan, reference docs, and devlog.
2. Use the new audit output to freeze the optimization queue for tool schema surface, system prompt weight, wrappers, and startup carryover.
3. Define the activation-resume gate so the repo knows when to leave this topic and return to bounded activation prep.

## Development Log Capture

- Trigger Level: high
- Pending Capture: yes
- Reason: this turn changes the active mainline, adds reusable latency-audit tooling, and opens a new durable governance topic
- Last Entry: docs/devlog/2026-04-14-close-milestone3-performance-optimization.md
