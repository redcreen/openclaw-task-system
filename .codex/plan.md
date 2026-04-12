# Project Plan

## Current Phase

Post-hardening maintenance has rolled from docs retrofit into one explicit next milestone: a post-hardening closeout run that should execute as one long-task line.

## Current Execution Line
- Objective: close the remaining post-hardening boundary work in one uninterrupted run across compound/future-first convergence, evidence depth, operator/release-facing closeout, and final docs/archive convergence
- Plan Link: `docs/reference/openclaw-task-system/development-plan.md`
- Runway: one long-task milestone pass instead of reopening unrelated mini-slices
- Progress: `1/4`
- Stop Conditions: release-facing validation fails, the work reopens architecture ownership debt, real-channel evidence changes what counts as mandatory release proof, or the milestone must be split into a new roadmap candidate
- Validation: `bash scripts/run_tests.sh`, `python3 scripts/runtime/release_gate.py --json`, `python3 scripts/runtime/planning_acceptance_suite.py --json`, `python3 scripts/runtime/channel_acceptance.py --json`, and `python3 scripts/runtime/main_ops_acceptance.py --json`

## Execution Tasks
- [x] EL-1 define the next milestone in roadmap and durable project-level development plan docs
- [ ] EL-2 close compound follow-up, future-first, and output-separation boundary drift from active docs and runtime-facing evidence
- [ ] EL-3 deepen planning/channel/operator evidence while keeping the release-facing gates green
- [ ] EL-4 do one final closeout pass across roadmap, test-plan, archive guidance, and control surfaces, then either close the milestone or split a new named roadmap candidate

## Architecture Supervision
- Signal: `green`
- Signal Basis: architecture hardening is closed, the docs stack is converged again, and the next milestone is now explicitly framed as one long-task closeout line with a durable development plan
- Problem Class: milestone execution clarity
- Root Cause Hypothesis: post-hardening work had remained too diffuse across extension bullets and small slices, which made “later closeout” easy to defer without one milestone owner or execution line
- Correct Layer: promote the remaining work into one named milestone with a durable plan and control-surface ownership
- Rejected Shortcut: keep describing the remainder as generic extension work without a milestone, queue, or explicit end condition
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
  - Validation: broader release gate stays green, planning record tooling writes to `docs/archive/`, and `run_planning_acceptance_bundle.py --json --date 2026-04-12` succeeds without overwriting an existing dated record
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

- Slice: planning bundle dry-run convergence
  - Objective: let maintainers rehearse the planning evidence workflow in a temporary workspace instead of writing directly into repo docs
  - Dependencies: `create_planning_acceptance_record.py`, `prepare_planning_acceptance.py`, `capture_planning_acceptance_artifacts.py`, `run_planning_acceptance_bundle.py`, `planning_acceptance_suite.py`, and planning docs
  - Risks: dry-run diverges from the real repo-writing flow, temp workspace paths are not discoverable, or planning docs still imply that rehearsal must modify repo docs
  - Validation: `test_*planning_acceptance*.py` stays green, `run_planning_acceptance_bundle.py --dry-run --json` succeeds, and `planning_acceptance_suite.py --dry-run --json` succeeds
  - Exit Condition: the planning evidence workflow can be rehearsed end-to-end in a temporary workspace and the docs point to that explicit entrypoint

- Slice: dry-run evidence promotion policy
  - Objective: make bundle / suite output and docs explicit about when a green dry-run must be promoted into a dated archive record
  - Dependencies: `run_planning_acceptance_bundle.py`, `planning_acceptance_suite.py`, planning runbook, archive docs, and current archive-first workflow
  - Risks: partial dry-runs get mistaken for formal evidence, or maintainers do not know when dated archive evidence is mandatory
  - Validation: promotion-policy tests stay green, bundle / suite expose policy fields, and docs point to the same promotion rule and command
  - Exit Condition: green full dry-runs, failed dry-runs, partial dry-runs, and repo-writing runs each surface an explicit promotion state

- Slice: docs retrofit convergence
  - Objective: replace placeholder bilingual public docs with standalone pages and repair docs landing / template quality
  - Dependencies: `docs/README*`, planning acceptance docs, same-session routing reference docs, and `.codex/*`
  - Risks: GitHub-facing docs look unfinished, template pages are not directly reusable, or durable docs keep session-specific review instructions
  - Validation: placeholder scan returns zero and `bash scripts/run_tests.sh` stays green
  - Exit Condition: public English docs stand alone, templates are copyable, durable references are free of session-specific review text, and control-surface state reflects the slice

- Slice: milestone 1 post-hardening closeout
  - Objective: execute the remaining post-hardening work as one long-task milestone instead of many disconnected cleanup slices
  - Dependencies: `docs/reference/openclaw-task-system/development-plan.md`, roadmap extension areas, planning/channel/operator acceptance helpers, and release-facing docs
  - Risks: the milestone stays too vague, evidence depth remains thin in the highest-risk areas, or the repo keeps carrying generic “close later” language without an end condition
  - Validation: release-facing gates stay green while EL-2 through EL-4 converge
  - Exit Condition: the remaining work is either shipped, archived, or explicitly broken into a new named roadmap candidate

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
