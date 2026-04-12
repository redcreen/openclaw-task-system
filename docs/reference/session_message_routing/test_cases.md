[English](test_cases.md) | [中文](test_cases.zh-CN.md)

# Test Cases

## Purpose

This document records the reference test cases for same-session routing.

## Core Case Table

| Case | Initial state | Follow-up message | Classification | Decision |
| --- | --- | --- | --- | --- |
| A | no active task | `check Hangzhou weather` | `queueing` | `queue-as-new-task` |
| B | active task queued but not started | `also bias it toward product-manager language` | `steering` | `merge-before-start` |
| C | active task running with no side effects | `make it more conversational` | `steering` | `interrupt-and-restart` |
| D | active task already wrote files | `add one more concluding section` | `steering` | `append-as-next-step` |
| E | active task running | `also check Hangzhou weather` | `queueing` | `queue-as-new-task` |
| F | no active task or queued task | `wait, I still have two more lines to send` | `collect-more` | `enter-collecting-window` |
| G | any active task | `continue` | `control-plane` | `handle-as-control-plane` |

## Ambiguous Cases That Should Trigger The Classifier

| Case | Message | Why it is ambiguous |
| --- | --- | --- |
| H | `add a bit more business perspective` | could refine the current draft or ask for a new analysis |
| I | `give me one more version` | could mean continue the active task or create a separate deliverable |
| J | `review this one too` | depends on prior context and reference resolution |

These cases are not about one fixed final answer. They exist to prove:

- runtime recognizes them as ambiguous
- runtime invokes the classifier
- runtime still produces a visible routing trace and `[wd]`

## Receipt-Coherence Regression Cases

Keep explicit regression coverage for these edges:

- a stale queue acknowledgement must not suppress a fresh runtime-owned routing `[wd]`
- an observed placeholder task must still be reusable as a pre-start takeover target when the new message is the first real request in the session

## Validation Layers

Split the tests into three layers:

1. pure contract tests for classification, decision, and receipt template selection
2. classifier-trigger tests for ambiguous versus obvious cases
3. end-to-end session tests for queue state, routing trace, and user-visible receipt behavior
