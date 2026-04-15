#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

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
from session_state import SessionStateStore
from same_session_routing import build_same_session_routing_decision, _is_stale_observed_takeover_candidate
from task_config import TaskSystemConfig, load_task_system_config
from task_state import ACTIVE_STATUSES, OBSERVED_STATUSES, RECOVERABLE_STATUSES, TaskPaths, TaskState, TaskStore, default_paths, now_iso

SameSessionRoutingClassifier = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class OpenClawInboundContext:
    agent_id: str
    session_key: str
    channel: str
    account_id: Optional[str]
    chat_id: str
    user_id: Optional[str]
    user_request: str
    reply_to_id: Optional[str] = None
    thread_id: Optional[str] = None
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
    routing_decision: Optional[dict[str, object]] = None
    session_state: Optional[dict[str, object]] = None

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


def _clone_task(task: TaskState) -> TaskState:
    return TaskState(**task.to_dict())


def _find_inflight_tasks(
    inflight_tasks: list[TaskState],
    *,
    agent_id: Optional[str] = None,
    session_key: Optional[str] = None,
    statuses: Optional[set[str]] = None,
) -> list[TaskState]:
    matched: list[TaskState] = []
    for task in inflight_tasks:
        if agent_id is not None and task.agent_id != agent_id:
            continue
        if session_key is not None and task.session_key != session_key:
            continue
        if statuses is not None and task.status not in statuses:
            continue
        matched.append(_clone_task(task))
    return sorted(matched, key=lambda item: item.updated_at, reverse=True)


def _find_latest_inflight_task(
    inflight_tasks: list[TaskState],
    *,
    agent_id: str,
    session_key: str,
    statuses: set[str],
) -> Optional[TaskState]:
    matches = _find_inflight_tasks(
        inflight_tasks,
        agent_id=agent_id,
        session_key=session_key,
        statuses=statuses,
    )
    return matches[0] if matches else None


def _replace_inflight_task(
    inflight_tasks: list[TaskState],
    task: TaskState,
) -> list[TaskState]:
    updated = [_clone_task(existing) for existing in inflight_tasks if existing.task_id != task.task_id]
    updated.append(_clone_task(task))
    return updated


def _queue_metrics(
    store: TaskStore,
    *,
    agent_id: str,
    task_id: Optional[str],
    inflight_tasks: Optional[list[TaskState]] = None,
) -> tuple[Optional[int], int, int, int, int]:
    queue_tasks = (
        _find_inflight_tasks(
            inflight_tasks,
            agent_id=agent_id,
            statuses={"received", "queued", "running"},
        )
        if inflight_tasks is not None
        else store.find_inflight_tasks(agent_id=agent_id, statuses={"received", "queued", "running"})
    )
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


def _queue_state(
    store: TaskStore,
    *,
    agent_id: str,
    inflight_tasks: Optional[list[TaskState]] = None,
) -> dict[str, int]:
    _, _, active_count, running_count, queued_count = _queue_metrics(
        store,
        agent_id=agent_id,
        task_id=None,
        inflight_tasks=inflight_tasks,
    )
    return {
        "active_count": active_count,
        "running_count": running_count,
        "queued_count": queued_count,
    }


def _collecting_window_payload(state: Optional[dict[str, Any]]) -> Optional[dict[str, object]]:
    if not state:
        return None
    collecting = state.get("same_session_collecting")
    if not isinstance(collecting, dict):
        return None
    return {
        "session_key": str(state.get("session_key") or "").strip() or None,
        "status": str(collecting.get("status") or "").strip() or None,
        "expires_at": str(collecting.get("expires_at") or "").strip() or None,
        "window_seconds": int(collecting.get("window_seconds") or 0),
        "buffered_message_count": int(collecting.get("buffered_message_count") or 0),
        "existing_task_id": str(collecting.get("existing_task_id") or "").strip() or None,
        "materialized_task_id": str(collecting.get("materialized_task_id") or "").strip() or None,
    }


