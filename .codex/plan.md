# Project Plan

## Current Phase

Post-hardening feature work after Phase 6 mainline closure; broader release-gate convergence is now complete and the release-facing line remains green.

## Current Execution Line
- Objective: converge the broader release-facing gate into one explicit runtime entrypoint instead of relying on a remembered manual command bundle
- Plan Link: `broader release gate convergence`
- Runway: one checkpoint-sized release-gate automation and doc sync pass
- Progress: `4/4`
- Stop Conditions: the scripted gate hides failing substeps, docs drift away from the new entrypoint, or repo / installed runtime sync falls behind the canonical runtime tree
- Validation: `python3 -m unittest discover -s tests -p 'test_release_gate.py' -v`, `python3 scripts/runtime/release_gate.py --json`, `python3 scripts/runtime/runtime_mirror.py --check --json`, and `python3 scripts/runtime/plugin_install_drift.py --json`

## Execution Tasks
- [x] EL-1 define the broader gate contract from the existing manual release-facing command bundle
- [x] EL-2 add a structured `release_gate.py` entrypoint that keeps all failing substeps visible
- [x] EL-3 refresh docs, devlog, and `.codex/*` so maintainers recover through the new release-gate entrypoint
- [x] EL-4 re-sync runtime mirrors and rerun the broader gate

## Architecture Supervision
- Signal: `green`
- Signal Basis: `test_release_gate.py`, `release_gate.py --json`, runtime mirror, install drift, and the existing broader gate steps all stayed green after converging on the new scripted entrypoint
- Problem Class: release gate convergence
- Root Cause Hypothesis: the repo already had the right release-facing checks, but maintainers still had to remember and retype an informal command bundle
- Correct Layer: one runtime-owned gate entrypoint plus release-facing docs and control-surface updates
- Rejected Shortcut: keep the manual command list only in status notes and docs without giving it a canonical executable entrypoint
- Escalation Gate: continue automatically

## Escalation Model
- Continue Automatically: operator-surface refinements that preserve the same runtime truth source and recovery ownership
- Raise But Continue: snapshot or doc changes that widen operator visibility without changing underlying recovery behavior
- Require User Decision: any change that alters release gates, acceptance ownership, or what counts as mandatory real-channel evidence

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

- Slice: planning anomaly acceptance expansion
  - Objective: prove representative planning anomaly recovery (`promise-without-task`, `planner-timeout`, `followup-task-missing`) through the contract-level acceptance path
  - Dependencies: `scripts/runtime/planning_acceptance.py`, `scripts/runtime/openclaw_hooks.py`, `scripts/runtime/main_ops.py`, `scripts/runtime/task_status.py`
  - Risks: anomaly handling regresses while happy-path planning still looks green, or operator/user projections drift apart
  - Validation: `planning_acceptance.py --json` passes with anomaly-specific steps and `test_*planning_acceptance*.py` stays green
  - Exit Condition: acceptance proves happy path, compound boundary, and representative anomaly recovery projection from one runtime-owned flow

- Slice: channel acceptance sample expansion
  - Objective: prove the shipped per-channel rollout boundary through sample-based acceptance instead of a summary-only helper
  - Dependencies: `scripts/runtime/channel_acceptance.py`, `scripts/runtime/producer_contract.py`, `scripts/runtime/stable_acceptance.py`
  - Risks: focus-channel or fallback-channel behavior regresses while the static channel matrix still looks complete
  - Validation: `channel_acceptance.py --json` passes and `test_channel_acceptance.py` / `test_stable_acceptance.py` stay green
  - Exit Condition: stable acceptance exercises concrete channel samples for matrix, session focus, and fallback channels from one acceptance entry

- Slice: operator recovery acceptance expansion
  - Objective: prove representative operator-facing recovery projection across `dashboard`, `triage`, and `continuity`
  - Dependencies: `scripts/runtime/main_ops.py`, `scripts/runtime/main_ops_acceptance.py`, `scripts/runtime/stable_acceptance.py`
  - Risks: dashboard and triage drift on the primary recovery action, or watchdog auto-resume remains unit-tested but not release-facing
  - Validation: `main_ops_acceptance.py --json` passes and `test_main_ops_acceptance.py` / `test_stable_acceptance.py` stay green
  - Exit Condition: stable acceptance exercises session focus, planning recovery, and watchdog auto-resume from one operator-facing acceptance entry

- Slice: planning evidence archival convergence
  - Objective: keep dated planning evidence under `docs/archive/` and refresh one semi-real record after the expanded release-facing acceptance surface lands
  - Dependencies: `scripts/runtime/create_planning_acceptance_record.py`, `scripts/runtime/prepare_planning_acceptance.py`, planning bundle tooling, archive docs, and `stable_acceptance.py`
  - Risks: dated evidence lands in the active docs stack, or the archived record drifts behind the current acceptance helper inventory
  - Validation: broader release gate stays green, planning record tooling writes to `docs/archive/`, and `run_planning_acceptance_bundle.py --json --date 2026-04-12 --force` succeeds
  - Exit Condition: archive-first evidence workflow is enforced and the latest semi-real record reflects the current stable acceptance surface

- Slice: operator UX snapshot depth
  - Objective: give operators short continuity / triage views that reuse the same runbook truth as the full reports
  - Dependencies: `scripts/runtime/main_ops.py`, `scripts/runtime/main_ops_acceptance.py`, operator docs, runtime mirror, and installed runtime sync
  - Risks: short views drift from the full runbook, or operators start trusting a summary surface that is not release-facing
  - Validation: `main_ops_acceptance.py --json`, `test_main_ops.py`, `test_main_ops_acceptance.py`, `test_stable_acceptance.py`, and `bash scripts/run_tests.sh` all stay green
  - Exit Condition: continuity and triage both expose compact operator snapshots, continuity also exposes issue-only output, and stable acceptance proves those views end to end

- Slice: broader release gate convergence
  - Objective: turn the broader release-facing check bundle into one explicit scripted entrypoint with structured step status
  - Dependencies: `scripts/run_tests.sh`, `scripts/runtime/main_ops_acceptance.py`, `scripts/runtime/stable_acceptance.py`, `scripts/runtime/runtime_mirror.py`, `scripts/runtime/plugin_install_drift.py`, and release-facing docs
  - Risks: maintainers skip part of the release line, docs describe a gate with no canonical command, or failing substeps become hidden behind a wrapper
  - Validation: `release_gate.py --json` passes, `test_release_gate.py` stays green, and docs point to the same canonical release-gate entrypoint
  - Exit Condition: one runtime-owned command executes the broader release-facing line and reports enough structure to show which substep failed

- Slice: post-hardening feature follow-on
  - Objective: continue broader release-gate depth and real-channel evidence work on top of the tightened planning, channel, and operator acceptance baseline
  - Dependencies: roadmap extension areas and the completed hardening / acceptance slices above
  - Risks: new feature work lands without updating acceptance, real-channel evidence, or operator snapshot depth
  - Validation: the next execution line names a concrete feature slice beyond anomaly acceptance
  - Exit Condition: follow-on feature work starts from an explicit, tested extension boundary instead of generic “continue later” tracking

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
