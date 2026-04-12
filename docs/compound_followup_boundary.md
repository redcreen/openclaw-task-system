[English](compound_followup_boundary.md) | [中文](compound_followup_boundary.zh-CN.md)

# Compound Follow-Up Boundary

> Status: open design boundary
> Scope: delayed replies and continuation semantics inside compound-intent requests

## Problem

The current task system already handles two request shapes reliably:

1. work that should start immediately
2. a clear, single-intent delayed reply such as `reply 333 in 3 minutes`

Compound requests blur that line:

- `check the weather, then reply to me in five minutes`
- `handle this now, then remind me to review the result later`
- `look into this first, then come back and continue`

Those requests contain at least two intent fragments:

- immediate work
- a delayed or dependent follow-up

## Why Regex Growth Is Not The Fix

This is not a problem that converges by adding more phrase rules for words like `then`, `later`, or `reply me`.

That path fails because:

1. natural language remains open-ended
2. the delayed part may be vague or conditional
3. the follow-up may depend on whether the first step succeeds
4. one message may contain more than two intent fragments
5. a rule that helps one sentence can misroute another

This is fundamentally a planning problem, not a long-term regex problem.

## Current Shipped Boundary

What the repository supports today:

- clear single-intent delayed replies as a first-class runtime capability
- a supervisor-first contract where the runtime verifies whether a promised future action became a real task
- acceptance coverage proving that compound requests must not silently create hidden follow-up state without a structured plan

What it intentionally does not promise:

- broad automatic support for mixed-intent compound requests
- silent runtime materialization of hidden follow-up tasks from legacy post-run phrasing
- turning the task system into a universal front-door semantic classifier

## Long-Term Direction

The durable direction is to split a request into structured work:

```text
user request
  -> intent decomposition
  -> task plan
       - immediate task
       - delayed follow-up task
       - dependency and ordering
  -> task-system runtime
```

That keeps the responsibilities clean:

- the agent or LLM continues to understand the request
- planning creates explicit structured state
- the runtime creates and supervises the real task graph

## Why This Boundary Matters

Without a clear boundary, the system drifts toward:

- more hard-coded phrase rules
- more brittle delayed follow-up behavior
- free-form promises from the agent that the runtime never backed with a scheduled task

The core task-system contract must remain:

> if the system promises to do something later, the truth source must contain a real scheduled task behind that promise

## Next Design Question

A strong next step is to expose task creation and follow-up scheduling as explicit tools that the agent can call when it wants to create a future promise.

That would support:

- normal immediate execution
- explicit delayed follow-up creation
- multi-step task decomposition

without growing the runtime into a phrase-driven orchestrator.
