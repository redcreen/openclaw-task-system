[English](development-plan.md) | [中文](development-plan.zh-CN.md)

# Development Plan

## Purpose

This plan bridges the roadmap and `.codex/plan.md`.

Use it when maintainers need one durable place to answer:

- what the last completed milestone closed
- why a new milestone is now open
- what must be true before the next activation step begins

## Current Position

The repo has completed:

- Phase 0-6 minimum closure
- architecture hardening closeout
- bilingual public-doc convergence
- `Milestone 1: post-hardening closeout`

A new project-level milestone is now active:

- `Milestone 2: Growware Project 1 pilot foundation`

This milestone is open because the repo already contains real Growware pilot implementation work in docs, policy compilation, preflight / deploy gates, and host-side audit bootstrap. That work should be closed as an explicit milestone instead of remaining a future candidate.

## Milestone Overview

| Milestone | Status | Objective | Validation | Exit Condition |
| --- | --- | --- | --- | --- |
| Milestone 1: post-hardening closeout | complete | close the remaining compound / future-first boundary work, deepen release-facing evidence, and leave the repo in a clean post-hardening state | `bash scripts/run_tests.sh`, `python3 scripts/runtime/release_gate.py --json`, planning / channel / main-ops acceptance helpers, docs consistency checks | boundary docs, acceptance depth, and operator / release-facing closeout are converged without reopening architecture debt |
| Milestone 2: Growware Project 1 pilot foundation | active | turn Growware `Project 1` from a candidate into a durable repo-owned baseline with project-local policy truth, activation gates, and host-audit bootstrap | Growware policy sync / preflight / binding preview, targeted Growware tests, `bash scripts/run_tests.sh`, runtime mirror, doctor / smoke, and docs alignment | compiled `.policy` is the only live runtime input, activation safety is documented and green, and host-audit scope is explicitly bounded |

## Milestone 2: Growware Project 1 Pilot Foundation

### 1. Project-Local Truth And Policy Layer

Delivered:

- `.growware/` now records Growware `Project 1`, `feishu6-chat`, and the project-local contracts / ops surface
- `docs/policy/*.md` is now the human policy source and `.policy/` is the compiled machine execution layer
- `growware_policy_sync.py` compiles policy docs into manifest / index / rule artifacts
- `growware_project.py` now exposes policy manifest / index / rule data in the project summary
- `growware_feedback_classifier.py` now reads the compiled policy rule instead of depending on legacy prose or direct `.growware/policies` reads

Remaining to close:

- bound `.growware/policies/*.json` as compatibility-only inputs or retire any remaining live dependence on them
- keep install, mirror, preflight, and deploy flows converged on the same compiled policy truth

### 2. Validation And Pilot Activation Safety

Delivered:

- `growware_preflight.py` now checks `policy-sync`
- `growware_local_deploy.py` now runs policy sync write + check before runtime mirror and doctor
- install and usage docs now surface `growware_policy_sync.py` and host-side audit commands
- plugin tests and Python tests were refreshed to match the current Growware wording and policy path

Remaining to close:

- prove one clean operator baseline across `growware_policy_sync.py`, `growware_preflight.py`, `growware_openclaw_binding.py --json`, runtime mirror, doctor, smoke, and session hygiene guidance
- define what evidence is mandatory before the first real `feishu6-chat` activation step

### 3. Host-Side Audit Bootstrap

Delivered:

- `openclaw_runtime_audit.py` now inspects recent tasks, stale running tasks, failed deliveries, cron events, config health, and user-visible excerpts from real `~/.openclaw` data
- `tests/test_openclaw_runtime_audit.py` now proves stale-task, failed-delivery, cron-error, and user-visible noise filtering behavior
- the audit is documented as a read-only bootstrap, not a silent repair tool

Remaining to close:

- decide whether read-only audit is enough for Milestone 2 or whether repair planning should be promoted into the next named milestone
- keep the audit boundary separate from release gates until the host-side policy is explicit

### 4. Next Activation Gate

Move from foundation to live pilot activation only when all of the following are true:

1. compiled `.policy` is the only live intake / deploy truth the runtime depends on
2. `growware_policy_sync.py`, `growware_preflight.py`, `growware_openclaw_binding.py --json`, targeted Growware tests, runtime mirror, doctor, and smoke all pass on the same baseline
3. session hygiene for the dedicated `growware` production session is explicit and reproducible
4. the roadmap explicitly says whether host-side audit remains bootstrap evidence or becomes the next milestone

## Validation Stack

Current milestone validation should draw from this stack:

```bash
python3 scripts/runtime/growware_policy_sync.py --check --json
python3 scripts/runtime/growware_preflight.py --json
python3 scripts/runtime/growware_openclaw_binding.py --json
python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_policy_sync tests.test_growware_preflight tests.test_growware_project tests.test_openclaw_runtime_audit
bash scripts/run_tests.sh
python3 scripts/runtime/runtime_mirror.py --write
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
```

Use `python3 scripts/runtime/growware_local_deploy.py --json` only when the current change is meant to be locally deployed into OpenClaw, not for every repo-only review pass.
