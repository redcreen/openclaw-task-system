# Project Brief

## Delivery Tier
- Tier: `medium`
- Why this tier: multi-session maintenance needs a lightweight but durable control surface
- Last reviewed: 2026-04-12

## Outcome

Turn OpenClaw from a chat-only flow into a task-supervised runtime that can accept, track, recover, and complete user-visible tasks with truthful control-plane feedback.

## Scope

- OpenClaw plugin runtime and task truth source
- `[wd]`, follow-up, watchdog, continuity, and terminal control-plane projection
- Queue, lane, dashboard, triage, planning acceptance, and related operator tooling
- Installation, validation, and durable documentation for maintainers and operators

## Non-Goals

- Replacing the original agent / LLM execution path
- Requiring changes to OpenClaw core or host code
- Turning the project into a general-purpose orchestrator

## Constraints

- Must work through existing plugin and runtime extension points
- User-visible control-plane messages must stay outside the free-form LLM path
- Future promises must map to real persisted tasks
- Release-quality changes must keep the automated testsuite green

## Definition of Done

- architecture retrofit notes, plan, and status match the actual repo boundary decisions
- `./scripts/run_tests.sh` passes
- Public docs provide a clear English/Chinese landing path
- current runtime boundaries, execution line, and next maintenance slice are visible from `.codex/status.md`
