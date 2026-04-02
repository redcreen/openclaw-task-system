#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from task_policy import ContinuationPlan, TaskClassification, classify_main_task, parse_delayed_reply_request
from task_config import TaskSystemConfig, load_task_system_config
from task_state import TaskPaths, TaskState, TaskStore, default_paths


@dataclass(frozen=True)
class MainTaskContext:
    agent_id: str
    session_key: str
    channel: str
    account_id: Optional[str]
    chat_id: str
    user_request: str
    user_id: Optional[str] = None
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


def detect_continuation_plan(context: MainTaskContext) -> ContinuationPlan | None:
    return parse_delayed_reply_request(context.user_request)


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
    should_register = classification.is_long_task
    reason = "long-task" if should_register else "short-task"
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
) -> TaskState:
    runtime_config = config or load_task_system_config()
    store = TaskStore(paths=paths or runtime_config.build_paths() or default_paths())
    task = store.register_task(
        agent_id=context.agent_id,
        session_key=context.session_key,
        channel=context.channel,
        account_id=context.account_id,
        chat_id=context.chat_id,
        user_id=context.user_id,
        task_label=context.user_request[:80],
        meta={
          "source": "main-task-adapter",
          "estimated_steps": context.estimated_steps,
          "touches_multiple_files": context.touches_multiple_files,
          "involves_delegation": context.involves_delegation,
          "requires_external_wait": context.requires_external_wait,
          "needs_verification": context.needs_verification,
        },
    )
    continuation = detect_continuation_plan(context)
    if continuation is not None:
        return store.schedule_continuation(
            task.task_id,
            continuation_kind=continuation.kind,
            due_at=continuation.due_at,
            payload={
                "reply_text": continuation.reply_text,
                "wait_seconds": continuation.wait_seconds,
            },
            reason="scheduled continuation wait",
        )
    if runtime_config.agent_config(context.agent_id).auto_start:
        return store.claim_execution_slot(task.task_id)
    return task


def sync_main_progress(
    task_id: str,
    *,
    status: Optional[str] = None,
    progress_note: Optional[str] = None,
    paths: Optional[TaskPaths] = None,
) -> TaskState:
    store = TaskStore(paths=paths or default_paths())
    meta = {"last_progress_note": progress_note} if progress_note else None
    return store.touch_task(task_id, user_visible=True, status=status, meta=meta)


def finish_main_task(
    task_id: str,
    *,
    result_summary: Optional[str] = None,
    paths: Optional[TaskPaths] = None,
) -> TaskState:
    store = TaskStore(paths=paths or default_paths())
    meta = {"result_summary": result_summary} if result_summary else None
    return store.complete_task(task_id, meta=meta)


def block_main_task(
    task_id: str,
    reason: str,
    *,
    paths: Optional[TaskPaths] = None,
) -> TaskState:
    store = TaskStore(paths=paths or default_paths())
    return store.block_task(task_id, reason)


def resume_main_task(
    task_id: str,
    *,
    progress_note: Optional[str] = None,
    paths: Optional[TaskPaths] = None,
) -> TaskState:
    store = TaskStore(paths=paths or default_paths())
    return store.resume_task(task_id, progress_note=progress_note)


def fail_main_task(
    task_id: str,
    reason: str,
    *,
    paths: Optional[TaskPaths] = None,
) -> TaskState:
    store = TaskStore(paths=paths or default_paths())
    return store.fail_task(task_id, reason)
