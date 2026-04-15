[English](development-plan.md) | [中文](development-plan.zh-CN.md)

# Development Plan

## Purpose

This plan is the human-facing execution layer under the roadmap.

Use it when maintainers need one durable place to answer:

- what the last completed milestone closed
- why the current active phase is this line
- what still must be true before the next live activation step begins

## Overall Progress

| Item | Current Value |
| --- | --- |
| Mainline Progress | Mainline is complete through `Milestone 3`; the active work has moved into reply-latency and context-weight governance before activation prep resumes |
| Current Phase | `reply-latency and context-weight governance` |
| Current Objective | turn the measured Telegram slowdown into durable repo truth, add repeatable session-latency audits, and bound the biggest context contributors before activation prep returns |
| Clear Next Move | `TG-1` freeze the slowdown trigger and add a reusable session-latency audit command |
| Next Candidate Move | resume bounded `feishu6-chat` activation preparation after context budgets and resume criteria are explicit |

## Topic Governance Progress

| Order | Task | Status |
| --- | --- | --- |
| 1 | TG-1 freeze the slowdown trigger and add `session_latency_audit.py` for turn timing and context-weight evidence | in progress |
| 2 | TG-2 rank and reduce the top context contributors: tool schema surface, system prompt weight, per-turn wrapper, and startup transcript carryover | queued |
| 3 | TG-3 define the activation-resume criteria and the evidence package that proves the slowdown is no longer a mainline blocker | queued |

## Current Position

The repo has completed:

- Phase 0-6 minimum closure
- architecture hardening closeout
- bilingual public-doc convergence
- `Milestone 1: post-hardening closeout`
- `Milestone 2: Growware Project 1 pilot foundation`

The active project-level phase is now:

- `reply-latency and context-weight governance`

Milestone 2 is closed because the Growware pilot control surface, policy compilation layer, validation entrypoints, binding preview, and read-only host-audit bootstrap are now durable repo truth, and legacy `.growware/policies/*.json` is retired from live runtime / preflight dependency.

Milestone 3 is now also closed because the repo has a reproducible benchmark contract, reviewed hotspot attribution, measured optimizations, and regression gates for the improved paths.

## Current Next Step

| Next Move | Why |
| --- | --- |
| `TG-1` freeze the slowdown trigger and add a reusable session-latency audit command | The repo has already closed the task-runtime hotspot milestone, but host-observed sessions still show user-visible reply slowness without a durable, rerunnable audit entrypoint. |

## Milestone Overview

| Milestone | Status | Objective | Validation | Exit Condition |
| --- | --- | --- | --- | --- |
| Milestone 1: post-hardening closeout | complete | close the remaining compound / future-first boundary work, deepen release-facing evidence, and leave the repo in a clean post-hardening state | `bash scripts/run_tests.sh`, `python3 scripts/runtime/release_gate.py --json`, planning / channel / main-ops acceptance helpers, docs consistency checks | boundary docs, acceptance depth, and operator / release-facing closeout are converged without reopening architecture debt |
| Milestone 2: Growware Project 1 pilot foundation | complete | turn Growware `Project 1` from a candidate into a durable repo-owned baseline with project-local policy truth, activation gates, and host-audit bootstrap | Growware policy sync / preflight / binding preview, targeted Growware tests, `bash scripts/run_tests.sh`, runtime mirror, doctor / smoke, and docs alignment | compiled `.policy` is the only live runtime input, activation safety is documented and green, and host-audit scope is explicitly bounded |
| Milestone 3: system performance testing and optimization | complete | establish reproducible performance baselines first, then optimize the measured hotspots | current runtime safety validation stack, performance entrypoints, baseline sample data, and benchmark / profile artifacts | benchmark and profile baselines exist, hotspots are attributed, optimizations are verified, and regression gates protect the improved paths |

## Milestone 2: Growware Project 1 Pilot Foundation

### 1. Project-Local Truth And Policy Layer

Completed:

- `.growware/` records Growware `Project 1`, `feishu6-chat`, and the project-local contracts / ops surface
- `docs/policy/*.md` is the human policy source and `.policy/` is the compiled machine execution layer
- `growware_policy_sync.py` compiles policy docs into manifest / index / rule artifacts
- `growware_project.py` exposes policy manifest / index / rule data in the project summary
- `growware_feedback_classifier.py`, `growware_preflight.py`, and `growware_local_deploy.py` are converged on the compiled policy layer
- legacy `.growware/policies/*.json` is retired and no longer required as a live runtime / preflight input

