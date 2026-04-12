# Project Plan

## Current Phase

Architecture hardening after Phase 6 mainline closure; runtime source-of-truth convergence complete.

## Current Execution Line
- Objective: define `scripts/runtime/` as the single canonical editable runtime tree, make `plugin/scripts/runtime/` a strict mirror, and wire that rule into docs and runtime tooling
- Plan Link: `runtime source-of-truth convergence`
- Runway: one checkpoint-sized convergence pass
- Progress: `6/6`
- Stop Conditions: runtime mirror enforcement fails, install flow can proceed with drift, or docs still leave canonical-source ownership ambiguous
- Validation: `./scripts/run_tests.sh`, `runtime_mirror.py --check`, `plugin_doctor.py`, and `deep`

## Execution Tasks
- [x] EL-1 refresh `.codex/architecture-retrofit.md`, `.codex/status.md`, and `.codex/plan.md` around runtime source ownership
- [x] EL-2 make repo docs explicitly state that `scripts/runtime/` is canonical and `plugin/scripts/runtime/` is a synchronized mirror
- [x] EL-3 wire runtime mirror enforcement into doctor / install / validation entrypoints
- [x] EL-4 align workstream and roadmap docs so architecture hardening no longer looks half-open
- [x] EL-5 write a durable devlog for the canonical-source decision
- [x] EL-6 rerun `deep` and `./scripts/run_tests.sh`

## Architecture Supervision
- Signal: `green`
- Signal Basis: lifecycle ownership and canonical runtime-source ownership are explicit in tooling, docs, and control surfaces
- Problem Class: architecture hardening closeout
- Root Cause Hypothesis: once lifecycle ownership moved into the coordinator, the remaining architectural ambiguity lived in dual runtime-tree ownership rather than missing code
- Correct Layer: runtime mirror tooling, install/doctor/test entrypoints, docs, and control surfaces
- Rejected Shortcut: keep treating `plugin/scripts/runtime/` as a peer-owned source and let drift tooling carry the semantic burden
- Escalation Gate: continue automatically

## Escalation Model
- Continue Automatically: refactors that preserve hook payload shape while reducing duplicated ownership
- Raise But Continue: source/install sync steps that still leave the canonical-source question open
- Require User Decision: any release-path or packaging change that changes how the plugin bundle is built or installed

## Slices
- Slice: lifecycle coordinator boundary
  - Objective: introduce an explicit coordination layer that owns register/progress/finalize lifecycle projection end-to-end
  - Dependencies: `scripts/runtime/lifecycle_coordinator.py`, `scripts/runtime/openclaw_hooks.py`, `plugin/scripts/runtime/*`, plugin control-plane callers
  - Risks: user-visible receipt drift, finalize path regressions, adapter code continuing to rebuild lifecycle payloads
  - Validation: register and terminal lifecycle payloads are emitted from the coordinator boundary and existing hook tests remain green
  - Exit Condition: register/progress/finalize/terminal control-plane responsibilities are explicit and testable from one runtime-owned boundary

- Slice: runtime source-of-truth convergence
  - Objective: define one canonical runtime source and turn the other tree into a generated or strictly synchronized artifact
  - Dependencies: `scripts/runtime/*`, `plugin/scripts/runtime/*`, install drift tooling, packaging layout
  - Risks: dual-edit drift, partial fixes landing in only one tree, installation mistakes hidden by validators
  - Validation: source-of-truth ownership is explicit in docs and build/install flow
  - Exit Condition: maintainers no longer need to reason about two peer runtime sources; `scripts/runtime/` is explicitly canonical and `plugin/scripts/runtime/` is enforced as a strict mirror

- Slice: post-hardening feature work
  - Objective: resume planning anomaly coverage and channel acceptance expansion on top of cleaner boundaries
  - Dependencies: roadmap extension areas and the two hardening slices above
  - Risks: more features land before structural ownership is fixed
  - Validation: status board names a concrete extension slice after hardening
  - Exit Condition: the next feature slice starts from stable architecture rather than accumulated patching

## Development Log Capture

- Trigger Level: high
- Auto-Capture When:
  - the root-cause hypothesis changes
  - a reusable mechanism replaces repeated local fixes
  - a retrofit changes governance, architecture, or release policy
  - a tradeoff or rejected shortcut is likely to matter in future work
- Skip When:
  - the change is mechanical or formatting-only
  - no durable reasoning changed
  - the work simply followed an already-approved path
  - the change stayed local and introduced no durable tradeoff
