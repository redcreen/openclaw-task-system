[English](decision_contract.md) | [中文](decision_contract.zh-CN.md)

# Decision Contract

## Purpose

This document defines the runtime-owned decision contract for same-session routing.

## Message Classification

| Classification | Meaning | Enters the ordinary task path? |
| --- | --- | --- |
| `control-plane` | status, cancel, pause, resume, continue, or other operator-style commands | no |
| `steering` | a refinement, correction, or constraint on the active task | depends on execution stage |
| `queueing` | a new independent task | yes |
| `collect-more` | the user explicitly wants the system to wait for more input before starting | not yet |

## Execution Decision

When the classification is not `control-plane`, runtime still has to choose the execution action:

| Decision | Meaning |
| --- | --- |
| `merge-before-start` | the task has not really started yet, so merge directly |
| `interrupt-and-restart` | the task is running but is still safe to restart |
| `append-as-next-step` | the task already has side effects, so keep the new message as the next step |
| `queue-as-new-task` | create a separate queued task |
| `enter-collecting-window` | hold execution and wait for the user to finish sending context |
| `handle-as-control-plane` | treat the message as control-plane |

## Ownership By Layer

- runtime decides whether the classifier is needed
- the classifier only returns structured semantic classification
- runtime decides the final execution action
- runtime renders the final `[wd]` receipt
- the main business LLM does not own lane, queue, or interrupt semantics here

## When The Classifier Runs

By default, do not ask the classifier on every message.

Use it only when all of the following are true:

1. there is already an active task in the same session
2. the new message is not obviously `control-plane`
3. the new message is not obviously `collect-more`
4. deterministic rules cannot safely tell `steering` from `queueing`

Do not use it for these obvious cases:

- `continue`, `stop`, `status`, `cancel`
- `wait, I am still sending more`
- an ordinary new message when there is no active task
- a clearly independent new goal

## Execution-Stage Gate

Semantic classification alone is not enough. Runtime must still gate the action by task stage:

| Active task stage | Preferred action |
| --- | --- |
| `received` / `queued` | `merge-before-start` |
| `running-no-side-effects` | `interrupt-and-restart` |
| `running-with-side-effects` | `append-as-next-step` or `queue-as-new-task` |
| `paused` / `continuation` | prefer `append-as-next-step` or `queue-as-new-task` |

This keeps one distinction explicit:

> `interruption` is the user-facing semantic; merge, restart, append, or queue is the runtime-owned execution decision.

## `[wd]` Receipt Contract

Every same-session automatic routing decision must produce a runtime-owned `[wd]` that says:

1. what the system did
2. why it did it
3. enough concrete detail to be believable without exposing internals

Example structure:

```json
{
  "decision": "interrupt-and-restart",
  "reason_code": "active-task-safe-restart",
  "reason_text": "This follow-up changes the active task and the current run is still safe to restart.",
  "target_task_id": "task_xxx",
  "user_visible_wd": "[wd] I restarted the current task with this update because the current run was still safe to rewrite."
}
```

## Low-Confidence Fallback

When the classifier times out, errors, or returns low confidence, runtime should not pretend it understood.

Recommended fallback order:

1. obvious control-plane still goes to control-plane
2. obvious collect-more still enters collecting
3. if the active task already has side effects, default toward `queue-as-new-task`
4. if the active task has not started, default toward `merge-before-start`
5. ask a short confirmation only for high-risk ambiguity
