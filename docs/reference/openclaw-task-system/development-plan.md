[English](development-plan.md) | [中文](development-plan.zh-CN.md)

# Development Plan

## Purpose

This plan bridges the roadmap and `.codex/plan.md`.

Use it when maintainers need one durable place to answer:

- what the most recent project-level milestone closed
- what was required to close it
- when a new project-level milestone should be opened again

## Current Position

The repo has now completed:

- Phase 0-6 minimum closure
- architecture hardening closeout
- bilingual public-doc convergence
- `Milestone 1: post-hardening closeout`

No newer project-level milestone is active today.

This plan now records the completed closeout milestone and the rule for opening the next one.

## Milestone Overview

| Milestone | Status | Objective | Validation | Exit Condition |
| --- | --- | --- | --- | --- |
| Milestone 1: post-hardening closeout | complete | close the remaining compound/future-first boundary work, deepen release-facing evidence, and leave the repo in a clean post-hardening state | `bash scripts/run_tests.sh`, `python3 scripts/runtime/release_gate.py --json`, planning / channel / main-ops acceptance helpers, docs consistency checks | boundary docs, acceptance depth, and operator/release-facing closeout are converged without reopening architecture debt |

## Completed Closeout Queue

### 1. Boundary Convergence

Delivered:

- compound follow-up docs now describe the shipped runtime boundary instead of an open design placeholder
- output-channel separation docs now match the current runtime contract instead of treating `task_user_content` as the active long-term protocol
- same-session routing decision docs now describe `collect-more` as a shipped non-task path
- user-visible versus runtime-owned status projection is described consistently across the active docs stack

Result:

- docs and runtime behavior now describe the same boundary
- the active docs stack no longer depends on "temporary" or "open boundary" wording to explain shipped behavior

### 2. Evidence Depth

Delivered:

- planning acceptance now proves that a scheduled follow-up summary stays in control-plane projection instead of leaking into business content
- channel acceptance now includes an explicit bounded-focus sample for `webchat`
- main-ops acceptance now includes `followup-task-missing` operator recovery projection alongside the earlier anomaly and watchdog samples

Result:

- release-facing acceptance depth no longer depends on summary-only wording for the remaining risky areas

### 3. Operator And Release-Facing Closeout

Delivered:

- operator and release-facing docs now point to the same validation entrypoints
- roadmap, README, todo intake, and control-surface docs all describe the same post-closeout state
- archive and promotion guidance remain aligned with the repo's planning evidence workflow

Result:

- operators can recover, triage, and validate from one coherent command set
- release-facing docs no longer point at half-finished or duplicated guidance

### 4. Next Activation Rule

Open a new project-level milestone only when all of the following are true:

1. extension work graduates from `docs/todo.md` into a named roadmap candidate
2. the candidate has explicit validation and exit conditions
3. the repo would otherwise start carrying generic follow-up debt again

Until then, use `roadmap.md`, `test-plan.md`, and `.codex/status.md` as the steady-state entrypoints.

## Validation Stack

Validation that closed this milestone:

```bash
bash scripts/run_tests.sh
python3 scripts/runtime/release_gate.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
python3 scripts/runtime/channel_acceptance.py --json
python3 scripts/runtime/main_ops_acceptance.py --json
```

Use additional real or semi-real evidence capture when a future change touches delivery or planning contracts directly.