### 2. Validation And Pilot Activation Safety

Completed:

- `growware_preflight.py` checks `policy-sync`
- `growware_local_deploy.py` runs policy sync write + check before runtime mirror and doctor
- install and usage docs surface `growware_policy_sync.py`, binding preview, and host-side audit commands
- plugin tests and Python tests are aligned to the current Growware policy path
- the reviewed baseline has been rerun on the same compiled `.policy/` path across policy sync, preflight, binding preview, runtime mirror, doctor / smoke, targeted Growware tests, and the repo-wide test stack

### 3. Host-Side Audit Bootstrap

Completed:

- `openclaw_runtime_audit.py` inspects recent tasks, stale running tasks, failed deliveries, cron events, config health, and user-visible excerpts from real `~/.openclaw` data
- `tests/test_openclaw_runtime_audit.py` proves stale-task, failed-delivery, cron-error, and user-visible noise filtering behavior
- the audit boundary is frozen as read-only bootstrap evidence, not a silent repair tool and not the default rollout gate for the next phase

### 4. Closeout Result

Milestone 2 is complete because all four closeout signals are now true:

1. compiled `.policy` is the only live intake / deploy truth the runtime depends on
2. policy sync, preflight, binding preview, targeted Growware tests, runtime mirror, doctor, and smoke all pass on the same reviewed baseline
3. session hygiene for the dedicated `growware` production session is documented through tools and operator guidance instead of informal memory
4. roadmap, development-plan, and `.codex/*` explicitly record host-side audit as bootstrap evidence and open the next phase as performance work

## Milestone 3: System Performance Testing And Optimization

### 1. Benchmark Contract

Completed:

- `scripts/runtime/performance_baseline.py` now defines one reproducible repo-local benchmark / profile contract for runtime, same-session routing, control-plane projection, and operator entrypoints
- `docs/reference/openclaw-task-system/performance-baseline*.md` fix the reviewed fixtures, budgets, commands, and profile vocabulary in durable repo truth
- the first benchmark surface stays repo-local by design, so host-install drift is visible but not mixed into the baseline itself

### 2. Measured Hotspot Reductions

Completed:

- `task_status.py` moved the reviewed `system-overview` fixture from roughly `484ms` median to about `18ms`
- `task_state.py`, `openclaw_bridge.py`, and `main_task_adapter.py` collapsed repeated registration rescans to one inflight snapshot / shared store on the hot path
- `openclaw_hooks.py` now runs the repo-owned Growware same-session classifier in-process, moving the reviewed classifier path from about `90.0957ms` median / `132.2014ms` p95 to about `24.9839ms` / `38.5312ms`

### 3. Regression Protection And Validation

Completed:

- `tests/test_task_status.py`, `tests/test_task_state.py`, `tests/test_openclaw_bridge.py`, `tests/test_main_task_adapter.py`, `tests/test_openclaw_hooks.py`, and `tests/test_performance_baseline.py` now protect the measured paths structurally
- the reviewed repo-local validation baseline has been rerun across benchmark, preflight, binding preview, runtime mirror, the full testsuite, doctor, and smoke
- installed-runtime drift remains visible in `plugin_doctor.py` instead of being hidden inside a repo-local performance milestone

### 4. Closeout Result

Milestone 3 is complete because all four closeout signals are now true:

1. a reproducible benchmark / profile contract exists in durable repo truth
2. the main hotspots are attributed with reviewed before / after evidence
3. the improved paths are protected by benchmark budgets and structural regression checks
4. the repo kept runtime truth, activation boundaries, and the existing validation stack green while landing the measured cuts

## Reply-Latency And Context-Weight Governance

### Trigger Evidence

This topic exists because a real Telegram session after `2026-04-15 23:44` showed user-visible reply latency even though the repo-local performance baseline remained green.

The measured trigger is:

- turn durations of roughly `16s-50s`
- dominant latency share in LLM segments rather than task-system hook time
- static context of about `140,465 chars`
- user payload wrappers of about `1.5k chars` per turn
- startup and transcript growth that keep adding cost to later turns

