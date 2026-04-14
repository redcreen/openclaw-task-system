[English](development-plan.md) | [中文](development-plan.zh-CN.md)

# Development Plan

## Purpose

This plan bridges the roadmap and `.codex/plan.md`.

Use it when maintainers need one durable place to answer:

- what the last completed milestone closed
- why the current active phase is this line
- what still must be true before the next live activation step begins

## Current Position

The repo has completed:

- Phase 0-6 minimum closure
- architecture hardening closeout
- bilingual public-doc convergence
- `Milestone 1: post-hardening closeout`
- `Milestone 2: Growware Project 1 pilot foundation`

The active project-level phase is now:

- `Milestone 3: system performance testing and optimization`

Milestone 2 is closed because the Growware pilot control surface, policy compilation layer, validation entrypoints, binding preview, and read-only host-audit bootstrap are now durable repo truth, and legacy `.growware/policies/*.json` is retired from live runtime / preflight dependency.

Milestone 3 should not reopen foundation semantics. Its job is to establish reproducible, attributable, regression-safe performance baselines before live activation, operator ergonomics, or self-heal discussions expand further.

## Milestone Overview

| Milestone | Status | Objective | Validation | Exit Condition |
| --- | --- | --- | --- | --- |
| Milestone 1: post-hardening closeout | complete | close the remaining compound / future-first boundary work, deepen release-facing evidence, and leave the repo in a clean post-hardening state | `bash scripts/run_tests.sh`, `python3 scripts/runtime/release_gate.py --json`, planning / channel / main-ops acceptance helpers, docs consistency checks | boundary docs, acceptance depth, and operator / release-facing closeout are converged without reopening architecture debt |
| Milestone 2: Growware Project 1 pilot foundation | complete | turn Growware `Project 1` from a candidate into a durable repo-owned baseline with project-local policy truth, activation gates, and host-audit bootstrap | Growware policy sync / preflight / binding preview, targeted Growware tests, `bash scripts/run_tests.sh`, runtime mirror, doctor / smoke, and docs alignment | compiled `.policy` is the only live runtime input, activation safety is documented and green, and host-audit scope is explicitly bounded |
| Milestone 3: system performance testing and optimization | active | establish reproducible performance baselines first, then optimize the measured hotspots | current runtime safety validation stack, performance entrypoints, baseline sample data, and benchmark / profile artifacts | benchmark and profile baselines exist, hotspots are attributed, optimizations are verified, and regression gates protect the improved paths |

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

### Active Rules

This active phase has three rules:

1. measure first and optimize second; no intuition-driven tuning without a baseline
2. standardize sample data and command entrypoints before debating hotspots
3. do not break the runtime truth, activation boundary, or validation stack that Milestone 2 just closed

### Immediate Execution Line

The current line breaks into four steps:

1. define the benchmark surface and budgets
   - cover runtime register / resolve-active / progress / finalize
   - cover same-session routing and classifier invocation
   - cover control-plane enqueue / delivery / queue projection
   - cover operator entrypoints such as `main_ops.py`, `plugin_doctor.py`, `plugin_smoke.py`, and `growware_preflight.py`

2. build reproducible measurement entrypoints
   - fix sample data, environment assumptions, and command entrypoints
   - avoid baselines that depend on accidental host state

3. capture the first baseline and attribute hotspots
   - produce benchmark / profile output
   - rank the main hotspots by impact and scope

4. land the first evidence-backed optimization and regression gate
   - every optimization must include before / after comparison
   - at least the critical paths should enter a scripted regression check

### Recommended Scope

- runtime register / resolve-active / progress / finalize paths
- same-session routing and classifier invocation paths
- control-plane enqueue / delivery / queue projection
- task store, SQLite, file scans, and log-read hotspots
- operator entrypoints such as `main_ops.py`, `plugin_doctor.py`, `plugin_smoke.py`, and `growware_preflight.py`

### Recommended Exit Condition

- at least one reproducible benchmark / profile baseline exists
- the main hotspots are attributed instead of only observing “it feels slow”
- every optimization has before / after evidence
- performance regression checks are wired into a scripted gate or stable validation entrypoint

## Validation Stack

Keep the Milestone 2 runtime-safety baseline green while opening Milestone 3:

```bash
python3 scripts/runtime/growware_policy_sync.py --write --json
python3 scripts/runtime/growware_preflight.py --json
python3 scripts/runtime/growware_openclaw_binding.py --json
python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_policy_sync tests.test_growware_preflight tests.test_growware_project tests.test_openclaw_runtime_audit -v
bash scripts/run_tests.sh
python3 scripts/runtime/runtime_mirror.py --write
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
```

Use `python3 scripts/runtime/growware_local_deploy.py --json` only when the current change is meant to be locally deployed into OpenClaw, not for repo-only performance-baseline work.
