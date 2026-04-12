# Project Status

## Delivery Tier
- Tier: `medium`
- Why this tier: multi-session maintenance needs a lightweight but durable control surface
- Last reviewed: 2026-04-12

## Current Phase

The docs retrofit slice is complete, and the repo is now rolled forward to one explicit next milestone: a post-hardening closeout run that should execute as one long-task line instead of many small cleanup slices.

## Active Slice

`milestone: post-hardening closeout`

## Current Execution Line
- Objective: close the remaining post-hardening boundary work in one uninterrupted run across compound/future-first convergence, evidence depth, operator/release-facing closeout, and final docs/archive convergence
- Plan Link: `docs/reference/openclaw-task-system/development-plan.md`
- Runway: one long-task milestone pass instead of reopening unrelated mini-slices
- Progress: `1/4` tasks complete
- Stop Conditions: release-facing validation fails, the work reopens architecture ownership debt, real-channel evidence changes what counts as mandatory release proof, or the milestone proves too broad and must be split into a new roadmap candidate

## Execution Tasks
- [x] EL-1 define the next milestone in roadmap and durable project-level development plan docs
- [ ] EL-2 close compound follow-up, future-first, and output-separation boundary drift from active docs and runtime-facing evidence
- [ ] EL-3 deepen planning/channel/operator evidence while keeping `bash scripts/run_tests.sh` and `release_gate.py --json` green
- [ ] EL-4 do one final closeout pass across roadmap, test-plan, archive guidance, and control surfaces, then either close the milestone or split a new named roadmap candidate

## Architecture Supervision
- Signal: `green`
- Signal Basis: architecture hardening is already closed, the docs stack is converged again, and the next milestone is now explicitly framed as one long-task closeout line with a durable development plan
- Root Cause Hypothesis: post-hardening work had remained too diffuse across extension bullets and small slices, which made “later closeout” easy to defer without one milestone owner or execution line
- Correct Layer: promote the remaining work into one named milestone with a durable plan and control-surface ownership
- Escalation Gate: continue automatically

## Current Escalation State
- Current Gate: continue automatically
- Reason: the next milestone is now explicit and still stays within the repo's existing runtime and release-facing boundaries
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
- `prepare_planning_acceptance.py`, `capture_planning_acceptance_artifacts.py`, `run_planning_acceptance_bundle.py`, and `planning_acceptance_suite.py` now support `--dry-run`
- planning dry-run now writes records and artifacts into a temporary workspace instead of mutating `docs/archive/` or `docs/artifacts/`
- planning docs now point maintainers to explicit dry-run rehearsal commands for the evidence workflow
- planning bundle / suite output now expose explicit promotion states for `ready-for-archive`, `insufficient-signal`, `blocked`, and `already-archived`
- runbook and archive docs now say when a green dry-run must be promoted into a dated archive record
- repo-side planning evidence promotion now refreshes artifacts without clobbering an existing dated archive record back to template content
- docs landing pages now explain directory roles and markdown governance without duplicated placeholder sections
- placeholder English pages for compound follow-up, planning/tool usage, output separation, planning evidence, task-user-content, todo tracking, and same-session routing reference docs now stand on their own
- planning acceptance record templates are now copyable in both English and Chinese
- durable same-session routing reference docs no longer contain a session-specific Feishu review instruction
- placeholder-doc scan returned `total=0`
- `bash scripts/run_tests.sh` passed after the docs retrofit
- roadmap now exposes `Milestone 1: post-hardening closeout` as the next long-task milestone
- `docs/reference/openclaw-task-system/development-plan.md` now gives the project a durable milestone-level execution queue below roadmap and above `.codex/plan.md`

## In Progress

- Milestone 1 is framed and ready to run as one long-task execution line
- the remaining work is being treated as one closeout queue instead of many unrelated mini-slices

## Blockers / Open Decisions

- none currently.

## Next 3 Actions
1. Start EL-2 from the project development plan and close the compound/future-first boundary as the first real milestone work item.
2. Keep `bash scripts/run_tests.sh` and `python3 scripts/runtime/release_gate.py --json` green while deepening evidence and operator-facing closeout.
3. Decide at milestone end whether the repo can truly close post-hardening work or whether a smaller new roadmap candidate needs to be named explicitly.

## Development Log Capture

- Trigger Level: high
- Pending Capture: no
- Last Entry: docs/devlog/2026-04-12-preserve-archive-record-on-promotion.md
