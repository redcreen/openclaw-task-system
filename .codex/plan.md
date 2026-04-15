# Project Plan

## Current Phase

`reply-latency and context-weight governance` is active.

Milestone 2 and Milestone 3 remain closed: compiled `.policy/` is the only live Growware policy truth, the reviewed repo-local performance baseline is green, and the host-side audit remains bootstrap-only evidence. The new active line is a measured governance topic for host-observed reply latency.

## Current Execution Line

- Objective: turn one measured Telegram slowdown into a durable governance topic, add repeatable latency/context audits, and only resume activation prep after the highest-cost prompt paths have an explicit reduction plan
- Plan Link: `docs/reference/openclaw-task-system/development-plan.md#reply-latency-and-context-weight-governance`
- Runway: keep `performance_baseline.py` as the repo-local guardrail, use session-level audits for host-observed slowdown evidence, and isolate prompt/context slimming work from host-only provider variance
- Progress: `1/3`
- Stop Conditions: the topic loses measured evidence, the proposed reductions change business or compatibility promises without review, or the team resumes activation prep before static / transcript cost is bounded
- Validation: `python3 scripts/runtime/performance_baseline.py --profile-scenario hooks-cycle --profile-scenario same-session-routing-classifier --profile-scenario system-overview --profile-top 8 --enforce-budgets --json`, `python3 scripts/runtime/session_latency_audit.py --session-key 'agent:main:telegram:direct:8705812936' --json`, `python3 scripts/runtime/growware_preflight.py --json`, targeted tests for changed files, `bash scripts/run_tests.sh`, `python3 scripts/runtime/runtime_mirror.py --write`, `python3 scripts/runtime/plugin_doctor.py --json`, and `python3 scripts/runtime/plugin_smoke.py --json`

## Execution Tasks

- [x] TG-1 freeze the slowdown trigger and add a repeatable `session_latency_audit.py` entrypoint for turn timing and context-weight evidence
- [ ] TG-2 rank and reduce the largest prompt contributors: tool schema surface, system prompt weight, per-turn wrapper, and startup transcript carryover
- [ ] TG-3 define activation-resume criteria, including what evidence proves the slowdown is no longer a mainline blocker

## Architecture Supervision

- Signal: `yellow`
- Signal Basis: repo-local performance paths remain green, but host-observed reply latency is still user-visible and now has measured context-bloat evidence that must be governed before activation resumes
- Problem Class: prompt-surface and transcript-growth governance on top of a closed repo-local performance milestone
- Root Cause Hypothesis: the main user-visible slowdown is no longer task-system hook cost; it is oversized static prompt plus wrapper plus accumulated transcript driving slow LLM turns
- Correct Layer: add repeatable session audit tooling, treat context slimming as a repo-owned governance topic, and keep host-provider variance visible but separate
- Rejected Shortcut: jumping straight back into live activation prep without a durable explanation of where the extra latency is coming from
- Automatic Review Trigger: any change to system prompt composition, workspace bootstrap files, tool surface exposure, session-startup reads, memory injection, or activation-resume criteria
- Escalation Gate: continue automatically

## Escalation Model

- Continue Automatically: repo-local audit tooling, control-surface updates, docs alignment, and prompt-surface measurements that stay inside the approved governance topic
- Raise But Continue: reductions that change default prompt composition, audit thresholds, or operator expectations while staying inside current product boundaries
- Require User Decision: any live rehearsal launch, local deploy meant to change installed runtime behavior, compatibility promise change, or product-facing tradeoff that deliberately removes user/agent context

## Slices

- Slice: session-level latency evidence
  - Objective: make host-observed slowdown reproducible through one durable audit command instead of manual log forensics
  - Dependencies: session JSONL structure, session metadata, and the measured Telegram trigger case
  - Risks: maintainers keep debating whether the slowdown is “really LLM” because the evidence is not rerunnable
  - Validation: one command reports turn timing, LLM/tool shares, transcript growth, and static prompt weights on a real session
  - Exit Condition: the repo owns a stable latency-attribution entrypoint for future incidents

- Slice: prompt-surface diet
  - Objective: rank and reduce the largest static contributors without deleting required capability blindly
  - Dependencies: system prompt report, tool schema inventory, skill exposure, and workspace bootstrap contract
  - Risks: reducing the wrong context may save tokens while breaking agent behavior or safety boundaries
  - Validation: each proposed cut cites measured prompt weight and its expected latency impact
  - Exit Condition: the top static contributors have an explicit keep / shrink / remove decision

- Slice: startup and transcript discipline
  - Objective: stop the startup turn and later transcript from carrying avoidable weight into every business turn
  - Dependencies: startup file-read path, transcript accumulation behavior, and per-turn wrapper shape
  - Risks: startup convenience or memory quality is silently traded away without review
  - Validation: startup carryover and transcript-growth rules are written down and measurable
  - Exit Condition: the repo has explicit rules for what should not persist into later turns

- Slice: activation resume gate
  - Objective: define when activation prep is allowed back onto the mainline
  - Dependencies: governance evidence, chosen reduction queue, and runtime-safety / performance guardrails
  - Risks: the topic becomes an endless tuning bucket or activation resumes without closing the user-visible blocker
  - Validation: resume criteria, required evidence, and fallback handling are recorded in durable docs
  - Exit Condition: activation prep returns as a bounded next phase instead of an implicit default

## Next Phase Preview

- Planned Phase: `bounded live pilot activation preparation`
- Why Next: after the governance topic fixes or bounds the measured slowdown, activation prep becomes justified again on top of reviewed resume criteria
- Draft Scope: `feishu6-chat` rehearsal entry criteria, explicit local-deploy intent if needed, operator evidence capture, and rollback handling
- Draft Rule: do not resume activation prep until reply-latency evidence and context-budget decisions are explicit

## Development Log Capture

- Trigger Level: high
- Auto-Capture When:
  - a new session-audit or latency-evidence command becomes a reusable repo capability
  - prompt-surface governance changes durable activation or operator assumptions
  - the repo changes what context is injected or persisted across turns
  - the repo moves from activation prep into a governance topic or back again
- Skip When:
  - the change is mechanical or formatting-only
  - no durable reasoning changed
  - the work simply followed an already-approved measurement path
  - the change stayed local and introduced no durable tradeoff
