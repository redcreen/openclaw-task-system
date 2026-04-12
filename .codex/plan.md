# Project Plan

## Current Phase

Architecture hardening after Phase 6 mainline closure.

## Slices
- Slice: lifecycle coordinator boundary
  - Objective: introduce an explicit coordination layer that owns task lifecycle transitions end-to-end
  - Dependencies: `plugin/src/plugin/index.ts`, `scripts/runtime/openclaw_hooks.py`, `scripts/runtime/openclaw_bridge.py`, task mutation helpers
  - Risks: continuing race repairs, duplicated terminalization logic, user-visible receipt/final-state skew
  - Validation: lifecycle transition ownership can be described as one boundary with reduced plugin-side repair logic
  - Exit Condition: register/progress/finalize/terminal control-plane responsibilities are explicit and testable

- Slice: runtime source-of-truth convergence
  - Objective: define one canonical runtime source and turn the other tree into a generated or strictly synchronized artifact
  - Dependencies: `scripts/runtime/*`, `plugin/scripts/runtime/*`, install drift tooling, packaging layout
  - Risks: dual-edit drift, partial fixes landing in only one tree, installation mistakes hidden by validators
  - Validation: source-of-truth ownership is explicit in docs and build/install flow
  - Exit Condition: maintainers no longer need to reason about two peer runtime sources

- Slice: post-hardening feature work
  - Objective: resume planning anomaly coverage and channel acceptance expansion on top of cleaner boundaries
  - Dependencies: roadmap extension areas and the two hardening slices above
  - Risks: more features land before structural ownership is fixed
  - Validation: status board names a concrete extension slice after hardening
  - Exit Condition: the next feature slice starts from stable architecture rather than accumulated patching
