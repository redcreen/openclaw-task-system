# Project Status

## Delivery Tier

- Tier: `medium`
- Why this tier: multi-session repo work now spans runtime behavior, Growware project-local operations, and durable control-surface maintenance
- Last reviewed: 2026-04-14

## Current Phase

`Milestone 2: Growware Project 1 pilot foundation` is active.

The repo has moved out of watch-mode maintenance because the Growware pilot is already partially implemented in code, docs, and validation flow.

## Active Slice

`growware pilot: policy truth + activation baseline`

## Current Execution Line

- Objective: turn the current Growware foundation into a validated pilot baseline without regressing the shipped mainline
- Plan Link: `docs/reference/openclaw-task-system/development-plan.md#milestone-2-growware-project-1-pilot-foundation`
- Runway: close policy truth, activation safety, and host-audit positioning before any live rollout
- Progress: `1/4` tasks complete
- Stop Conditions: policy truth remains split, activation baseline stays ambiguous, host audit shows unresolved operator or user-visible issues, or release-facing validation fails

## Execution Tasks

- [x] EL-1 review the current Growware pilot diff and open an explicit milestone in roadmap / development-plan / control-surface docs
- [ ] EL-2 converge policy ownership so `docs/policy/*.md -> .policy/` is the only live runtime input and `.growware/policies/*.json` is bounded as compatibility-only
- [ ] EL-3 prove a clean pilot activation baseline across policy sync, preflight, binding preview, runtime mirror, doctor / smoke, and session hygiene
- [ ] EL-4 decide whether `openclaw_runtime_audit.py` stays Milestone 2 bootstrap evidence or becomes the lead slice of the next milestone

## Architecture Supervision

- Signal: `yellow`
- Signal Basis: source-of-truth drift is still visible between compiled policy, compatibility JSON, and activation docs
- Root Cause Hypothesis: Growware pilot implementation landed before roadmap and control surfaces formally named the new milestone, so compatibility layers and activation gates stayed implicit
- Correct Layer: milestone-level boundary convergence across roadmap, policy source-of-truth, and operator activation gates
- Automatic Review Trigger: any change to `.policy/`, `.growware/`, binding flow, session hygiene, or host-audit evidence
- Escalation Gate: raise but continue

## Current Escalation State

- Current Gate: raise but continue
- Reason: the new milestone direction is clear, but policy-truth and activation-boundary convergence still need visible review
- Next Review Trigger: review again when `.policy/`, `.growware/`, binding preview, session hygiene, or host-audit scope changes

## Done

- Phase 0-6 minimum closure and `Milestone 1: post-hardening closeout` remain complete
- `.growware/` now acts as the durable project-local control surface for Growware `Project 1`
- `docs/policy/*.md` and `.policy/` now establish a human-source plus compiled-machine-layer policy model
- `growware_feedback_classifier.py`, `growware_project.py`, `growware_preflight.py`, and `growware_local_deploy.py` now consume or enforce the compiled policy layer
- install, usage, and pilot reference docs now explain the policy layer and host-side runtime audit entrypoints
- `openclaw_runtime_audit.py` now provides a read-only host-side audit bootstrap with test coverage for stale tasks, failed deliveries, cron errors, and user-visible noise filtering
- `scripts/run_tests.sh` now uses deterministic Python discovery and serial Node plugin tests for the current runtime / plugin suite

## In Progress

- closing the remaining source-of-truth gap between `.policy/` and legacy `.growware/policies/*.json`
- proving one clean activation baseline across policy sync, preflight, binding preview, runtime mirror, doctor / smoke, and session hygiene
- deciding whether host-side audit remains read-only bootstrap evidence or becomes the next named milestone

## Blockers / Open Decisions

- whether `.growware/policies/*.json` remains compatibility-only for this milestone or should be retired from live paths entirely
- whether the first real `feishu6-chat` activation rehearsal requires additional host-side evidence beyond the current validation stack
- whether `openclaw_runtime_audit.py` should stay outside release gates after Milestone 2 or become the lead slice of a follow-on milestone

## Next 3 Actions

1. Close EL-2 by making the compiled `.policy/` layer the only live policy truth the runtime depends on.
2. Run the reviewed activation baseline across policy sync, preflight, binding preview, runtime mirror, doctor, smoke, and targeted Growware / audit tests.
3. Decide whether host-side audit remains bootstrap-only or graduates into the next named milestone before any live pilot rollout.

## Development Log Capture

- Trigger Level: high
- Pending Capture: yes
- Reason: the repo has been reclassified from watch-mode maintenance into an explicit Growware pilot milestone
- Last Entry: docs/devlog/2026-04-12-close-post-hardening-closeout.md
