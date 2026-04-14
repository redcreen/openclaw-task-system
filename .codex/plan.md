# Project Plan

## Current Phase

`Milestone 2: Growware Project 1 pilot foundation` is active.

The repo is no longer in watch-mode maintenance because Growware policy, deploy, and host-audit work has already landed in code and docs.

## Current Execution Line

- Objective: turn the current Growware foundation into a validated pilot baseline without regressing the shipped mainline
- Plan Link: `docs/reference/openclaw-task-system/development-plan.md#milestone-2-growware-project-1-pilot-foundation`
- Runway: the foundation is partially shipped; next close policy truth, activation safety, and audit positioning before any live rollout
- Progress: `1/4`
- Stop Conditions: policy truth remains split across layers, activation baseline stays ambiguous, host audit shows unresolved operator or user-visible issues, or release-facing validation fails
- Validation: `python3 scripts/runtime/growware_policy_sync.py --check --json`, `python3 scripts/runtime/growware_preflight.py --json`, `python3 scripts/runtime/growware_openclaw_binding.py --json`, `python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_policy_sync tests.test_growware_preflight tests.test_growware_project tests.test_openclaw_runtime_audit`, `bash scripts/run_tests.sh`, `python3 scripts/runtime/runtime_mirror.py --write`, `python3 scripts/runtime/plugin_doctor.py --json`, and `python3 scripts/runtime/plugin_smoke.py --json`

## Execution Tasks

- [x] EL-1 review the current Growware pilot diff and open an explicit milestone in roadmap / development-plan / control-surface docs
- [ ] EL-2 converge policy ownership so `docs/policy/*.md -> .policy/` is the only live runtime input and `.growware/policies/*.json` is bounded as compatibility-only
- [ ] EL-3 prove a clean pilot activation baseline across policy sync, preflight, binding preview, runtime mirror, doctor / smoke, and session hygiene
- [ ] EL-4 decide whether `openclaw_runtime_audit.py` stays Milestone 2 bootstrap evidence or becomes the lead slice of the next milestone

## Architecture Supervision

- Signal: `yellow`
- Signal Basis: source-of-truth drift is still visible between compiled policy, compatibility JSON, and activation docs
- Problem Class: milestone opening / boundary convergence
- Root Cause Hypothesis: Growware pilot implementation landed before roadmap and control surfaces formally named the new milestone, so compatibility layers and activation gates stayed implicit
- Correct Layer: milestone-level boundary convergence across roadmap, policy source-of-truth, and operator activation gates
- Rejected Shortcut: continue treating Growware work as a future candidate while runtime and deploy scripts already depend on it
- Automatic Review Trigger: any change to `.policy/`, `.growware/`, binding flow, session hygiene, or host-audit evidence
- Escalation Gate: raise but continue

## Escalation Model

- Continue Automatically: doc / code convergence that preserves the same Growware pilot direction and approval boundary
- Raise But Continue: policy, deploy, or binding refinements that keep live-write approval intact but change activation evidence or operator steps
- Require User Decision: any live rollout decision, approval-boundary relaxation, change of the primary feedback channel, or host-side self-heal that mutates user-visible history

## Slices

- Slice: policy source-of-truth convergence
  - Objective: make `docs/policy/*.md -> .policy/` the only live policy path the runtime depends on
  - Dependencies: `scripts/runtime/growware_policy_sync.py`, `scripts/runtime/growware_project.py`, `scripts/runtime/growware_feedback_classifier.py`, `scripts/runtime/growware_preflight.py`, `scripts/runtime/growware_local_deploy.py`, `.growware/policies/*.json`, and policy docs
  - Risks: policy drift survives because compatibility JSON still looks authoritative, or one runtime path bypasses `.policy/`
  - Validation: policy sync, preflight, targeted Growware tests, and docs all point to the same source-of-truth rule
  - Exit Condition: maintainers no longer need to reason about multiple live policy truths

- Slice: pilot activation baseline
  - Objective: prove one clean operator path for previewing or rehearsing Growware activation without unintended live writes
  - Dependencies: `growware_openclaw_binding.py`, `growware_session_hygiene.py`, `growware_local_deploy.py`, runtime mirror, doctor, smoke, install docs, and `.growware/channels.json`
  - Risks: binding preview, session hygiene, and local deploy each look valid in isolation but do not compose into one safe baseline
  - Validation: policy sync, preflight, binding preview, mirror, doctor, smoke, and targeted tests all stay green on the same reviewed state
  - Exit Condition: operators have one documented baseline command set for the pilot foundation

- Slice: host-side audit positioning
  - Objective: keep `openclaw_runtime_audit.py` useful as a host-side reality check without silently expanding it into an unapproved repair system
  - Dependencies: `scripts/runtime/openclaw_runtime_audit.py`, `tests/test_openclaw_runtime_audit.py`, usage docs, and the runtime-audit proposal
  - Risks: a read-only audit gets mistaken for a release gate, or repair ideas creep in without an explicit milestone and approval boundary
  - Validation: audit docs, proposal docs, and roadmap all describe the same boundary; tests keep the current read-only model green
  - Exit Condition: Milestone 2 explicitly records whether audit stays bootstrap-only or hands off to a later milestone

## Development Log Capture

- Trigger Level: high
- Auto-Capture When:
  - the root-cause hypothesis changes
  - a reusable mechanism replaces repeated local fixes
  - a retrofit changes governance, architecture, or release policy
  - a milestone is opened, split, or materially reclassified
- Skip When:
  - the change is mechanical or formatting-only
  - no durable reasoning changed
  - the work simply followed an already-approved path
  - the change stayed local and introduced no durable tradeoff
