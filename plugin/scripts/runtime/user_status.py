#!/usr/bin/env python3
from __future__ import annotations

from typing import Any, Mapping


USER_STATUS_RECEIVED = "received"
USER_STATUS_PENDING_START = "pending-start"
USER_STATUS_QUEUED = "queued"
USER_STATUS_RUNNING = "running"
USER_STATUS_PAUSED = "paused"
USER_STATUS_BLOCKED = "blocked"
USER_STATUS_DONE = "done"
USER_STATUS_FAILED = "failed"
USER_STATUS_CANCELLED = "cancelled"
USER_STATUS_UNKNOWN = "unknown"

USER_STATUS_LABELS = {
    USER_STATUS_RECEIVED: "已收到",
    USER_STATUS_PENDING_START: "待开始",
    USER_STATUS_QUEUED: "排队中",
    USER_STATUS_RUNNING: "处理中",
    USER_STATUS_PAUSED: "已暂停",
    USER_STATUS_BLOCKED: "已阻塞",
    USER_STATUS_DONE: "已完成",
    USER_STATUS_FAILED: "已失败",
    USER_STATUS_CANCELLED: "已取消",
    USER_STATUS_UNKNOWN: "未知状态",
}

USER_STATUS_FAMILIES = {
    USER_STATUS_RECEIVED: "pending",
    USER_STATUS_PENDING_START: "pending",
    USER_STATUS_QUEUED: "pending",
    USER_STATUS_RUNNING: "active",
    USER_STATUS_PAUSED: "active",
    USER_STATUS_BLOCKED: "active",
    USER_STATUS_DONE: "terminal",
    USER_STATUS_FAILED: "terminal",
    USER_STATUS_CANCELLED: "terminal",
    USER_STATUS_UNKNOWN: "unknown",
}


def _queue_position(task: Mapping[str, Any]) -> int | None:
    queue = task.get("queue")
    if not isinstance(queue, Mapping):
        return None
    position = queue.get("position")
    return position if isinstance(position, int) else None


def resolve_user_facing_status_code(task: Mapping[str, Any]) -> str:
    raw_status = str(task.get("status") or "").strip()
    position = _queue_position(task)

    if raw_status == "received":
        return USER_STATUS_RECEIVED
    if raw_status == "queued":
        if isinstance(position, int) and position <= 1:
            return USER_STATUS_PENDING_START
        return USER_STATUS_QUEUED
    if raw_status == "running":
        return USER_STATUS_RUNNING
    if raw_status == "paused":
        return USER_STATUS_PAUSED
    if raw_status == "blocked":
        return USER_STATUS_BLOCKED
    if raw_status == "done":
        return USER_STATUS_DONE
    if raw_status == "failed":
        return USER_STATUS_FAILED
    if raw_status == "cancelled":
        return USER_STATUS_CANCELLED
    return USER_STATUS_UNKNOWN


def label_for_user_status_code(code: str) -> str:
    normalized = str(code or "").strip() or USER_STATUS_UNKNOWN
    return USER_STATUS_LABELS.get(normalized, USER_STATUS_LABELS[USER_STATUS_UNKNOWN])


def project_user_facing_status(task: Mapping[str, Any]) -> dict[str, str]:
    code = resolve_user_facing_status_code(task)
    return {
        "code": code,
        "label": label_for_user_status_code(code),
        "family": USER_STATUS_FAMILIES.get(code, USER_STATUS_FAMILIES[USER_STATUS_UNKNOWN]),
    }
