#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from main_task_adapter import (
    MainTaskContext,
    block_main_task,
    decide_main_task,
    fail_main_task,
    finish_main_task,
    register_main_task,
    resume_main_task,
    sync_main_progress,
)
from task_config import TaskSystemConfig, load_task_system_config
from task_state import TaskPaths, TaskState, TaskStore, default_paths


@dataclass(frozen=True)
class OpenClawInboundContext:
    agent_id: str
    session_key: str
    channel: str
    account_id: Optional[str]
    chat_id: str
    user_id: Optional[str]
    user_request: str
    estimated_steps: int | None = None
    touches_multiple_files: bool = False
    involves_delegation: bool = False
    requires_external_wait: bool = False
    needs_verification: bool = False


@dataclass(frozen=True)
class BridgeDecision:
    should_register_task: bool
    task_id: Optional[str]
    classification_reason: str
    confidence: str
    task_status: Optional[str] = None
    queue_position: Optional[int] = None
    ahead_count: int = 0
    active_count: int = 0
    running_count: int = 0
    queued_count: int = 0
    continuation_due_at: Optional[str] = None


def build_main_task_context(ctx: OpenClawInboundContext) -> MainTaskContext:
    return MainTaskContext(
        agent_id=ctx.agent_id,
        session_key=ctx.session_key,
        channel=ctx.channel,
        account_id=ctx.account_id,
        chat_id=ctx.chat_id,
        user_id=ctx.user_id,
        user_request=ctx.user_request,
        estimated_steps=ctx.estimated_steps,
        touches_multiple_files=ctx.touches_multiple_files,
        involves_delegation=ctx.involves_delegation,
        requires_external_wait=ctx.requires_external_wait,
        needs_verification=ctx.needs_verification,
    )


def register_inbound_task(
    ctx: OpenClawInboundContext,
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> BridgeDecision:
    runtime_config = config or load_task_system_config(config_path=config_path)
    resolved_paths = paths or runtime_config.build_paths() or default_paths()
    main_ctx = build_main_task_context(ctx)
    decision = decide_main_task(main_ctx, config=runtime_config)
    if not decision.should_register:
        return BridgeDecision(
            should_register_task=False,
            task_id=None,
            classification_reason=decision.reason,
            confidence=decision.classification.confidence,
        )

    store = TaskStore(paths=resolved_paths)
    recoverable = store.find_latest_recoverable_task(
        agent_id=ctx.agent_id,
        session_key=ctx.session_key,
    )
    if recoverable is not None:
        resumed = resume_main_task(
            recoverable.task_id,
            progress_note=f"恢复执行：{ctx.user_request[:120]}",
            paths=store.paths,
        )
        return BridgeDecision(
            should_register_task=True,
            task_id=resumed.task_id,
            classification_reason="resume-blocked-task",
            confidence="high",
            task_status=resumed.status,
            queue_position=1 if resumed.status == "running" else None,
            ahead_count=0 if resumed.status == "running" else 1,
            active_count=len(store.find_inflight_tasks(agent_id=ctx.agent_id, statuses={"queued", "running"})),
            running_count=len(store.find_running_tasks(agent_id=ctx.agent_id)),
            queued_count=len(store.find_queued_tasks(agent_id=ctx.agent_id)),
            continuation_due_at=str(resumed.meta.get("continuation_due_at") or "") or None,
        )

    task = register_main_task(
        main_ctx,
        paths=resolved_paths,
        config=runtime_config,
    )
    active_tasks = store.find_inflight_tasks(agent_id=ctx.agent_id, statuses={"queued", "running"})
    ordered_active = sorted(active_tasks, key=lambda item: item.created_at)
    queue_position = None
    ahead_count = 0
    for index, item in enumerate(ordered_active, start=1):
        if item.task_id == task.task_id:
            queue_position = index
            ahead_count = max(index - 1, 0)
            break
    return BridgeDecision(
        should_register_task=True,
        task_id=task.task_id,
        classification_reason=decision.reason,
        confidence=decision.classification.confidence,
        task_status=task.status,
        queue_position=queue_position,
        ahead_count=ahead_count,
        active_count=len(active_tasks),
        running_count=len(store.find_running_tasks(agent_id=ctx.agent_id)),
        queued_count=len(store.find_queued_tasks(agent_id=ctx.agent_id)),
        continuation_due_at=str(task.meta.get("continuation_due_at") or "") or None,
    )


def record_progress(
    task_id: str,
    *,
    progress_note: Optional[str] = None,
    status: Optional[str] = None,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> TaskState:
    runtime_config = config or load_task_system_config(config_path=config_path)
    return sync_main_progress(
        task_id,
        progress_note=progress_note,
        status=status,
        paths=paths or runtime_config.build_paths() or default_paths(),
    )


def record_blocked(
    task_id: str,
    reason: str,
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> TaskState:
    runtime_config = config or load_task_system_config(config_path=config_path)
    return block_main_task(task_id, reason, paths=paths or runtime_config.build_paths() or default_paths())


def record_completed(
    task_id: str,
    result_summary: Optional[str] = None,
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> TaskState:
    runtime_config = config or load_task_system_config(config_path=config_path)
    return finish_main_task(task_id, result_summary=result_summary, paths=paths or runtime_config.build_paths() or default_paths())


def record_failed(
    task_id: str,
    reason: str,
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> TaskState:
    runtime_config = config or load_task_system_config(config_path=config_path)
    return fail_main_task(task_id, reason, paths=paths or runtime_config.build_paths() or default_paths())
