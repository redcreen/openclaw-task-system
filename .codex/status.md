# Project Status

## Delivery Tier
- Tier: `medium`
- Why this tier: multi-session maintenance needs a lightweight but durable control surface
- Last reviewed: 2026-04-12

## Current Phase

Documentation retrofit is complete for this slice; the bilingual landing stack is aligned again, placeholder English public docs were replaced with standalone content, and the broader release gate remained green.

## Active Slice

`docs retrofit: bilingual public docs convergence`

## Current Execution Line
- Objective: replace placeholder public docs with standalone English content, repair docs landing roles, and remove session-specific review text from durable reference pages
- Plan Link: `docs retrofit: bilingual public docs convergence`
- Runway: one checkpoint-sized documentation convergence pass across landing docs, planning docs, and same-session routing reference pages
- Progress: `4/4` tasks complete
- Stop Conditions: placeholder English pages remain in the public docs stack, docs landing still duplicates governance content, durable docs still contain session-specific review instructions, or template pages are not copyable as-is

## Execution Tasks
- [x] EL-1 repair `docs/README*` so directory roles and markdown governance are explicit instead of duplicated or blank
- [x] EL-2 replace placeholder English pages in the public docs stack with standalone, repository-relative documentation
- [x] EL-3 make planning acceptance templates copyable and remove session-specific review instructions from durable reference docs
- [x] EL-4 verify the placeholder scan is clean and the project testsuite still passes

## Architecture Supervision
- Signal: `green`
- Signal Basis: placeholder scan now returns `total=0`, planning template pages render as copyable templates, and `bash scripts/run_tests.sh` stayed green after the docs retrofit
- Root Cause Hypothesis: the public docs stack had drifted into fake bilingual placeholders, duplicated landing-page governance, and one durable reference page still carried session-specific review instructions
- Correct Layer: fix the durable docs themselves and refresh `.codex/*`; do not rely on chat context or ad hoc reviewer memory
- Escalation Gate: continue automatically

## Current Escalation State
- Current Gate: continue automatically
- Reason: this slice changed documentation and control-surface quality without altering runtime truth-source ownership or delivery behavior
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

## In Progress

- selecting the next post-hardening slice after the docs retrofit pass
- keeping the refreshed public docs aligned with future runtime and acceptance changes

## Blockers / Open Decisions

- none currently.

## Next 3 Actions
1. Choose the next post-hardening feature or evidence slice instead of reopening already-converged docs placeholder work.
2. Keep public docs aligned whenever runtime routing, planning acceptance, or control-plane contracts change again.
3. Re-run the placeholder scan plus `bash scripts/run_tests.sh` before future docs-heavy release-facing commits.

## Development Log Capture

- Trigger Level: high
- Pending Capture: no
- Last Entry: docs/devlog/2026-04-12-preserve-archive-record-on-promotion.md
