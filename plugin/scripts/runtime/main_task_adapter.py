#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from task_policy import TaskClassification, classify_main_task
from task_config import TaskSystemConfig, load_task_system_config
from task_state import STATUS_QUEUED, STATUS_RUNNING, TaskPaths, TaskState, TaskStore, default_paths, now_iso


@dataclass(frozen=True)
class MainTaskContext:
    agent_id: str
    session_key: str
    channel: str
    account_id: Optional[str]
    chat_id: str
    user_request: str
    user_id: Optional[str] = None
    reply_to_id: Optional[str] = None
    thread_id: Optional[str] = None
    estimated_steps: int | None = None
    touches_multiple_files: bool = False
    involves_delegation: bool = False
    requires_external_wait: bool = False
    needs_verification: bool = False


@dataclass(frozen=True)
class MainTaskDecision:
    classification: TaskClassification
    should_register: bool
    reason: str


def is_control_command_request(user_request: str) -> bool:
    normalized = user_request.strip()
    if not normalized.startswith("/"):
        return False
    parts = normalized.split(maxsplit=1)
    command = parts[0]
    remainder = parts[1].strip() if len(parts) > 1 else ""
    if len(command) <= 1:
        return False
    # Treat bare slash commands and flag-style command invocations as transport/control
    # requests, not user work that should enter the main task queue.
    if not remainder:
        return True
    return remainder.startswith("-")


def decide_main_task(
    context: MainTaskContext,
    *,
    config: Optional[TaskSystemConfig] = None,
) -> MainTaskDecision:
    runtime_config = config or load_task_system_config()
    if not runtime_config.enabled:
        return MainTaskDecision(
            classification=TaskClassification(is_long_task=False, confidence="low", reasons=["system-disabled"]),
            should_register=False,
            reason="task-system-disabled",
        )

    agent_config = runtime_config.agent_config(context.agent_id)
    if not agent_config.enabled:
        return MainTaskDecision(
            classification=TaskClassification(is_long_task=False, confidence="low", reasons=["agent-disabled"]),
            should_register=False,
            reason="agent-disabled",
        )

    if is_control_command_request(context.user_request):
        return MainTaskDecision(
            classification=TaskClassification(is_long_task=False, confidence="high", reasons=["control-command"]),
            should_register=False,
            reason="control-command",
        )

    policy = agent_config.classification
    classification = classify_main_task(
        context.user_request,
        estimated_steps=context.estimated_steps,
        touches_multiple_files=context.touches_multiple_files,
        involves_delegation=context.involves_delegation,
        requires_external_wait=context.requires_external_wait,
        needs_verification=context.needs_verification,
        min_request_length=policy.min_request_length,
        min_reason_count=policy.min_reason_count,
        estimated_steps_threshold=policy.estimated_steps_threshold,
        keywords=policy.keywords,
    )
    should_register = True
    reason = "long-task" if classification.is_long_task else "observed-task"
    return MainTaskDecision(
        classification=classification,
        should_register=should_register,
        reason=reason,
    )


def register_main_task(
    context: MainTaskContext,
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    observe_only: bool = False,
    store: Optional[TaskStore] = None,
    has_running_task: Optional[bool] = None,
) -> TaskState:
    runtime_config = config or load_task_system_config()
    store = store or TaskStore(paths=paths or runtime_config.build_paths() or default_paths())
    decision = decide_main_task(context, config=runtime_config)
    task = store.observe_task(
        agent_id=context.agent_id,
        session_key=context.session_key,
        channel=context.channel,
        account_id=context.account_id,
        chat_id=context.chat_id,
        user_id=context.user_id,
        task_label=context.user_request[:80],
        meta={
          "source": "main-task-adapter",
          "original_user_request": context.user_request,
          "source_reply_to_id": context.reply_to_id,
          "source_thread_id": context.thread_id,
          "estimated_steps": context.estimated_steps,
          "touches_multiple_files": context.touches_multiple_files,
          "involves_delegation": context.involves_delegation,
          "requires_external_wait": context.requires_external_wait,
          "needs_verification": context.needs_verification,
        },
    )
    if runtime_config.agent_config(context.agent_id).auto_start and not observe_only:
        if has_running_task is None:
            return store.claim_execution_slot(task.task_id)
        ts = now_iso()
        if has_running_task:
            task.status = STATUS_QUEUED
            task.updated_at = ts
            task.last_internal_touch_at = ts
            return store.save_task(task)
        task.status = STATUS_RUNNING
        task.started_at = task.started_at or ts
        task.updated_at = ts
        task.last_internal_touch_at = ts
        task.last_user_visible_update_at = ts
        task.monitor_state = "normal"
        return store.save_task(task)
    return task


def sync_main_progress(
    task_id: str,
    *,
    status: Optional[str] = None,
    progress_note: Optional[str] = None,
    paths: Optional[TaskPaths] = None,
    store: Optional[TaskStore] = None,
) -> TaskState:
    store = store or TaskStore(paths=paths or default_paths())
    note = str(progress_note or "").strip()
    meta = None
    if note:
        task = store.load_task(task_id)
        current_count = task.meta.get("progress_update_count")
        try:
            progress_update_count = int(current_count)
        except (TypeError, ValueError):
            progress_update_count = 0
        meta = {
            "last_progress_note": note,
            "last_progress_note_at": now_iso(),
            "progress_update_count": max(progress_update_count, 0) + 1,
        }
    return store.touch_task(task_id, user_visible=True, status=status, meta=meta)


def finish_main_task(
    task_id: str,
    *,
    result_summary: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
    paths: Optional[TaskPaths] = None,
    store: Optional[TaskStore] = None,
) -> TaskState:
    store = store or TaskStore(paths=paths or default_paths())
    final_meta = dict(meta or {})
    if result_summary:
        final_meta["result_summary"] = result_summary
    return store.complete_task(task_id, meta=final_meta or None)


def block_main_task(
    task_id: str,
    reason: str,
    *,
    paths: Optional[TaskPaths] = None,
    store: Optional[TaskStore] = None,
) -> TaskState:
    store = store or TaskStore(paths=paths or default_paths())
    return store.block_task(task_id, reason)


def resume_main_task(
    task_id: str,
    *,
    progress_note: Optional[str] = None,
    paths: Optional[TaskPaths] = None,
    store: Optional[TaskStore] = None,
    has_running_task: Optional[bool] = None,
) -> TaskState:
    store = store or TaskStore(paths=paths or default_paths())
    if has_running_task is None:
        return store.resume_task(task_id, progress_note=progress_note)
    task = store.load_task(task_id)
    ts = now_iso()
    task.status = STATUS_QUEUED if has_running_task else STATUS_RUNNING
    task.block_reason = None
    task.monitor_state = "normal"
    task.updated_at = ts
    task.last_internal_touch_at = ts
    task.last_user_visible_update_at = ts
    if progress_note:
        task.meta["last_progress_note"] = progress_note
    task.meta["resumed_at"] = ts
    task.meta["resume_target_status"] = task.status
    return store.save_task(task)


def fail_main_task(
    task_id: str,
    reason: str,
    *,
    meta: Optional[dict[str, Any]] = None,
    paths: Optional[TaskPaths] = None,
    store: Optional[TaskStore] = None,
) -> TaskState:
    store = store or TaskStore(paths=paths or default_paths())
    return store.fail_task(task_id, reason, meta=meta)
