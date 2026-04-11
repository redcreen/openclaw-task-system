#!/usr/bin/env python3
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from task_state import TaskState

SAME_SESSION_ROUTING_SCHEMA = "openclaw.task-system.same-session-routing.v1"
SAME_SESSION_ROUTING_VERSION = 1
SAME_SESSION_ROUTING_PHASE = "phase-5-runtime-owned-classifier"
SAME_SESSION_ROUTING_CLASSIFIER_SCHEMA = "openclaw.task-system.same-session-routing-classifier.v1"

ROUTING_STATUS_DECIDED = "decided"
ROUTING_STATUS_RECORDED_ONLY = "recorded-only"

CLASSIFICATION_CONTROL_PLANE = "control-plane"
CLASSIFICATION_STEERING = "steering"
CLASSIFICATION_QUEUEING = "queueing"
CLASSIFICATION_COLLECT_MORE = "collect-more"

DECISION_HANDLE_AS_CONTROL_PLANE = "handle-as-control-plane"
DECISION_MERGE_BEFORE_START = "merge-before-start"
DECISION_INTERRUPT_AND_RESTART = "interrupt-and-restart"
DECISION_APPEND_AS_NEXT_STEP = "append-as-next-step"
DECISION_QUEUE_AS_NEW_TASK = "queue-as-new-task"
DECISION_ENTER_COLLECTING_WINDOW = "enter-collecting-window"

RUNTIME_ACTION_SKIP_REGISTER = "skip-register"
RUNTIME_ACTION_REGISTER_NEW_TASK = "register-new-task"
RUNTIME_ACTION_RESUME_EXISTING_TASK = "resume-existing-task"
RUNTIME_ACTION_REUSE_EXISTING_TASK = "reuse-existing-task"

_ASCII_WORD_RE = re.compile(r"[a-z0-9]{3,}")
_CJK_WORD_RE = re.compile(r"[\u4e00-\u9fff]{2,8}")

_PLAIN_CONTROL_COMMANDS = {
    "continue",
    "resume",
    "status",
    "pause",
    "cancel",
    "stop",
    "继续",
    "继续处理",
    "恢复",
    "状态",
    "进度",
    "暂停",
    "取消",
    "停止",
}

_COLLECT_MORE_SIGNALS = (
    "don't start yet",
    "do not start yet",
    "wait for more",
    "i'm not done yet",
    "i am not done yet",
    "i will send more",
    "先别开始",
    "不要开始",
    "先不要开始",
    "我还没发完",
    "还没发完",
    "等我发完",
    "等我再发",
    "我还要继续发",
)

_INDEPENDENT_REQUEST_PREFIXES = (
    "also ",
    "also,",
    "also please",
    "另请",
    "另外",
    "另外再",
    "顺便",
    "再帮我",
)

_REFINEMENT_SIGNALS = (
    "make it",
    "more ",
    "too",
    "instead",
    "rewrite it",
    "this one",
    "当前任务",
    "这个任务",
    "这个也",
    "改成",
    "改一下",
    "调整",
    "补充",
    "增加",
    "更",
)

_TASK_VERBS = (
    "check",
    "review",
    "analyze",
    "summarize",
    "rewrite",
    "fix",
    "investigate",
    "test",
    "查",
    "看",
    "分析",
    "总结",
    "重写",
    "修复",
    "排查",
    "测试",
    "整理",
)

DEFAULT_CLASSIFIER_MIN_CONFIDENCE = 0.7

SameSessionRoutingClassifier = Callable[[dict[str, Any]], dict[str, Any]]


def _task_stage(task: Optional[TaskState]) -> Optional[str]:
    if task is None:
        return None
    if task.status == "received":
        return "received"
    if task.status == "queued":
        return "queued"
    if task.status == "running":
        return "running"
    if task.status in {"blocked", "paused"}:
        if str(task.meta.get("continuation_kind") or "").strip():
            return "paused-continuation"
        return "paused"
    return task.status


def _running_stage(task: TaskState) -> str:
    meta = task.meta if isinstance(task.meta, dict) else {}
    explicit = str(meta.get("execution_stage") or meta.get("active_task_stage") or "").strip()
    if explicit in {"running-no-side-effects", "running-with-side-effects"}:
        return explicit
    if bool(meta.get("side_effects_started")) or bool(meta.get("external_actions_started")):
        return "running-with-side-effects"
    return "running-no-side-effects"


