#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from emit_task_event import write_outbox
from task_config import TaskSystemConfig, load_task_system_config
from task_state import STATUS_BLOCKED, STATUS_RUNNING, TaskPaths, TaskState, TaskStore, now_iso

DEFAULT_TIMEOUT_SECONDS = 30
RESEND_INTERVAL_SECONDS = 30


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


@dataclass
class SilenceFinding:
    task_id: str
    agent_id: str
    session_key: str
    channel: str
    chat_id: str
    status: str
    silence_seconds: int
    last_user_visible_update_at: str
    should_notify: bool
    reason: str
    escalation: str | None = None
    continuation_wake_state: str | None = None
    continuation_wake_attempt_count: int = 0
    continuation_last_wake_at: str | None = None
    continuation_wake_message: str | None = None


def is_active_task(task: TaskState) -> bool:
    return task.status == STATUS_RUNNING


def should_notify_task(
    task: TaskState,
    *,
    silence_seconds: int,
    now_dt: datetime,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    resend_interval_seconds: int = RESEND_INTERVAL_SECONDS,
) -> tuple[bool, str]:
    if silence_seconds <= timeout_seconds:
        return False, "within-timeout"

    last_notified = task.last_monitor_notify_at
    if not last_notified:
        return True, "first-overdue"

    delta = (now_dt - parse_iso(last_notified)).total_seconds()
    if delta >= resend_interval_seconds:
        return True, "resend-overdue"

    return False, "recently-notified"


def scan_tasks(
    tasks: Iterable[TaskState],
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    resend_interval_seconds: int = RESEND_INTERVAL_SECONDS,
) -> list[SilenceFinding]:
    findings: list[SilenceFinding] = []
    now_dt = now()
    for task in tasks:
        if not is_active_task(task):
            continue
        if not task.last_user_visible_update_at:
            continue
        silence_seconds = int((now_dt - parse_iso(task.last_user_visible_update_at)).total_seconds())
        notify, reason = should_notify_task(
            task,
            silence_seconds=silence_seconds,
            now_dt=now_dt,
            timeout_seconds=timeout_seconds,
            resend_interval_seconds=resend_interval_seconds,
        )
        if silence_seconds > timeout_seconds:
            escalation = None
            if str(task.meta.get("finalize_skipped_reason") or "").strip() == "success-without-visible-progress":
                escalation = "blocked-no-visible-progress"
            findings.append(
                SilenceFinding(
                    task_id=task.task_id,
                    agent_id=task.agent_id,
                    session_key=task.session_key,
                    channel=task.channel,
                    chat_id=task.chat_id,
                    status=task.status,
                    silence_seconds=silence_seconds,
                    last_user_visible_update_at=task.last_user_visible_update_at,
                    should_notify=notify,
                    reason=reason,
                    escalation=escalation,
                    continuation_wake_state=str(task.meta.get("continuation_wake_state") or "").strip() or None,
                    continuation_wake_attempt_count=int(task.meta.get("continuation_wake_attempt_count") or 0),
                    continuation_last_wake_at=str(task.meta.get("continuation_last_wake_at") or "").strip() or None,
                    continuation_wake_message=str(task.meta.get("continuation_wake_message") or "").strip() or None,
                )
            )
    return findings


def scan_inflight(
    store: TaskStore,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    resend_interval_seconds: int = RESEND_INTERVAL_SECONDS,
) -> list[SilenceFinding]:
    tasks = [store.load_task(path.stem, allow_archive=False) for path in store.list_inflight()]
    return scan_tasks(
        tasks,
        timeout_seconds=timeout_seconds,
        resend_interval_seconds=resend_interval_seconds,
    )


def fallback_message(_finding: SilenceFinding) -> str:
    if _finding.escalation == "blocked-no-visible-progress":
        return (
            "[task] 当前长任务没有形成可靠的可见进展，且执行过程中出现了内部重试或模型失败；"
            "我已将它标记为阻塞，后续需要继续重试、切换模型，或人工介入确认。"
        )
    if _finding.continuation_wake_state:
        message = (
            "[task] 已收到你的任务，当前仍在处理中；"
            f"最近一次已尝试唤醒 agent {max(_finding.continuation_wake_attempt_count, 1)} 次"
        )
        if _finding.continuation_wake_message:
            message += f"，最近状态：{_finding.continuation_wake_message}"
        return message + "。"
    return (
        "[task] 已收到你的任务，当前仍在处理中；"
        "如果 30 秒内还没有新的阶段结果，我会继续同步当前进展或阻塞点。"
    )


def mark_overdue_notified(store: TaskStore, task_id: str) -> TaskState:
    task = store.load_task(task_id, allow_archive=False)
    ts = now_iso()
    task.last_monitor_notify_at = ts
    task.notify_count = int(task.notify_count) + 1
    task.monitor_state = "notified"
    task.updated_at = ts
    task.last_internal_touch_at = ts
    return store.save_task(task)


def escalate_stalled_task(store: TaskStore, finding: SilenceFinding) -> TaskState:
    if finding.escalation == "blocked-no-visible-progress":
        task = store.block_task(
            finding.task_id,
            "agent run ended without visible progress; likely model failure or internal retry",
        )
        task.monitor_state = "blocked"
        task.meta["watchdog_escalation"] = finding.escalation
        task.meta["watchdog_escalation_at"] = now_iso()
        return store.save_task(task)
    return store.load_task(finding.task_id, allow_archive=False)


def process_overdue_tasks(
    *,
    paths: Optional[TaskPaths] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    resend_interval_seconds: int = RESEND_INTERVAL_SECONDS,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> list[dict[str, object]]:
    runtime_config = config or load_task_system_config(config_path=config_path)
    store = TaskStore(paths=paths or runtime_config.build_paths())
    findings: list[SilenceFinding] = []
    for path in store.list_inflight():
        task = store.load_task(path.stem, allow_archive=False)
        agent_config = runtime_config.agent_config(task.agent_id)
        monitor = agent_config.silence_monitor
        if not runtime_config.enabled or not agent_config.enabled or not monitor.enabled:
            continue
        findings.extend(
            scan_tasks(
                [task],
                timeout_seconds=monitor.silent_timeout_seconds,
                resend_interval_seconds=monitor.resend_interval_seconds,
            )
        )
    output: list[dict[str, object]] = []
    for finding in findings:
        if finding.should_notify:
            task = mark_overdue_notified(store, finding.task_id)
            if finding.escalation:
                task = escalate_stalled_task(store, finding)
            write_outbox(task.to_dict(), message=fallback_message(finding), paths=store.paths)
        output.append(
            {
                "task_id": finding.task_id,
                "agent_id": finding.agent_id,
                "session_key": finding.session_key,
                "channel": finding.channel,
                "chat_id": finding.chat_id,
                "status": finding.status,
                "silence_seconds": finding.silence_seconds,
                "should_notify": finding.should_notify,
                "reason": finding.reason,
                "escalation": finding.escalation,
                "fallback_message": fallback_message(finding),
            }
        )
    return output


if __name__ == "__main__":
    print(json.dumps(process_overdue_tasks(), ensure_ascii=False, indent=2))