def _reuse_stale_observed_task(
    store: TaskStore,
    *,
    task: TaskState,
    ctx: OpenClawInboundContext,
    runtime_config: TaskSystemConfig,
    observe_only: bool,
) -> TaskState:
    ts = now_iso()
    original_request = str(task.meta.get("original_user_request") or "").strip()
    task.channel = ctx.channel
    task.account_id = ctx.account_id
    task.chat_id = ctx.chat_id
    task.user_id = ctx.user_id
    task.task_label = ctx.user_request[:80]
    task.monitor_state = "normal"
    task.created_at = ts
    task.updated_at = ts
    task.last_internal_touch_at = ts
    task.last_user_visible_update_at = ts
    task.meta["source"] = "main-task-adapter"
    task.meta["original_user_request"] = ctx.user_request
    task.meta["source_reply_to_id"] = ctx.reply_to_id
    task.meta["source_thread_id"] = ctx.thread_id
    task.meta["estimated_steps"] = ctx.estimated_steps
    task.meta["touches_multiple_files"] = ctx.touches_multiple_files
    task.meta["involves_delegation"] = ctx.involves_delegation
    task.meta["requires_external_wait"] = ctx.requires_external_wait
    task.meta["needs_verification"] = ctx.needs_verification
    task.meta["same_session_takeover"] = {
        "kind": "stale-observed-task",
        "reused_at": ts,
        "previous_request": original_request or None,
    }
    store.save_task(task)
    if runtime_config.agent_config(ctx.agent_id).auto_start and not observe_only:
        return store.claim_execution_slot(task.task_id)
    return task


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
    if task_status in {"received", "queued"} and slots_ahead > 0 and estimate < 60:
        return None
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
        reply_to_id=ctx.reply_to_id,
        thread_id=ctx.thread_id,
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
    same_session_classifier: Optional[SameSessionRoutingClassifier] = None,
    same_session_classifier_min_confidence: float = 0.7,
) -> BridgeDecision:
    runtime_config = config or load_task_system_config(config_path=config_path)
    resolved_paths = paths or runtime_config.build_paths() or default_paths()
    store = TaskStore(paths=resolved_paths)
    session_store = SessionStateStore(paths=resolved_paths)
    inflight_tasks = store.list_inflight_tasks()
    has_running_task = any(task.agent_id == ctx.agent_id and task.status == "running" for task in inflight_tasks)
    active_task = _find_latest_inflight_task(
        inflight_tasks,
        agent_id=ctx.agent_id,
        session_key=ctx.session_key,
        statuses=ACTIVE_STATUSES,
    )
    observed_task = _find_latest_inflight_task(
        inflight_tasks,
        agent_id=ctx.agent_id,
        session_key=ctx.session_key,
        statuses=OBSERVED_STATUSES,
    )
    recoverable = _find_latest_inflight_task(
        inflight_tasks,
        agent_id=ctx.agent_id,
        session_key=ctx.session_key,
        statuses=RECOVERABLE_STATUSES,
    )
    main_ctx = build_main_task_context(ctx)
    decision = decide_main_task(main_ctx, config=runtime_config)
    routing_queue_state = _queue_state(store, agent_id=ctx.agent_id, inflight_tasks=inflight_tasks)
    session_state = session_store.load_collecting_state(agent_id=ctx.agent_id, session_key=ctx.session_key)
    collecting_state = False
    if isinstance(session_state, dict):
        collecting = session_state.get("same_session_collecting")
        collecting_state = isinstance(collecting, dict) and str(collecting.get("status") or "").strip() == "collecting"
    stale_observed_takeover = (
        observed_task
        if active_task is None and recoverable is None and _is_stale_observed_takeover_candidate(observed_task)
        else None
    )
    prestart_task = active_task if active_task is not None and active_task.status == "queued" else observed_task

    def _build_collecting_short_circuit(
        *,
        classification_reason: str,
        session_state_payload: Optional[dict[str, Any]],
        target_task: Optional[TaskState],
    ) -> BridgeDecision:
        routing_decision = build_same_session_routing_decision(
            session_key=ctx.session_key,
            user_request=ctx.user_request,
            should_register_task=False,
            classification_reason=classification_reason,
            active_task=active_task,
            recoverable_task=recoverable,
            observed_task=observed_task,
            target_task=target_task,
            classifier=same_session_classifier,
            classifier_min_confidence=same_session_classifier_min_confidence,
            queue_state=routing_queue_state,
            collecting_state=True,
        )
        collecting_payload = _collecting_window_payload(session_state_payload)
        if collecting_payload is not None:
            routing_decision["collecting_window"] = collecting_payload
        return BridgeDecision(
            should_register_task=False,
            task_id=target_task.task_id if target_task is not None else None,
            classification_reason=classification_reason,
            confidence="high",
            task_status=target_task.status if target_task is not None else None,
            queue_position=None,
            ahead_count=0,
            active_count=routing_queue_state["active_count"],
            running_count=routing_queue_state["running_count"],
            queued_count=routing_queue_state["queued_count"],
            continuation_due_at=None,
            routing_decision=routing_decision,
            session_state=collecting_payload,
        )

    collecting_window_seconds = runtime_config.agent_config(ctx.agent_id).same_session_routing.collecting_window_seconds
    explicit_collect_more_probe = build_same_session_routing_decision(
        session_key=ctx.session_key,
        user_request=ctx.user_request,
        should_register_task=True,
        classification_reason=decision.reason,
        active_task=active_task,
        recoverable_task=recoverable,
        observed_task=observed_task,
        target_task=prestart_task,
        queue_state=routing_queue_state,
        collecting_state=False,
    )
    if explicit_collect_more_probe.get("classification") == "collect-more":
        activated_state = session_store.activate_collecting_window(
            agent_id=ctx.agent_id,
            session_key=ctx.session_key,
            channel=ctx.channel,
            account_id=ctx.account_id,
            chat_id=ctx.chat_id,
            user_id=ctx.user_id,
            window_seconds=collecting_window_seconds,
            activation_message=ctx.user_request,
            existing_task_id=(prestart_task.task_id if prestart_task is not None and prestart_task.status in {"received", "queued"} else None),
        )
        return _build_collecting_short_circuit(
            classification_reason="collecting-window-activated",
            session_state_payload=activated_state,
            target_task=prestart_task,
        )
    if collecting_state and decision.reason != "control-command":
        buffered_state = session_store.append_collecting_message(
            agent_id=ctx.agent_id,
            session_key=ctx.session_key,
            message=ctx.user_request,
            refresh_window_seconds=collecting_window_seconds,
        ) or session_state
        return _build_collecting_short_circuit(
            classification_reason="collecting-window-buffered",
            session_state_payload=buffered_state,
            target_task=prestart_task,
        )
    if not decision.should_register:
        routing_decision = build_same_session_routing_decision(
            session_key=ctx.session_key,
            user_request=ctx.user_request,
            should_register_task=False,
            classification_reason=decision.reason,
            active_task=active_task,
            recoverable_task=recoverable,
            observed_task=observed_task,
            target_task=None,
            classifier=same_session_classifier,
            classifier_min_confidence=same_session_classifier_min_confidence,
            queue_state=routing_queue_state,
            collecting_state=collecting_state,
        )
        return BridgeDecision(
            should_register_task=False,
            task_id=None,
            classification_reason=decision.reason,
            confidence=decision.classification.confidence,
            routing_decision=routing_decision,
            session_state=_collecting_window_payload(session_state),
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
                recoverable = None
    if recoverable is not None:
        resumed = resume_main_task(
            recoverable.task_id,
            progress_note=f"恢复执行：{ctx.user_request[:120]}",
            paths=store.paths,
            store=store,
            has_running_task=has_running_task,
        )
        updated_inflight_tasks = _replace_inflight_task(inflight_tasks, resumed)
        routing_decision = build_same_session_routing_decision(
            session_key=ctx.session_key,
            user_request=ctx.user_request,
            should_register_task=True,
            classification_reason="resume-blocked-task",
            active_task=active_task,
            recoverable_task=recoverable,
            observed_task=observed_task,
            target_task=resumed,
            classifier=same_session_classifier,
            classifier_min_confidence=same_session_classifier_min_confidence,
            queue_state=routing_queue_state,
            collecting_state=collecting_state,
        )
        resumed.meta["same_session_routing"] = routing_decision
        store.save_task(resumed)
        _, _, active_count, running_count, queued_count = _queue_metrics(
            store,
            agent_id=ctx.agent_id,
            task_id=resumed.task_id,
            inflight_tasks=updated_inflight_tasks,
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
            routing_decision=routing_decision,
            session_state=_collecting_window_payload(session_state),
        )

    observed_task_for_routing = observed_task
    if stale_observed_takeover is not None:
        observed_task_for_routing = TaskState(**stale_observed_takeover.to_dict())
        task = _reuse_stale_observed_task(
            store,
            task=stale_observed_takeover,
            ctx=ctx,
            runtime_config=runtime_config,
            observe_only=observe_only,
        )
    else:
        task = register_main_task(
            main_ctx,
            paths=resolved_paths,
            config=runtime_config,
            observe_only=observe_only,
            store=store,
            has_running_task=has_running_task,
        )
    routing_decision = build_same_session_routing_decision(
        session_key=ctx.session_key,
        user_request=ctx.user_request,
        should_register_task=True,
        classification_reason=decision.reason,
        active_task=active_task,
        recoverable_task=recoverable,
        observed_task=observed_task_for_routing,
        target_task=task,
        classifier=same_session_classifier,
        classifier_min_confidence=same_session_classifier_min_confidence,
        queue_state=routing_queue_state,
        collecting_state=collecting_state,
    )
    task.meta["same_session_routing"] = routing_decision
    store.save_task(task)
    updated_inflight_tasks = _replace_inflight_task(inflight_tasks, task)
    queue_position, ahead_count, active_count, running_count, queued_count = _queue_metrics(
        store,
        agent_id=ctx.agent_id,
        task_id=task.task_id,
        inflight_tasks=updated_inflight_tasks,
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
        routing_decision=routing_decision,
        session_state=_collecting_window_payload(session_state),
    )


def materialize_due_collecting_windows(
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> list[dict[str, object]]:
    runtime_config = config or load_task_system_config(config_path=config_path)
    resolved_paths = paths or runtime_config.build_paths() or default_paths()
    store = TaskStore(paths=resolved_paths)
    session_store = SessionStateStore(paths=resolved_paths)
    materialized: list[dict[str, object]] = []
    for state in session_store.claim_due_collecting_windows():
        collecting = state.get("same_session_collecting") if isinstance(state.get("same_session_collecting"), dict) else {}
        buffered_messages = collecting.get("buffered_user_messages") if isinstance(collecting.get("buffered_user_messages"), list) else []
        existing_task_id = str(collecting.get("existing_task_id") or "").strip() or None
        session_key = str(state.get("session_key") or "").strip()
        agent_id = str(state.get("agent_id") or "").strip()
        channel = str(state.get("channel") or "").strip()
        account_id = str(state.get("account_id") or "").strip() or None
        chat_id = str(state.get("chat_id") or "").strip()
        user_id = str(state.get("user_id") or "").strip() or None
        reason = "collecting-window-materialized-new-task"
        task: Optional[TaskState] = None
        combined_parts = [str(item).strip() for item in buffered_messages if str(item).strip()]
        if existing_task_id:
            try:
                existing_task = store.load_task(existing_task_id, allow_archive=False)
            except FileNotFoundError:
                existing_task = None
            if existing_task is not None and existing_task.status in {"received", "queued"}:
                original_request = str(existing_task.meta.get("original_user_request") or "").strip()
                combined_request = "\n".join([item for item in [original_request, *combined_parts] if item]).strip()
                if combined_request:
                    existing_task.task_label = combined_request[:80]
                    existing_task.meta["original_user_request"] = combined_request
                existing_task.meta["same_session_collecting"] = _collecting_window_payload(state)
                task = store.claim_execution_slot(existing_task.task_id)
                reason = "collecting-window-merged-into-existing-task"
        if task is None:
            combined_request = "\n".join(combined_parts).strip()
            if not combined_request:
                session_store.complete_collecting_window(
                    session_key=session_key,
                    materialized_task_id=None,
                    materialization_reason="collecting-window-expired-empty",
                )
                continue
            ctx = OpenClawInboundContext(
                agent_id=agent_id,
                session_key=session_key,
                channel=channel,
                account_id=account_id,
                chat_id=chat_id,
                user_id=user_id,
                user_request=combined_request,
            )
            main_ctx = build_main_task_context(ctx)
            main_decision = decide_main_task(main_ctx, config=runtime_config)
            task = register_main_task(
                main_ctx,
                paths=resolved_paths,
                config=runtime_config,
                observe_only=main_decision.reason == "observed-task",
            )
            task.meta["same_session_collecting"] = _collecting_window_payload(state)
            store.save_task(task)
        session_store.complete_collecting_window(
            session_key=session_key,
            materialized_task_id=task.task_id if task is not None else None,
            materialization_reason=reason,
        )
        combined_request = str(task.meta.get("original_user_request") or "").strip()
        materialized.append(
            {
                "session_key": session_key,
                "agent_id": agent_id,
                "channel": channel,
                "account_id": account_id,
                "chat_id": chat_id,
                "user_id": user_id,
                "task_id": task.task_id,
                "task_status": task.status,
                "materialization_reason": reason,
                "combined_user_request": combined_request,
                "buffered_message_count": len(combined_parts),
            }
        )
    return materialized


def record_progress(
    task_id: str,
    *,
    progress_note: Optional[str] = None,
    status: Optional[str] = None,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
    store: Optional[TaskStore] = None,
) -> TaskState:
    runtime_config = config or load_task_system_config(config_path=config_path)
    store = store or TaskStore(paths=paths or runtime_config.build_paths() or default_paths())
    return sync_main_progress(
        task_id,
        progress_note=progress_note,
        status=status,
        paths=store.paths,
        store=store,
    )


def record_blocked(
    task_id: str,
    reason: str,
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
    store: Optional[TaskStore] = None,
) -> TaskState:
    runtime_config = config or load_task_system_config(config_path=config_path)
    store = store or TaskStore(paths=paths or runtime_config.build_paths() or default_paths())
    return block_main_task(task_id, reason, paths=store.paths, store=store)


def record_completed(
    task_id: str,
    result_summary: Optional[str] = None,
    *,
    meta: Optional[dict[str, Any]] = None,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
    store: Optional[TaskStore] = None,
) -> TaskState:
    runtime_config = config or load_task_system_config(config_path=config_path)
    store = store or TaskStore(paths=paths or runtime_config.build_paths() or default_paths())
    return finish_main_task(
        task_id,
        result_summary=result_summary,
        meta=meta,
        paths=store.paths,
        store=store,
    )


def record_failed(
    task_id: str,
    reason: str,
    *,
    meta: Optional[dict[str, Any]] = None,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
    store: Optional[TaskStore] = None,
) -> TaskState:
    runtime_config = config or load_task_system_config(config_path=config_path)
    store = store or TaskStore(paths=paths or runtime_config.build_paths() or default_paths())
    return fail_main_task(task_id, reason, meta=meta, paths=store.paths, store=store)