def _task_ref(task: Optional[TaskState]) -> dict[str, Optional[str]]:
    if task is None:
        return {
            "task_id": None,
            "task_status": None,
            "task_stage": None,
        }
    return {
        "task_id": task.task_id,
        "task_status": task.status,
        "task_stage": _running_stage(task) if task.status == "running" else _task_stage(task),
    }


def _normalized(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _keyword_set(text: str) -> set[str]:
    normalized = _normalized(text)
    return {
        *{item for item in _ASCII_WORD_RE.findall(normalized)},
        *{item for item in _CJK_WORD_RE.findall(normalized)},
    }


def _active_task_summary(task: Optional[TaskState]) -> str:
    if task is None:
        return ""
    original = str(task.meta.get("original_user_request") or "").strip()
    if original:
        return original
    return str(task.task_label or "").strip()


def _looks_like_placeholder_observed_request(text: str) -> bool:
    normalized = str(text or "").strip()
    compact = normalized.replace(" ", "")
    if not compact:
        return False
    if len(compact) > 8:
        return False
    if any(ch.isdigit() for ch in compact):
        return False
    if _is_plain_control_command(normalized):
        return False
    if _is_collect_more_request(normalized):
        return False
    if _looks_like_task_request(normalized):
        return False
    if _looks_like_refinement(normalized):
        return False
    return True


def _is_stale_observed_takeover_candidate(task: Optional[TaskState]) -> bool:
    if task is None or task.status != "received":
        return False
    monitor_state = str(getattr(task, "monitor_state", "") or "").strip().lower()
    meta = task.meta if isinstance(task.meta, dict) else {}
    if monitor_state == "manual-review":
        return True
    if bool(str(meta.get("manual_review_reason") or "").strip()):
        return True
    return _looks_like_placeholder_observed_request(_active_task_summary(task))


def _is_plain_control_command(text: str) -> bool:
    normalized = _normalized(text)
    return normalized.startswith("/") or normalized in _PLAIN_CONTROL_COMMANDS


def _is_collect_more_request(text: str) -> bool:
    normalized = _normalized(text)
    return any(signal in normalized for signal in _COLLECT_MORE_SIGNALS)


def _looks_like_refinement(text: str) -> bool:
    normalized = _normalized(text)
    return any(signal in normalized for signal in _REFINEMENT_SIGNALS)


def _looks_like_task_request(text: str) -> bool:
    normalized = _normalized(text)
    return any(signal in normalized for signal in _TASK_VERBS)


def _has_independent_request_prefix(text: str) -> bool:
    normalized = _normalized(text)
    return any(normalized.startswith(prefix) for prefix in _INDEPENDENT_REQUEST_PREFIXES)


def _looks_like_obvious_independent_new_request(text: str, active_task: Optional[TaskState]) -> bool:
    if active_task is None:
        return False
    if not _has_independent_request_prefix(text):
        return False
    if _looks_like_refinement(text):
        return False
    if not _looks_like_task_request(text):
        return False
    active_keywords = _keyword_set(_active_task_summary(active_task))
    request_keywords = _keyword_set(text)
    if not request_keywords:
        return False
    return active_keywords.isdisjoint(request_keywords)


def _execution_decision_for_steering(task: Optional[TaskState]) -> tuple[Optional[str], str, str]:
    if task is None:
        return None, "missing-active-task-stage", "No active task stage is available for steering execution gating."
    stage = _task_ref(task)["task_stage"]
    if stage in {"received", "queued"}:
        return (
            DECISION_MERGE_BEFORE_START,
            "active-task-not-started",
            "The active task has not formally started yet, so the follow-up can be merged before execution.",
        )
    if stage == "running-no-side-effects":
        return (
            DECISION_INTERRUPT_AND_RESTART,
            "active-task-safe-restart",
            "The active task is running without recorded side effects, so a safe restart is allowed.",
        )
    if stage == "running-with-side-effects":
        return (
            DECISION_APPEND_AS_NEXT_STEP,
            "active-task-has-side-effects",
            "The active task already has side effects, so the follow-up is appended as the next step instead of restarting.",
        )
    if stage in {"paused", "paused-continuation", "blocked"}:
        return (
            DECISION_APPEND_AS_NEXT_STEP,
            "active-task-paused-non-destructive",
            "The active task is paused or continuation-bound, so the follow-up is kept non-destructive and appended as the next step.",
        )
    return (
        None,
        "unknown-active-task-stage",
        "The active task stage is not explicit enough to choose a steering execution action safely.",
    )


def _build_classifier_input(
    *,
    session_key: str,
    user_request: str,
    active_task: Optional[TaskState],
    queue_state: Optional[dict[str, int]],
    collecting_state: bool,
    recent_user_messages: Optional[list[str]],
) -> dict[str, Any]:
    existing_ref = _task_ref(active_task)
    messages = [item for item in (recent_user_messages or []) if str(item or "").strip()]
    if not messages:
        active_summary = _active_task_summary(active_task)
        if active_summary:
            messages.append(active_summary[:160])
        if str(user_request or "").strip():
            messages.append(str(user_request or "").strip()[:160])
    return {
        "schema": SAME_SESSION_ROUTING_CLASSIFIER_SCHEMA,
        "session_key": str(session_key or "").strip() or None,
        "active_task_summary": _active_task_summary(active_task)[:160] or None,
        "active_task_stage": existing_ref["task_stage"],
        "recent_user_messages": messages,
        "new_message": str(user_request or "").strip()[:160] or None,
        "collecting_state": bool(collecting_state),
        "queue_state": {
            "running_count": int((queue_state or {}).get("running_count") or 0),
            "queued_count": int((queue_state or {}).get("queued_count") or 0),
            "active_count": int((queue_state or {}).get("active_count") or 0),
        },
    }


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_classifier_output(payload: dict[str, Any]) -> dict[str, Any]:
    classification = str(payload.get("classification") or "").strip()
    confidence = _safe_float(payload.get("confidence"))
    return {
        "classification": classification or None,
        "confidence": confidence,
        "needs_confirmation": bool(payload.get("needs_confirmation")),
        "reason_code": str(payload.get("reason_code") or "").strip() or None,
        "reason_text": str(payload.get("reason_text") or "").strip() or None,
    }


def _fallback_for_ambiguous_followup(task: Optional[TaskState]) -> tuple[str, str, str, str]:
    stage = _task_ref(task)["task_stage"]
    if stage in {"received", "queued"}:
        return (
            CLASSIFICATION_STEERING,
            DECISION_MERGE_BEFORE_START,
            "classifier-fallback-task-not-started",
            "The classifier was unavailable or uncertain, and the active task has not started yet, so runtime used the non-destructive pre-start merge fallback.",
        )
    return (
        CLASSIFICATION_QUEUEING,
        DECISION_QUEUE_AS_NEW_TASK,
        "classifier-fallback-safe-queue",
        "The classifier was unavailable or uncertain, so runtime used the safer queue-as-new-task fallback for this ambiguous follow-up.",
    )


def build_same_session_routing_decision(
    *,
    session_key: str,
    user_request: str,
    should_register_task: bool,
    classification_reason: str,
    active_task: Optional[TaskState],
    recoverable_task: Optional[TaskState],
    observed_task: Optional[TaskState] = None,
    target_task: Optional[TaskState] = None,
    classifier: Optional[SameSessionRoutingClassifier] = None,
    classifier_min_confidence: float = DEFAULT_CLASSIFIER_MIN_CONFIDENCE,
    queue_state: Optional[dict[str, int]] = None,
    collecting_state: bool = False,
    recent_user_messages: Optional[list[str]] = None,
) -> dict[str, Any]:
    existing_task = active_task or recoverable_task
    stale_observed_takeover = (
        existing_task is None
        and should_register_task
        and classification_reason != "control-command"
        and _is_stale_observed_takeover_candidate(observed_task)
    )
    existing_task_for_trace = existing_task or (observed_task if stale_observed_takeover else None)
    same_session_followup = existing_task_for_trace is not None
    routing_status = ROUTING_STATUS_RECORDED_ONLY
    classification: Optional[str] = None
    execution_decision: Optional[str] = None
    reason_code = "phase2-routing-recorded"
    reason_text = (
        "The routing context is recorded in truth source, but this case still waits for a later deterministic or classifier-backed decision."
    )
    runtime_action = (
        RUNTIME_ACTION_REGISTER_NEW_TASK if should_register_task else RUNTIME_ACTION_SKIP_REGISTER
    )
    active_summary = _active_task_summary(existing_task_for_trace)
    classifier_invoked = False
    classifier_input: Optional[dict[str, Any]] = None
    classifier_result: Optional[dict[str, Any]] = None
    classifier_error: Optional[str] = None
    classifier_low_confidence = False
    decision_source = "rule" if routing_status == ROUTING_STATUS_DECIDED else "recorded-only"

    if not should_register_task and classification_reason == "control-command":
        routing_status = ROUTING_STATUS_DECIDED
        classification = CLASSIFICATION_CONTROL_PLANE
        execution_decision = DECISION_HANDLE_AS_CONTROL_PLANE
        reason_code = "control-plane-command"
        reason_text = "The message is a control-plane command, so runtime handles it outside the normal task path."
    elif same_session_followup and _is_plain_control_command(user_request):
        routing_status = ROUTING_STATUS_DECIDED
        classification = CLASSIFICATION_CONTROL_PLANE
        execution_decision = DECISION_HANDLE_AS_CONTROL_PLANE
        reason_code = "same-session-control-plane-rule"
        reason_text = "A deterministic same-session control-plane rule matched this short management instruction."
    elif collecting_state and classification_reason != "control-command":
        routing_status = ROUTING_STATUS_DECIDED
        classification = CLASSIFICATION_COLLECT_MORE
        execution_decision = DECISION_ENTER_COLLECTING_WINDOW
        reason_code = "collecting-window-active"
        reason_text = "A same-session collecting window is already active, so runtime keeps buffering follow-up input before execution starts."
    elif _is_collect_more_request(user_request):
        routing_status = ROUTING_STATUS_DECIDED
        classification = CLASSIFICATION_COLLECT_MORE
        execution_decision = DECISION_ENTER_COLLECTING_WINDOW
        reason_code = "collect-more-rule"
        reason_text = "A deterministic collect-more rule matched the user's explicit request to wait for more input."
    elif stale_observed_takeover:
        routing_status = ROUTING_STATUS_DECIDED
        classification = CLASSIFICATION_STEERING
        execution_decision = DECISION_MERGE_BEFORE_START
        reason_code = "stale-observed-task-takeover"
        reason_text = (
            "A stale same-session observed task was reused as the pre-start target, so runtime merged this new request into that task instead of creating another queued entry."
        )
        runtime_action = RUNTIME_ACTION_REUSE_EXISTING_TASK
        decision_source = "rule"
    elif not same_session_followup:
        routing_status = ROUTING_STATUS_DECIDED
        classification = CLASSIFICATION_QUEUEING
        execution_decision = DECISION_QUEUE_AS_NEW_TASK
        reason_code = "no-active-task-default-new-request"
        reason_text = "No active task exists in this session, so runtime keeps the request on the normal new-task path."
    elif _looks_like_obvious_independent_new_request(user_request, existing_task):
        routing_status = ROUTING_STATUS_DECIDED
        classification = CLASSIFICATION_QUEUEING
        execution_decision = DECISION_QUEUE_AS_NEW_TASK
        reason_code = "same-session-obvious-independent-request"
        reason_text = "A deterministic rule matched an obvious independent follow-up request, so runtime keeps it as a separate queued task."
    elif classification_reason == "resume-blocked-task":
        reason_code = "phase2-resume-existing-task-recorded"
        reason_text = (
            "Runtime resumed the latest recoverable task in this session and recorded the same-session routing context."
        )
        runtime_action = RUNTIME_ACTION_RESUME_EXISTING_TASK
    else:
        if active_summary and _looks_like_refinement(user_request):
            classification = CLASSIFICATION_STEERING
            execution_decision, reason_code, reason_text = _execution_decision_for_steering(existing_task_for_trace)
            if execution_decision is not None:
                routing_status = ROUTING_STATUS_DECIDED
                decision_source = "rule"
        else:
            reason_code = "phase3-same-session-followup-recorded"
            reason_text = (
                "An active same-session task already exists, but deterministic rules still do not separate steering from queueing for this case."
            )

    classifier_should_run = (
        same_session_followup
        and classification is None
        and routing_status != ROUTING_STATUS_DECIDED
        and classification_reason != "resume-blocked-task"
    )
    if classifier_should_run:
        classifier_input = _build_classifier_input(
            session_key=session_key,
            user_request=user_request,
            active_task=existing_task_for_trace,
            queue_state=queue_state,
            collecting_state=collecting_state,
            recent_user_messages=recent_user_messages,
        )
        if classifier is not None:
            classifier_invoked = True
            try:
                classifier_result = _normalize_classifier_output(classifier(dict(classifier_input)))
            except Exception as exc:
                classifier_error = str(exc).strip() or exc.__class__.__name__
        candidate_classification = str((classifier_result or {}).get("classification") or "").strip()
        candidate_confidence = _safe_float((classifier_result or {}).get("confidence"))
        if (
            classifier_result is not None
            and candidate_classification in {CLASSIFICATION_STEERING, CLASSIFICATION_QUEUEING}
            and candidate_confidence is not None
            and candidate_confidence >= float(classifier_min_confidence)
            and not bool(classifier_result.get("needs_confirmation"))
        ):
            classification = candidate_classification
            if classification == CLASSIFICATION_STEERING:
                execution_decision, reason_code, reason_text = _execution_decision_for_steering(existing_task_for_trace)
                if execution_decision is None:
                    (
                        classification,
                        execution_decision,
                        reason_code,
                        reason_text,
                    ) = _fallback_for_ambiguous_followup(existing_task_for_trace)
                    decision_source = "classifier-fallback"
                else:
                    reason_code = str(classifier_result.get("reason_code") or reason_code).strip() or reason_code
                    reason_text = str(classifier_result.get("reason_text") or reason_text).strip() or reason_text
                    decision_source = "classifier"
            else:
                execution_decision = DECISION_QUEUE_AS_NEW_TASK
                reason_code = (
                    str(classifier_result.get("reason_code") or "").strip()
                    or "classifier-independent-new-request"
                )
                reason_text = (
                    str(classifier_result.get("reason_text") or "").strip()
                    or "The classifier judged this follow-up to be a separate same-session task."
                )
                decision_source = "classifier"
            routing_status = ROUTING_STATUS_DECIDED
        else:
            if classifier_invoked and classifier_result is not None:
                classifier_low_confidence = True
            classification, execution_decision, reason_code, reason_text = _fallback_for_ambiguous_followup(
                existing_task_for_trace
            )
            routing_status = ROUTING_STATUS_DECIDED
            decision_source = "classifier-fallback"

    target_ref = _task_ref(target_task)
    existing_ref = _task_ref(existing_task_for_trace)
    return {
        "schema": SAME_SESSION_ROUTING_SCHEMA,
        "version": SAME_SESSION_ROUTING_VERSION,
        "phase": SAME_SESSION_ROUTING_PHASE,
        "routing_status": routing_status,
        "same_session_followup": same_session_followup,
        "classifier_invoked": classifier_invoked,
        "classifier_input": classifier_input,
        "classifier_result": classifier_result,
        "classifier_error": classifier_error,
        "classifier_low_confidence": classifier_low_confidence,
        "classifier_min_confidence": float(classifier_min_confidence),
        "provisional": routing_status != ROUTING_STATUS_DECIDED,
        "rule_matched": decision_source == "rule",
        "decision_source": decision_source,
        "classification": classification,
        "execution_decision": execution_decision,
        "runtime_action": runtime_action,
        "classification_reason": classification_reason,
        "reason_code": reason_code,
        "reason_text": reason_text,
        "active_task_summary": active_summary[:160] or None,
        "session_key": str(session_key or "").strip() or None,
        "user_request_excerpt": str(user_request or "").strip()[:160] or None,
        "active_task_id": existing_ref["task_id"],
        "active_task_status": existing_ref["task_status"],
        "active_task_stage": existing_ref["task_stage"],
        "target_task_id": target_ref["task_id"],
        "target_task_status": target_ref["task_status"],
        "target_task_stage": target_ref["task_stage"],
        "target_session_key": str(session_key or "").strip() or None,
        "wd_receipt": None,
    }
