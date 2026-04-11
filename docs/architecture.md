[English](architecture.md) | [中文](architecture.zh-CN.md)

# Architecture

## Purpose

This document explains the runtime shape of `openclaw-task-system`:

- which layers exist
- which state belongs to the task-system truth source
- how `[wd]`, follow-up, watchdog, continuity, and final business output stay coordinated

For the full Chinese detail, see [architecture.zh-CN.md](architecture.zh-CN.md).

## Architectural Goals

The project keeps these boundaries:

- do not modify OpenClaw core
- do not require host patches
- do not depend on modifying other plugins
- work through this repository's plugin, runtime, state, and existing extension points

The system exists to separate:

- message flow from task flow
- control-plane output from normal reply output
- runtime truth from transient executor behavior

## Main Layers

| Layer | Responsibility |
| --- | --- |
| Producer / Admission | decide whether a message becomes a managed task |
| Task Truth Source | store tasks, queue identity, continuity metadata, and projections |
| Control-Plane Lane | send `[wd]`, progress, follow-up, watchdog, and terminal control-plane messages |
| Execution Path | reuse the underlying agent / LLM path for actual work |
| Projection / Ops | expose the same truth to users and operators through status and ops views |

## Core Contracts

- the first `[wd]` is runtime-owned
- future-action promises must correspond to a real task or structured planning state
- internal planning state is not sent directly to the user
- control-plane output and business output are projected separately

## Current Focus Areas

The current shipped architecture explicitly includes:

- same-session routing
- future-first planning contracts
- planning anomaly projection and recovery hints
- install drift visibility between source payload and local installed runtime

## Related Docs

- [roadmap.md](roadmap.md)
- [llm_tool_task_planning.md](llm_tool_task_planning.md)
- [compound_followup_boundary.md](compound_followup_boundary.md)
