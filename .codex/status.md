# Project Status

## Delivery Tier
- Tier: `medium`
- Why this tier: multi-session maintenance needs a lightweight but durable control surface
- Last reviewed: 2026-04-12

## Current Phase

Post-hardening feature work is underway; the broader release gate is still green and the latest extension slice converged that gate into one explicit runtime entrypoint.

## Active Slice

`broader release gate convergence`

## Current Execution Line
- Objective: converge the broader release-facing gate into one explicit runtime entrypoint instead of relying on a remembered manual command bundle
- Plan Link: `broader release gate convergence`
- Runway: one checkpoint-sized release-gate automation pass across runtime scripts, docs, and sync gates
- Progress: `4/4` tasks complete
- Stop Conditions: the scripted gate hides failing substeps, docs drift away from the new entrypoint, or repo / installed runtime sync falls behind the shipped operator surface

## Execution Tasks
- [x] EL-1 define the broader gate contract from the existing manual release-facing command bundle
- [x] EL-2 add a structured `release_gate.py` entrypoint that keeps all failing substeps visible
- [x] EL-3 refresh docs, devlog, and `.codex/*` so maintainers recover through the new release-gate entrypoint
- [x] EL-4 re-sync runtime mirrors and rerun the broader gate

## Architecture Supervision
- Signal: `green`
- Signal Basis: `test_release_gate.py`, `release_gate.py --json`, runtime mirror, install drift, and the existing broader gate steps all stayed green after converging on the new scripted entrypoint
- Root Cause Hypothesis: the repo already had the right release-facing checks, but maintainers still had to remember and retype an informal command bundle
- Correct Layer: one runtime-owned gate entrypoint plus release-facing docs, tests, and runtime sync
- Escalation Gate: continue automatically

## Current Escalation State
- Current Gate: continue automatically
- Reason: this slice deepened operator visibility without changing the underlying runtime truth source or recovery ownership
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
- `planning_acceptance.py` now validates `promise-without-task`, `planner-timeout`, and `followup-task-missing` as contract-level anomaly cases
- planning acceptance markdown and tests now track the expanded anomaly-recovery step inventory
- `channel_acceptance.py` now exposes standalone contract-level samples for channel matrix, session focus, and observed-channel fallback behavior
- `stable_acceptance.py` now treats channel acceptance samples as a first-class release-facing step
- `main_ops_acceptance.py` now exposes standalone operator-facing samples for dashboard focus, planning recovery projection, and watchdog auto-resume guidance
- `stable_acceptance.py` now treats main-ops acceptance as a first-class release-facing step
- `bash scripts/run_tests.sh` is green again after the planning, channel, and operator acceptance expansions
- planning acceptance record tooling now writes dated records to `docs/archive/`
- a fresh semi-real planning acceptance record was archived at `docs/archive/planning_acceptance_record_2026-04-12.md`
- `main_ops.py continuity` now exposes `--compact` and `--only-issues` operator snapshots from the same runbook truth as the full report
- `main_ops.py triage` now exposes `--compact` for shorter operator duty views
- `main_ops_acceptance.py` now proves the operator snapshot contract as a release-facing sample
- `bash scripts/run_tests.sh` is green after the operator snapshot UX expansion
- `release_gate.py` now provides one structured runtime entrypoint for the broader release-facing check line
- release-facing docs now point to `python3 scripts/runtime/release_gate.py --json` instead of requiring maintainers to reconstruct the broader gate from status notes
- `test_release_gate.py` now proves the wrapper reports success, failure propagation, and markdown/json output

## In Progress

- selecting the next post-hardening slice after the release-gate convergence pass
- keeping the new release-gate entrypoint aligned with stable acceptance, runtime mirror, and real-channel evidence collection as the release surface widens

## Blockers / Open Decisions

- none currently.

## Next 3 Actions
1. Choose the next post-hardening slice from real Feishu / Telegram evidence capture or planning bundle dry-run convergence instead of reopening already-covered helpers.
2. Keep `release_gate.py`, `stable_acceptance.py`, and install-drift visibility aligned if release-facing checks change again.
3. Rerun `python3 scripts/runtime/release_gate.py --json` before batching more feature-facing changes on top of this release-gate slice.

## Development Log Capture

- Trigger Level: high
- Pending Capture: no
- Last Entry: docs/devlog/2026-04-12-converge-broader-release-gate.md
