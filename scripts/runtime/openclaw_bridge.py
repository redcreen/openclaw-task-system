#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
    estimated_wait_seconds: Optional[int] = None
    continuation_due_at: Optional[str] = None

    def to_payload(self) -> dict[str, object]:
        return asdict(self)


def _queue_sort_key(task: TaskState) -> tuple[int, str, str]:
    state = task.status
    if state == "running":
        priority = 0
    elif state == "queued":
        priority = 1
    elif state == "received":
        priority = 2
    else:
        priority = 3
    anchor = str(task.started_at or task.created_at or "")
    return (priority, anchor, str(task.task_id))


def _queue_metrics(
    store: TaskStore,
    *,
    agent_id: str,
    task_id: Optional[str],
) -> tuple[Optional[int], int, int, int, int]:
    queue_tasks = store.find_inflight_tasks(agent_id=agent_id, statuses={"received", "queued", "running"})
    ordered_queue = sorted(queue_tasks, key=_queue_sort_key)
    queue_position = None
    ahead_count = 0
    for index, item in enumerate(ordered_queue, start=1):
        if item.task_id == task_id:
            queue_position = index
            ahead_count = max(index - 1, 0)
            break
    running_count = sum(1 for item in ordered_queue if item.status == "running")
    queued_count = sum(1 for item in ordered_queue if item.status in {"queued", "received"})
    active_count = len(ordered_queue)
    return queue_position, ahead_count, active_count, running_count, queued_count


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _estimate_wait_seconds(
    store: TaskStore,
    *,
    agent_id: str,
    queue_position: Optional[int],
    task_status: Optional[str],
    classification_reason: Optional[str] = None,
) -> Optional[int]:
    if task_status not in {"received", "queued", "running"}:
        return None
    if queue_position is None or queue_position < 1:
        return None
    if str(classification_reason or "").strip() == "observed-task":
        return None

    samples: list[int] = []
    for path in sorted(store.paths.archive_dir.glob("*.json"), reverse=True):
        try:
            task = store.load_task(path.stem, allow_archive=True)
        except FileNotFoundError:
            continue
        if task.agent_id != agent_id or task.status != "done":
            continue
        anchor = _parse_iso8601(task.started_at or task.created_at)
        finished = _parse_iso8601(task.updated_at)
        if anchor is None or finished is None:
            continue
        duration_seconds = int((finished - anchor).total_seconds())
        if duration_seconds < 1 or duration_seconds > 1800:
            continue
        samples.append(duration_seconds)
        if len(samples) >= 7:
            break

    if not samples:
        return None

    ordered = sorted(samples)
    typical_seconds = ordered[len(ordered) // 2]
    slots_ahead = max(queue_position - 1, 0)
    if task_status == "running":
        slots_ahead = 0
    estimate = max(typical_seconds * (slots_ahead + 1), typical_seconds)
    return estimate


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
    observe_only: bool = False,
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
    if recoverable is not None and decision.reason != "continuation-task":
        continuation_kind = str(recoverable.meta.get("continuation_kind") or "").strip()
        continuation_due_at = str(recoverable.meta.get("continuation_due_at") or "").strip()
        if continuation_kind and continuation_due_at:
            try:
                due_dt = datetime.fromisoformat(continuation_due_at)
            except ValueError:
                due_dt = None
            now_dt = datetime.now(timezone.utc).astimezone()
            if due_dt is not None and due_dt > now_dt:
                _, _, active_count, running_count, queued_count = _queue_metrics(
                    store,
                    agent_id=ctx.agent_id,
                    task_id=recoverable.task_id,
                )
                return BridgeDecision(
                    should_register_task=True,
                    task_id=recoverable.task_id,
                    classification_reason="scheduled-continuation",
                    confidence="high",
                    task_status=recoverable.status,
                    queue_position=None,
                    ahead_count=0,
                    active_count=active_count,
                    running_count=running_count,
                    queued_count=queued_count,
                    estimated_wait_seconds=None,
                    continuation_due_at=continuation_due_at,
                )
        resumed = resume_main_task(
            recoverable.task_id,
            progress_note=f"恢复执行：{ctx.user_request[:120]}",
            paths=store.paths,
        )
        _, _, active_count, running_count, queued_count = _queue_metrics(
            store,
            agent_id=ctx.agent_id,
            task_id=resumed.task_id,
        )
        return BridgeDecision(
            should_register_task=True,
            task_id=resumed.task_id,
            classification_reason="resume-blocked-task",
            confidence="high",
            task_status=resumed.status,
            queue_position=1 if resumed.status == "running" else None,
            ahead_count=0 if resumed.status == "running" else 1,
            active_count=active_count,
            running_count=running_count,
            queued_count=queued_count,
            estimated_wait_seconds=_estimate_wait_seconds(
                store,
                agent_id=ctx.agent_id,
                queue_position=1 if resumed.status == "running" else None,
                task_status=resumed.status,
                classification_reason="resume-blocked-task",
            ),
            continuation_due_at=str(resumed.meta.get("continuation_due_at") or "") or None,
        )

    task = register_main_task(
        main_ctx,
        paths=resolved_paths,
        config=runtime_config,
        observe_only=observe_only,
    )
    queue_position, ahead_count, active_count, running_count, queued_count = _queue_metrics(
        store,
        agent_id=ctx.agent_id,
        task_id=task.task_id,
    )
    return BridgeDecision(
        should_register_task=True,
        task_id=task.task_id,
        classification_reason=decision.reason,
        confidence=decision.classification.confidence,
        task_status=task.status,
        queue_position=queue_position,
        ahead_count=ahead_count,
        active_count=active_count,
        running_count=running_count,
        queued_count=queued_count,
        estimated_wait_seconds=_estimate_wait_seconds(
            store,
            agent_id=ctx.agent_id,
            queue_position=queue_position,
            task_status=task.status,
            classification_reason=decision.reason,
        ),
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
