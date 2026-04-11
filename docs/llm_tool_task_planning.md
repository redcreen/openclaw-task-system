[English](llm_tool_task_planning.md) | [中文](llm_tool_task_planning.zh-CN.md)

# LLM Tool Task Planning

## Purpose

This document captures the current planning direction:

- keep the task system supervisor-first
- keep `[wd]`, fixed progress messages, and recovery text runtime-owned
- let future-action planning use structured tools instead of text cleanup

For full Chinese detail, see [llm_tool_task_planning.zh-CN.md](llm_tool_task_planning.zh-CN.md).

## Current Accepted Direction

- the main LLM should not freely own task-system control-plane decisions
- planning should create structured state that the runtime can verify
- future-first output must obey `main_user_content_mode`
- promises without real tasks must surface as anomalies

## Minimum Closure Already Shipped

- structured planning state and materialized follow-up tasks
- future-first output control
- planning anomaly projection in ops views
- stable acceptance coverage for the minimum planning closure
