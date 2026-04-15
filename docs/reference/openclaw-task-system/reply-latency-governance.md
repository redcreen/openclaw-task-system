[English](reply-latency-governance.md) | [中文](reply-latency-governance.zh-CN.md)

# Reply Latency Governance

## Purpose

This document records the current governance topic for host-observed reply latency.

Use it when maintainers need one durable place to answer:

- why the repo reopened a performance-adjacent line even after Milestone 3 closed
- what evidence says the slowdown is really happening
- which contributors are large enough to deserve optimization work
- what must be true before activation preparation resumes

## Trigger

The trigger is a real Telegram session after `2026-04-15 23:44` that showed reply times of roughly `16s-50s` while repo-local benchmark paths remained green.

Measured observations from that trigger:

- LLM segments dominated total latency
- tool time was secondary and only large in one turn
- static context was about `140,465 chars`
- tool schema surface was the single largest static block
- startup and transcript growth pushed extra context into later turns

## Durable Audit Entry Point

Use the repo-owned audit command instead of manual log dissection:

```bash
python3 scripts/runtime/session_latency_audit.py --session-key 'agent:main:telegram:direct:8705812936' --json
```

The audit reports:

- turn-by-turn total duration
- LLM time vs tool time
- transcript chars before each turn
- startup transcript carryover
- static prompt composition from `sessions.json`
- top tool / workspace / skill contributors

## Current Attribution

The current measured attribution is:

1. static prompt weight
2. per-turn wrapper tax
3. startup transcript carryover
4. transcript growth over the life of the session
5. residual tool cost in a minority of turns

This means the dominant user-visible slowdown is not the repo's hot-path task lifecycle code. The current user-visible cost is mostly the model paying to process oversized context.

## Governance Queue

### P0: Static Prompt Diet

- tool schema surface
- system prompt weight
- unnecessary skill exposure
- workspace bootstrap files that do not need to ride in every turn

### P0: Wrapper And Startup Diet

- per-turn task-system wrapper shape
- startup read behavior
- what startup artifacts should stop persisting into later transcript

### P1: Transcript Growth Discipline

- which earlier artifacts should be summarized instead of kept verbatim
- what later turns should stop inheriting by default

### P1: Activation Resume Gate

- what evidence proves the slowdown is bounded
- what must stay green while returning to bounded activation preparation

## Resume Criteria

Activation preparation may return as the active mainline only after:

- the trigger session is reproducible through the audit command
- the largest prompt/context contributors have explicit keep / shrink / remove decisions
- chosen reductions preserve required runtime safety and agent capability
- the repo records what latency/context evidence counts as good enough to treat the slowdown as bounded

## Validation

Run the governance topic on top of the existing repo-local guardrails:

```bash
python3 scripts/runtime/performance_baseline.py --profile-scenario hooks-cycle --profile-scenario same-session-routing-classifier --profile-scenario system-overview --profile-top 8 --enforce-budgets --json
python3 scripts/runtime/session_latency_audit.py --session-key 'agent:main:telegram:direct:8705812936' --json
python3 scripts/runtime/growware_preflight.py --json
python3 -m unittest tests.test_session_latency_audit tests.test_performance_baseline -v
python3 scripts/runtime/runtime_mirror.py --write
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
```
