# Project Plan

## Current Phase

`wd reliability and task usefulness convergence` is active.

Milestone 2 and Milestone 3 remain closed. The current active line is no longer performance governance; it is runtime usefulness work on top of the existing baseline.

## Current Execution Line

- Objective: improve runtime-owned user-visible usefulness, starting with `wd` receipts and terminal control-plane messages that are currently inaccurate or low-value
- Plan Link: `runtime usefulness / wd`
- Runway: inspect real host logs first, fix the runtime-owned message rules in one place, and verify against targeted tests plus doctor / smoke / local deploy
- Progress: `WU-1 docs side-track removed; WU-2 wd wording and terminal usefulness in progress`
- Stop Conditions: `wd` still reports misleading queue state, terminal follow-ups keep repeating low-value text, or the work drifts back into unrelated performance/doc governance
- Validation: `python3 scripts/runtime/growware_preflight.py --json`, targeted tests for changed files, `python3 scripts/runtime/runtime_mirror.py --write`, `python3 scripts/runtime/plugin_doctor.py --json`, `python3 scripts/runtime/plugin_smoke.py --json`, and `python3 scripts/runtime/growware_local_deploy.py --json`

## Execution Tasks

- [x] WU-1 remove the recent performance/documentation side-track from the project's public docs
- [ ] WU-2 fix misleading `wd` receipts, especially queue wording that self-counts or implies the wrong state
- [ ] WU-3 make terminal control-plane follow-ups say only useful things, not generic task-label echoes

## Architecture Supervision

- Signal: `yellow`
- Signal Basis: the runtime is functionally working, but today's host logs still show inaccurate or low-value `wd` feedback that weakens the product's usefulness
- Problem Class: runtime-owned control-plane wording and usefulness, not LLM performance governance
- Root Cause Hypothesis: queue receipts overfit internal counters, and generic terminal follow-ups still leak through when they add no user value
- Correct Layer: fix the runtime-owned rendering rules and keep the message contract accurate and sparse
- Rejected Shortcut: treating user-visible usefulness issues as another documentation or performance topic
- Automatic Review Trigger: any change to `wd` receipt wording, queue-state semantics, terminal control-plane messages, or transcript-sanitization boundaries
- Escalation Gate: continue automatically

## Escalation Model

- Continue Automatically: runtime-owned `wd` wording fixes, targeted validation, mirror sync, and local deploy needed to verify the installed plugin behavior
- Raise But Continue: changes that alter queue semantics or terminal-message policy while keeping the same product boundary
- Require User Decision: any change that weakens required runtime safety, changes product direction, or expands this repo back into unrelated docs/performance tracks

## Slices

- Slice: queue receipt truthfulness
  - Objective: make the first `wd` receipt match the user's real state instead of echoing misleading queue math
  - Dependencies: runtime register decision, queue counters, and same-session routing receipt rendering
  - Risks: wording changes hide useful state or drift from actual scheduler semantics
  - Validation: targeted tests plus today's host-log patterns no longer show self-counted or misleading queue text
  - Exit Condition: first receipts are concise, truthful, and stable across `received`, `queued`, and `running` starts

- Slice: terminal usefulness
  - Objective: stop terminal `wd` follow-ups from repeating low-value task-label echoes
  - Dependencies: finalize hook summaries, visible-output detection, and lifecycle completion rendering
  - Risks: over-suppression could hide the only completion signal in some flows
  - Validation: generic completions stay generic, informative summaries still pass through, and growware-specific completion semantics remain intact
  - Exit Condition: terminal messages add net value instead of restating the original request

## Next Phase Preview

- Planned Phase: `runtime usefulness hardening`
- Why Next: after `wd` truthfulness and terminal usefulness are stable, the repo can continue on more substantive runtime behavior instead of side-track cleanup
- Draft Scope: queue / continuity / watchdog user-facing semantics and higher-signal task progress
- Draft Rule: keep the repo focused on runtime behavior, not unrelated public-doc performance programs

## Development Log Capture

- Trigger Level: high
- Auto-Capture When:
  - the repo changes runtime-owned `wd` semantics or terminal-message policy
  - host logs reveal a new user-visible mismatch between scheduler truth and control-plane wording
  - the repo intentionally removes a public-doc side track from the active project line
- Skip When:
  - the change is mechanical or formatting-only
  - no durable reasoning changed
  - the work simply followed an already-approved measurement path
  - the change stayed local and introduced no durable tradeoff