### Immediate Execution Line

The governance topic breaks into three steps:

1. freeze the evidence
   - add one reusable command that audits a real session's turn timing, LLM/tool shares, transcript growth, and static prompt composition
   - stop relying on manual one-off log dissection

2. rank the largest context contributors
   - separate tool schema surface, system prompt weight, workspace bootstrap, per-turn wrappers, and transcript carryover
   - decide which contributors must stay, which can shrink, and which should move out of later turns

3. define the activation resume gate
   - record what evidence proves the user-visible slowdown is no longer a mainline blocker
   - only then return to bounded activation preparation

### Governance Rules

This topic has four rules:

1. keep `performance_baseline.py` green; repo-local hotspot work stays closed unless a measured regression reopens it
2. use `session_latency_audit.py` for host-observed session slowdowns instead of arguing from anecdotes
3. do not cut prompt/context blindly; every reduction must cite what cost it removes and what behavior risk it introduces
4. do not resume activation prep until reply-latency evidence, resume criteria, and rollback expectations are explicit

### First Optimization Queue

- tool schema surface: currently the largest static contributor in the measured Telegram session
- system prompt weight: the second-largest static contributor and the biggest repo-owned non-tool block
- per-turn wrapper tax: short user requests currently arrive as `~1.5k`-char payloads
- startup transcript carryover: startup file reads spill into later turns and raise the cost of the first business question
- transcript growth discipline: later turns continue paying for earlier injected material

### Activation Resume Criteria

Activation preparation may return as the mainline only after all of the following are true:

- the slowdown trigger can be rerun through a reviewed audit command
- the top prompt/context contributors have explicit keep / shrink / remove decisions
- the chosen cuts keep runtime safety and required agent capability intact
- the repo records what evidence is sufficient to treat reply latency as bounded rather than open-ended

## Bounded Live Pilot Activation Preparation

### Entry Rules

This next phase is no longer active. It returns only after the governance topic closes its trigger conditions.

When it resumes, it must still obey three rules:

1. keep `performance_baseline.py` as an ongoing guardrail; do not reopen broad tuning without a measured regression
2. decide explicitly whether installed-runtime drift should be cleared through a deliberate local deploy before the first bounded rehearsal
3. keep activation rehearsal scoped to approved `feishu6-chat` evidence capture, rollback boundaries, and current runtime truth

### Immediate Execution Line

The next line breaks into three steps:

1. define activation entry criteria and the operator evidence package
   - decide which repo-local and host-visible signals must be captured before or during rehearsal
   - keep the activation story tied to the reviewed benchmark and validation baseline

2. decide the install-sync path
   - determine whether the current installed-runtime drift should be cleared before the first rehearsal
   - keep any `growware_local_deploy.py --json` use explicit instead of implying it from repo-only work

3. stage the first bounded rehearsal
   - define rollback criteria, evidence capture, and the rule for when a newly observed slowdown re-enters the performance line

### Recommended Entry Criteria

- the reviewed repo-local performance baseline stays green
- the Milestone 2 runtime-safety validation stack remains green
- activation evidence, rollback boundaries, and install-sync intent are recorded before any live rehearsal
- carry-forward performance hotspots stay backlog candidates unless activation evidence turns them into a measured blocker

## Validation Stack

Keep the repo-local performance baseline and the Growware runtime-safety baseline green while running the governance topic and later entering activation preparation:

```bash
python3 scripts/runtime/performance_baseline.py --profile-scenario hooks-cycle --profile-scenario same-session-routing-classifier --profile-scenario system-overview --profile-top 8 --enforce-budgets --json
python3 scripts/runtime/session_latency_audit.py --session-key 'agent:main:telegram:direct:8705812936' --json
python3 scripts/runtime/growware_policy_sync.py --write --json
python3 scripts/runtime/growware_preflight.py --json
python3 scripts/runtime/growware_openclaw_binding.py --json
python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_policy_sync tests.test_growware_preflight tests.test_growware_project tests.test_openclaw_runtime_audit tests.test_session_latency_audit -v
bash scripts/run_tests.sh
python3 scripts/runtime/runtime_mirror.py --write
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
```

Use `python3 scripts/runtime/growware_local_deploy.py --json` only when the current change is deliberately meant to refresh the installed OpenClaw runtime before rehearsal.
