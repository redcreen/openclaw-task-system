[English](README.md) | [中文](README.zh-CN.md)

# Architecture Hardening

## Current Status

This workstream is now in closeout rather than open-ended diagnosis.

The repo has adopted two explicit hardening decisions:

- `lifecycle_coordinator.py` owns runtime lifecycle projection
- `scripts/runtime/` is the only canonical editable runtime tree, while `plugin/scripts/runtime/` is a strict synchronized mirror

Enforcement now comes from:

- `python3 scripts/runtime/runtime_mirror.py --check`
- `python3 scripts/runtime/plugin_doctor.py`
- `bash scripts/run_tests.sh`
- `bash scripts/install_remote.sh`

## Why This Workstream Exists

The Phase 0-6 mainline is already shipped, but the implementation still carries two structural debts:

- task lifecycle ownership is split across plugin hook orchestration, runtime hook commands, and task mutation helpers
- runtime logic exists in both `scripts/runtime/` and `plugin/scripts/runtime/`, with drift tooling acting as a guardrail instead of removing the duplicated ownership

This workstream exists to harden those boundaries before more feature work accumulates on top of them.

## Root-Cause Summary

The current architecture is not failing at the product-contract level. It is failing at the ownership level.

Symptoms include:

- repair-style logic after lifecycle races
- terminal state decisions spread across multiple layers
- large entrypoint files carrying too many responsibilities
- source/install drift treated as an operational concern instead of a design concern

## Target Boundary Model

The hardening target is:

1. `plugin ingress`
   - collect OpenClaw hook events
   - normalize channel/session metadata
   - call runtime-owned lifecycle entrypoints

2. `lifecycle coordinator`
   - own `register -> progress -> finalize -> terminal control-plane`
   - decide when a task becomes done / failed / blocked / awaiting-visible-output
   - produce runtime-owned receipts and terminal projections

3. `task truth-source layer`
   - provide durable task/session state mutation
   - remain storage-oriented, not orchestration-oriented

4. `projection / ops layer`
   - render the same truth for users and operators
   - stay downstream of lifecycle decisions rather than re-inferring them

## Runtime Source-of-Truth Goal

The runtime tree must have one canonical source.

Desired end state:

- one source runtime tree is edited directly
- install payload runtime files are generated or synchronized from that source
- install drift tooling remains as verification, not as the primary way maintainers reason about ownership

## Phased Retrofit

### Phase A: Lifecycle Contract Extraction

- define the lifecycle coordinator API and state transitions
- document which layer owns:
  - receipt creation
  - visible progress sync
  - finalize skip / retry rules
  - terminal control-plane projection

Exit signal:

- a maintainer can point to one boundary as the owner of task lifecycle decisions

### Phase B: Plugin Thinning

- move lifecycle decision logic out of `plugin/src/plugin/index.ts`
- keep plugin code focused on OpenClaw ingress, transport metadata, and host delivery concerns
- remove repair logic that only exists because lifecycle ownership is split

Exit signal:

- plugin-side lifecycle repair paths are measurably reduced

### Phase C: Runtime Canonicalization

- choose the canonical runtime tree
- make the second runtime tree generated or strictly synchronized
- document the packaging/install flow around that choice

Exit signal:

- maintainers no longer treat `scripts/runtime` and `plugin/scripts/runtime` as peer-owned sources

### Phase D: Resume Feature Work

- continue planning anomaly coverage
- continue planning/channel acceptance expansion

Guardrail:

- no new feature should expand the old split-ownership pattern

## Non-Goals

- changing OpenClaw core
- replacing the executor/agent path with a new orchestrator
- expanding regex/phrase-list routing shortcuts

## Related Docs

- [../../architecture.md](../../architecture.md)
- [../../roadmap.md](../../roadmap.md)
- [../../todo.md](../../todo.md)
- [../../../.codex/status.md](../../../.codex/status.md)
- [../../../.codex/plan.md](../../../.codex/plan.md)
