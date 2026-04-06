#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from task_policy import (
    ContinuationPlan,
    TaskClassification,
    classify_main_task,
    parse_delayed_reply_request,
    parse_post_run_delayed_followup_request,
)
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
    continuation_plan: Optional[ContinuationPlan] = None
    post_run_continuation_plan: Optional[ContinuationPlan] = None


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

    continuation_plan = parse_delayed_reply_request(context.user_request)
    if continuation_plan is not None:
        return MainTaskDecision(
            classification=TaskClassification(is_long_task=True, confidence="high", reasons=["delayed-reply"]),
            should_register=True,
            reason="continuation-task",
            continuation_plan=continuation_plan,
        )

    post_run_continuation_plan = parse_post_run_delayed_followup_request(context.user_request)
    if post_run_continuation_plan is not None:
        return MainTaskDecision(
            classification=TaskClassification(
                is_long_task=True,
                confidence="high",
                reasons=["post-run-delayed-followup"],
            ),
            should_register=True,
            reason="long-task",
            post_run_continuation_plan=post_run_continuation_plan,
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
        continuation_plan=None,
    )


def register_main_task(
    context: MainTaskContext,
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    observe_only: bool = False,
) -> TaskState:
    runtime_config = config or load_task_system_config()
    store = TaskStore(paths=paths or runtime_config.build_paths() or default_paths())
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
          "estimated_steps": context.estimated_steps,
          "touches_multiple_files": context.touches_multiple_files,
          "involves_delegation": context.involves_delegation,
          "requires_external_wait": context.requires_external_wait,
          "needs_verification": context.needs_verification,
          **(
              {
                  "post_run_continuation_plan": {
                      "kind": decision.post_run_continuation_plan.kind,
                      "due_at": decision.post_run_continuation_plan.due_at,
                      "wait_seconds": decision.post_run_continuation_plan.wait_seconds,
                      "reply_text": decision.post_run_continuation_plan.reply_text,
                      "lead_request": decision.post_run_continuation_plan.lead_request,
                  }
              }
              if decision.post_run_continuation_plan is not None
              else {}
          ),
        },
    )
    if decision.continuation_plan is not None:
        return store.schedule_continuation(
            task.task_id,
            continuation_kind=decision.continuation_plan.kind,
            due_at=decision.continuation_plan.due_at,
            payload={
                "reply_text": decision.continuation_plan.reply_text,
                "wait_seconds": decision.continuation_plan.wait_seconds,
                "original_user_request": context.user_request,
            },
            reason="scheduled continuation wait",
        )
    if runtime_config.agent_config(context.agent_id).auto_start and not observe_only:
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
