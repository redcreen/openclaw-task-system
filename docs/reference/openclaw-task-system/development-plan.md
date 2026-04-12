[English](development-plan.md) | [中文](development-plan.zh-CN.md)

# Development Plan

## Purpose

This plan bridges the roadmap and `.codex/plan.md`.

Use it when maintainers need one durable place to answer:

- what the next project-level milestone is
- how that milestone should be executed
- what must be verified before the repo can call the slice closed

## Current Position

The repo has already completed:

- Phase 0-6 minimum closure
- architecture hardening closeout
- bilingual public-doc convergence

The next project-level milestone is:

- `Milestone 1: post-hardening closeout`

This milestone should be executed as one uninterrupted long-task line rather than reopened as many small cleanup slices.

## Milestone Overview

| Milestone | Status | Objective | Validation | Exit Condition |
| --- | --- | --- | --- | --- |
| Milestone 1: post-hardening closeout | next | close the remaining compound/future-first boundary work, deepen release-facing evidence, and leave the repo in a clean post-hardening state | `bash scripts/run_tests.sh`, `python3 scripts/runtime/release_gate.py --json`, planning / channel / main-ops acceptance helpers, docs consistency checks | remaining work is either shipped, archived, or explicitly moved into a new roadmap candidate instead of lingering as generic follow-up |

## Ordered Execution Queue

### 1. Boundary Convergence

Close the product and runtime boundary around:

- compound follow-up behavior
- future-first planning expectations
- output-channel separation
- user-visible versus runtime-owned status projection

Exit signal:

- docs and runtime behavior describe the same boundary
- no shipped behavior still depends on hand-wavy "temporary" wording in the active docs stack

### 2. Evidence Depth

Deepen release-facing evidence where the repo still calls out limited real-channel proof:

- planning acceptance evidence depth
- channel acceptance sample depth
- semi-real or real dated records where current docs explicitly say coverage is still thin

Exit signal:

- acceptance coverage no longer relies on a single dated record or summary-only wording for the remaining risky areas

### 3. Operator And Release-Facing Closeout

Finish the maintainer-facing closeout work:

- operator snapshot and runbook alignment
- release-gate wording and entrypoint alignment
- archive and promotion guidance consistency

Exit signal:

- operators can recover, triage, and validate from one coherent command set
- release-facing docs no longer point at half-finished or duplicated guidance

### 4. Final Closeout Pass

Do one final convergence pass before calling the milestone closed:

- refresh roadmap, todo, and active docs wording
- archive superseded temporary notes if needed
- capture a devlog or handoff only if the reasoning changed materially

Exit signal:

- the remaining backlog is explicit and small
- `.codex/status.md`, `.codex/plan.md`, roadmap, and test-plan all point at the same post-closeout state

## Execution Rule

Treat this milestone as one long-task execution line:

1. start from the first open queue item
2. continue automatically until a real blocker, checkpoint, or decision gate appears
3. avoid reopening already-closed slices just because they are nearby
4. only stop when the milestone can either be closed or deliberately split into a new named roadmap candidate

## Validation Stack

Minimum validation for milestone closeout:

```bash
bash scripts/run_tests.sh
python3 scripts/runtime/release_gate.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
python3 scripts/runtime/channel_acceptance.py --json
python3 scripts/runtime/main_ops_acceptance.py --json
```

Use additional real or semi-real evidence capture when the slice touches delivery or planning contracts directly.
