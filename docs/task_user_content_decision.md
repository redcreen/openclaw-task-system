[English](task_user_content_decision.md) | [中文](task_user_content_decision.zh-CN.md)

# `task_user_content` Decision

## Final Decision

`task_user_content` is no longer an active runtime protocol.

For full Chinese detail and evidence, see [task_user_content_decision.zh-CN.md](task_user_content_decision.zh-CN.md).

## What Remains

The project now keeps only:

- sanitize and hard-block behavior
- historical leak audit
- historical scrub tooling

## Why

The runtime can reliably trust structured planning state.

It cannot reliably trust ad hoc text markers as a stable long-term protocol boundary between user-visible business output and hidden planning state.
