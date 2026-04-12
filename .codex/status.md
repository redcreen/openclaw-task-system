# Project Status

## Delivery Tier
- Tier: `medium`
- Why this tier: multi-session maintenance needs a lightweight but durable control surface
- Last reviewed: 2026-04-12

## Current Phase

Post-hardening closeout is complete, and the repo is back in steady-state maintenance until a new named roadmap candidate exists.

## Active Slice

`steady state: post-hardening stable`

## Current Execution Line
- Objective: keep the shipped runtime, docs, and release-facing evidence stable after closing Milestone 1
- Plan Link: `docs/reference/openclaw-task-system/development-plan.md`
- Runway: no open closeout tasks; reopen planning only when a new explicit roadmap candidate is named
- Progress: `4/4` tasks complete
- Stop Conditions: release-facing validation fails, evidence requirements materially change, or new capability work needs a named roadmap candidate

## Execution Tasks
- [x] EL-1 define the next milestone in roadmap and durable project-level development plan docs
- [x] EL-2 close compound follow-up, future-first, and output-separation boundary drift from active docs and runtime-facing evidence
- [x] EL-3 deepen planning/channel/operator evidence while keeping `bash scripts/run_tests.sh` and `release_gate.py --json` green
- [x] EL-4 do one final closeout pass across roadmap, test-plan, archive guidance, and control surfaces, then either close the milestone or split a new named roadmap candidate

## Architecture Supervision
- Signal: `green`
- Signal Basis: architecture hardening stayed closed, the active docs now match the shipped compound/future-first/output-channel boundary, and release-facing acceptance depth expanded without reopening ownership debt
- Root Cause Hypothesis: post-hardening work had remained too diffuse across extension bullets and small slices, which made “later closeout” easy to defer without one milestone owner or execution line
- Correct Layer: close the milestone explicitly and return to watch-mode maintenance until a new named roadmap candidate exists
- Escalation Gate: continue automatically

## Current Escalation State
- Current Gate: continue automatically
- Reason: no active closeout debt remains and the current state stays within the repo's existing runtime and release-facing boundaries
- Next Review Trigger: review again when a new roadmap candidate appears, blockers change, or release-facing evidence requirements change

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
- roadmap and the project development plan promoted `Milestone 1: post-hardening closeout` into a named long-task milestone and now record it as complete
- `docs/reference/openclaw-task-system/development-plan.md` now keeps a durable milestone-level record below roadmap and above `.codex/plan.md`
- compound follow-up docs now describe the shipped runtime boundary instead of an open design placeholder
- output-channel separation docs now match the current runtime contract, and `task_user_content` remains only as a legacy leak-audit concern
- same-session routing decision docs now describe `collect-more` as a shipped non-task path
- planning acceptance now proves scheduled follow-up summaries stay in control-plane projection
- channel acceptance now includes an explicit bounded-focus sample for `webchat`
- main-ops acceptance now includes `followup-task-missing` operator recovery projection
- roadmap, README, todo intake, development plan, and control surfaces now all record Milestone 1 as closed
- `bash scripts/run_tests.sh`, `python3 scripts/runtime/release_gate.py --json`, `python3 scripts/runtime/planning_acceptance_suite.py --json`, `python3 scripts/runtime/channel_acceptance.py --json`, and `python3 scripts/runtime/main_ops_acceptance.py --json` are green after the closeout pass

## In Progress

- none; Milestone 1 is closed and the repo is back in steady-state maintenance

## Blockers / Open Decisions

- none currently.

## Next 3 Actions
1. Keep `bash scripts/run_tests.sh` and `python3 scripts/runtime/release_gate.py --json` green on every runtime or plugin change.
2. Rerun planning evidence capture when a future change touches planning/runtime contracts or release-facing acceptance coverage materially.
3. Name a new roadmap candidate before starting broader planning, steering, or operator extension work.

## Development Log Capture

- Trigger Level: high
- Pending Capture: no
- Last Entry: docs/devlog/2026-04-12-close-post-hardening-closeout.md
