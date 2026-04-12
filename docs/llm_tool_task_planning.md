[English](llm_tool_task_planning.md) | [中文](llm_tool_task_planning.zh-CN.md)

# LLM-Assisted Task Planning And Follow-Up Tools

> Status: design draft
> Scope: compound requests, delayed follow-up planning, and tool-assisted task decomposition

## Review Constraints

Treat these as fixed unless they are explicitly re-reviewed:

- task-system supervises execution; it does not replace the original executor
- ordinary request understanding stays on the main agent or LLM path
- the runtime should not keep growing a front-door simple-versus-complex classifier
- `[wd]`, fixed progress nudges, fallback text, and recovery text stay runtime-owned
- every future promise must be backed by a real task in the truth source
- if planning fails, times out, or is skipped, the user must be told plainly
- absolute due time is the authoritative scheduling field
- tool-chain internals are not user output
- regex or text cleanup is not an acceptable long-term fix

## Hard Rule: Tool State Is Not User Output

These are not normal user-visible business output:

- plan IDs
- promise guards
- schedule accepted or rejected state
- follow-up task IDs
- raw tool results

They must first flow into the task system and then be projected as one of two things:

1. runtime-owned control-plane output such as `[wd]`
2. real business content, either now or at the actual follow-up time

## Problem

Some requests contain multiple task intents in one message:

- do something now
- do something later
- sometimes make the later step depend on whether the first step succeeded

Examples:

- `check the weather, then reply in five minutes`
- `summarize this first, then remind me to review the result later`
- `run a check now and come back in half an hour if it still fails`

Regex can cover a few low-ambiguity cases, but it is not the durable solution.

## Goals

- keep the fast control-plane path
- avoid forcing every request through planning first
- let the LLM create structured follow-up state when it truly needs to
- detect when the model promised future work without creating a real task
- keep the task-system runtime as the final truth source
- fail honestly when the planning path is unhealthy

## Non-Goals

- moving `[wd]` generation into the LLM
- requiring a tool call before every first acknowledgement
- treating free-form promises as proof that a delayed task exists
- replacing deterministic handling for simple, low-risk delayed replies

## Recommended Model

The preferred model is hybrid:

1. deterministic runtime fast path
2. tool-assisted planning path
3. runtime verification and fallback

That is more robust than either extreme:

- regex-only is too brittle
- tool-only is too optimistic about planner reliability

## Why `[wd]` Stays Outside The LLM

`[wd]` is a control-plane acknowledgement, not a planning artifact.

It must stay outside the LLM because:

1. it must appear quickly
2. it cannot wait on planning or tool latency
3. it still has to work when the planner times out or skips a tool

The sequence should remain:

```text
message received
  -> register / pre-register
  -> send [wd]
  -> choose execution path
       - deterministic runtime fast path
       - or LLM-assisted planning path
```

## When Tools Are Required

The runtime should not ask the LLM to self-route every request. Instead:

- normal immediate work stays on the original agent path
- the agent must call task-system tools when it wants to create a future promise
- delayed follow-up, reminders, and dependent continuation should default to tool-backed planning

In short:

```text
request -> agent / LLM understanding
if future action is being promised -> task-system tools are mandatory
runtime supervises and verifies the contract
```

## Suggested Tool Surface

| Tool | Purpose |
| --- | --- |
| `ts_get_task_planning_context` | fetch task or session context for planning |
| `ts_create_followup_plan` | record a structured delayed or dependent follow-up plan |
| `ts_schedule_followup_from_plan` | materialize a real scheduled follow-up task |
| `ts_attach_promise_guard` | arm a runtime expectation that a promised future action must be fulfilled |
| `ts_finalize_planned_followup` | close the guard by linking the real follow-up task back to the source task |

## Prompt Contract

The system prompt should make these rules explicit:

- runtime owns the first `[wd]`
- runtime owns fixed 30-second progress nudges
- runtime owns fallback and recovery control-plane text unless it delegates otherwise
- future promises, delayed follow-up, reminders, and dependent continuation should be tool-first
- the model must not say `I'll come back later` unless the runtime accepted a real scheduled follow-up
- if a scheduling tool fails, times out, or is skipped, the model must say so plainly
- if the request is ambiguous, ask instead of silently inventing a delayed task

## Runtime Monitoring And Fallback

Even with tools, the runtime must assume the planner can:

- time out
- skip a tool
- choose the wrong tool
- promise a future action without creating a task

The runtime therefore still needs:

- planner-health monitoring
- promise-without-task detection
- expectation-guard enforcement
- deterministic fallback scheduling for low-risk cases
- truthful overdue or recovered follow-up projection when `now > due_at`

## Minimum Closure Already Shipped

The repository already ships the minimum baseline needed for this direction:

- structured planning state and materialized follow-up tasks
- future-first output control under `main_user_content_mode`
- planning anomaly projection in ops views
- stable acceptance coverage for the planning closure
