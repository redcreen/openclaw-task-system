# Project Plan

## Current Phase

`Milestone 3: system performance testing and optimization` is active.

Milestone 2 is closed: compiled `.policy/` is now the only live Growware policy truth, the reviewed activation baseline is green, and host-side audit is explicitly frozen as bootstrap-only evidence.

## Current Execution Line

- Objective: establish a reproducible performance baseline for the shipped runtime and Growware operator surface without regressing the closed foundation milestone
- Plan Link: `docs/reference/openclaw-task-system/development-plan.md#milestone-3-system-performance-testing-and-optimization`
- Runway: define benchmark surfaces and budgets first, then add reproducible measurement entrypoints, capture the first baseline, and only then optimize the measured hotspots
- Progress: `0/4`
- Stop Conditions: measurement entrypoints are not reproducible, optimization starts before baseline capture, benchmark evidence depends on unstable host state, or runtime-safety validation regresses
- Validation: `python3 scripts/runtime/growware_policy_sync.py --write --json`, `python3 scripts/runtime/growware_preflight.py --json`, `python3 scripts/runtime/growware_openclaw_binding.py --json`, `python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_policy_sync tests.test_growware_preflight tests.test_growware_project tests.test_openclaw_runtime_audit -v`, `bash scripts/run_tests.sh`, `python3 scripts/runtime/runtime_mirror.py --write`, `python3 scripts/runtime/plugin_doctor.py --json`, and `python3 scripts/runtime/plugin_smoke.py --json`

## Execution Tasks

- [ ] PL-1 define the first benchmark surface, sample fixtures, and performance budgets for runtime, control-plane, and operator entrypoints
- [ ] PL-2 add or standardize reproducible measurement entrypoints so the same commands produce comparable baseline output
- [ ] PL-3 capture the initial benchmark / profile baseline and attribute the top hotspots before changing behavior
- [ ] PL-4 land the first evidence-backed optimization and wire the improved path into a regression gate

## Architecture Supervision

- Signal: `yellow`
- Signal Basis: the repo has real performance-sensitive paths, but there is still no durable benchmark surface, baseline sample set, or agreed budget to anchor optimization work
- Problem Class: measurement-gap closure before optimization
- Root Cause Hypothesis: earlier milestones focused on correctness, control-surface convergence, and pilot-safety boundaries, so performance evidence never became a first-class artifact
- Correct Layer: milestone-level performance measurement and regression discipline across runtime, control-plane, and operator entrypoints
- Rejected Shortcut: tuning whichever path feels slow first without fixed samples, command entrypoints, or before / after evidence
- Automatic Review Trigger: any change to runtime hot paths, control-plane projections, SQLite / file-scan access, benchmark helpers, or operator entrypoints under measurement
- Escalation Gate: raise but continue

## Escalation Model

- Continue Automatically: benchmark-surface definition, measurement helpers, fixture prep, and evidence-backed optimization that preserve current product direction
- Raise But Continue: changes that alter operator workflows, benchmark budgets, or validation cost while staying inside the approved performance milestone
- Require User Decision: any live-rollout decision, approval-boundary relaxation, compatibility promise change, or performance tradeoff that meaningfully changes scope / cost / latency guarantees for users

## Slices

- Slice: benchmark surface definition
  - Objective: define what must be measured, with which fixtures, and against which budgets before optimization starts
  - Dependencies: roadmap / development plan, runtime hot-path inventory, operator entrypoints, and current validation stack
  - Risks: the team optimizes isolated code paths that do not represent user-visible latency or operational cost
  - Validation: one durable benchmark-surface document or script contract covers runtime, control-plane, and operator entrypoints
  - Exit Condition: maintainers share one measurement vocabulary instead of ad-hoc local timing

- Slice: reproducible measurement entrypoints
  - Objective: make baseline capture runnable through repeatable commands and controlled sample inputs
  - Dependencies: benchmark surface, fixture data, runtime scripts, and any helper harnesses needed for profiling
  - Risks: baseline numbers drift because commands, sample data, or environment assumptions are not controlled
  - Validation: the same reviewed commands can be rerun locally to produce comparable outputs
  - Exit Condition: benchmark and profile capture no longer depends on a specific maintainer remembering the setup

- Slice: hotspot attribution and first optimization
  - Objective: rank the first real bottlenecks and change only the measured paths that matter
  - Dependencies: captured baseline artifacts, code ownership in hot paths, and runtime-safety validation
  - Risks: optimization changes behavior without proving impact, or gains in one path create regressions elsewhere
  - Validation: before / after evidence plus runtime-safety validation on the same reviewed state
  - Exit Condition: at least one optimized path is measurably faster and protected by regression checks

## Next Phase Preview

- Planned Phase: `post-performance live pilot activation`
- Why Next: after the repo has a stable performance baseline, the next justified expansion is rehearsal and activation on top of measured, regression-protected foundations
- Draft Scope: `feishu6-chat` live activation rehearsal, operator evidence capture, and only then any broader rollout or ergonomics expansion
- Draft Rule: do not reopen alternate policy truths or expand host-side repair scope while activation prep is underway

## Development Log Capture

- Trigger Level: high
- Auto-Capture When:
  - the benchmark surface or budget model changes
  - a new measurement harness becomes a reusable repo capability
  - an optimization changes architecture, operator workflow, or validation cost in a durable way
  - the repo moves from baseline capture into optimization or activation rehearsal
- Skip When:
  - the change is mechanical or formatting-only
  - no durable reasoning changed
  - the work simply followed an already-approved measurement path
  - the change stayed local and introduced no durable tradeoff
