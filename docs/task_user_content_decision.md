[English](task_user_content_decision.md) | [中文](task_user_content_decision.zh-CN.md)

# `task_user_content` Decision

## Final Decision

`task_user_content` is no longer an active long-term runtime protocol boundary.

The durable decision is broader than a single tag:

- runtime-owned control-plane state must stay separate from business content
- user-visible business content must travel through an explicit controlled channel
- tool metadata and planning state must not leak into the main answer

## What Remains

The project now keeps only:

- sanitize and hard-block behavior
- historical leak audit
- historical scrub tooling

## Why

The runtime can reliably trust structured planning state.

It cannot reliably trust ad hoc text markers as a durable protocol boundary between user-visible output and hidden planning state.

## Accepted Replacement Direction

The accepted architecture is output-channel separation:

- scheduling and control-plane truth stay in runtime state first
- runtime projects that state into `[wd]` or other control-plane messages
- business content is emitted separately and only when it is safe to show

That solves the real problem at the channel boundary instead of trying to keep one magic tag alive forever.

## Operational Consequence

This repository still keeps validation around `task_user_content` history for one reason: to make sure old leakage patterns do not silently return while the runtime continues migrating toward cleaner structured output gates.
