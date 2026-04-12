# Project Status

## Delivery Tier
- Tier: `medium`
- Why this tier: multi-session maintenance needs a lightweight but durable control surface
- Last reviewed: 2026-04-12

## Current Phase

Architecture hardening is now closed; canonical runtime source and lifecycle ownership are explicit.

## Active Slice

`runtime source-of-truth convergence`

## Current Execution Line
- Objective: formalize `scripts/runtime/` as the canonical editable runtime tree, make `plugin/scripts/runtime/` a strict synchronized mirror, and close architecture hardening with explicit tooling and docs
- Plan Link: `runtime source-of-truth convergence`
- Runway: one checkpoint-sized convergence pass across runtime tooling, install path, maintainer docs, workstream docs, and `.codex/*`
- Progress: `6/6` tasks complete
- Stop Conditions: runtime mirror enforcement regresses, install path no longer protects against mirror drift, or source ownership remains ambiguous in maintainer docs

## Execution Tasks
- [x] EL-1 refresh the architecture-retrofit note and control surface around the canonical-source decision
- [x] EL-2 formalize `scripts/runtime/` as the canonical editable runtime tree in repo docs and maintainer guidance
- [x] EL-3 make install/doctor/test entrypoints enforce the synchronized mirror rule
- [x] EL-4 align `README`, architecture docs, roadmap, and architecture-hardening workstream with the new ownership rule
- [x] EL-5 record the decision in `docs/devlog/` and close architecture-hardening ambiguity in `.codex/*`
- [x] EL-6 rerun `deep` and `./scripts/run_tests.sh`

## Architecture Supervision
- Signal: `green`
- Signal Basis: lifecycle ownership and canonical runtime source ownership are now explicit in code-entry tooling, docs, and control surfaces
- Root Cause Hypothesis: the remaining architecture debt was not missing code paths but missing ownership clarity between canonical runtime source and install payload mirror
- Correct Layer: runtime mirror tooling, install/doctor/test entrypoints, architecture docs, and control surfaces
- Escalation Gate: continue automatically

## Current Escalation State
- Current Gate: continue automatically
- Reason: the architecture hardening slice has converged; remaining work is feature-facing rather than boundary-repair work
- Next Review Trigger: review again when blockers change, the active slice rolls forward, or release-facing work begins

## Done

- `.codex` control surface is present and aligned to the architecture-hardening workstream
- README and docs landing stack are aligned to the shipped Phase 6 baseline
- architecture root-cause review identified lifecycle ownership and runtime source duplication as the main structural debts
- lifecycle receipt and terminal projection logic has been moved into `scripts/runtime/lifecycle_coordinator.py`
- `plugin/scripts/runtime/*` has been re-synced to the source runtime after the lifecycle refactor
- `scripts/runtime/` is now the only canonical editable runtime tree
- `plugin/scripts/runtime/` is now documented and enforced as a strict synchronized mirror
- tests, doctor, and install paths all validate the runtime mirror rule before shipping or local install succeeds
- docs, roadmap, workstream notes, and retrofit notes now describe the same runtime-source ownership rule
- `./scripts/run_tests.sh` passed after the lifecycle ownership refactor

## In Progress

- preparing the first post-hardening feature slice from cleaner runtime boundaries
- watching for any feature work that tries to reintroduce plugin-side lifecycle or runtime-source drift

## Blockers / Open Decisions

- none currently.

## Next 3 Actions
1. Start the first post-hardening feature slice from the existing roadmap extension areas instead of continuing architecture cleanup.
2. Keep `runtime_mirror.py --check`, `plugin_doctor.py`, and install flow aligned if packaging changes in future work.
3. Watch for any new plugin-side lifecycle repair logic; treat that as an architecture regression instead of a local fix.

## Development Log Capture

- Trigger Level: high
- Pending Capture: no
- Last Entry: docs/devlog/2026-04-12-close-runtime-source-of-truth-convergence.md
