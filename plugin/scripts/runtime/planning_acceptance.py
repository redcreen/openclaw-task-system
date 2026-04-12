#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from main_ops import get_main_continuity_summary, get_main_planning_summary
from openclaw_hooks import (
    attach_promise_guard_from_payload,
    claim_due_continuations_from_payload,
    create_followup_plan_from_payload,
    finalize_planned_followup_from_payload,
    register_from_payload,
    resolve_active_task_from_payload,
    should_send_short_followup_from_payload,
    sync_source_reply_target_from_payload,
    schedule_followup_from_plan_from_payload,
)
from task_status import build_status_summary
from task_state import TaskPaths, TaskStore, now_iso


@dataclass(frozen=True)
class AcceptanceStep:
    step: str
    ok: bool
    detail: str


def _write_config(path: Path, data_dir: Path) -> None:
    path.write_text(
        json.dumps({"taskSystem": {"storageDir": str(data_dir)}}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _set_env(config_path: Path) -> str | None:
    previous = os.environ.get("OPENCLAW_TASK_SYSTEM_CONFIG")
    os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = str(config_path)
    return previous


def _restore_env(previous: str | None) -> None:
    if previous is None:
        os.environ.pop("OPENCLAW_TASK_SYSTEM_CONFIG", None)
    else:
        os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = previous


def run_planning_acceptance() -> dict[str, Any]:
    temp_dir = Path(tempfile.mkdtemp(prefix="task-system-planning-acceptance."))
    data_dir = temp_dir / "data"
    config_path = temp_dir / "task_system.json"
    _write_config(config_path, data_dir)
    previous_env = _set_env(config_path)
    steps: list[AcceptanceStep] = []
    paths = TaskPaths.from_root(temp_dir, data_dir)
    store = TaskStore(paths=paths)
    try:
        registration = register_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:main:planning-acceptance:test",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:planning-acceptance",
                "user_id": "ou_acceptance",
                "user_request": "先整理这批问题，5分钟后回来同步结论",
                "estimated_steps": 4,
                "needs_verification": True,
            },
            config_path=config_path,
        )
        source_task_id = str(registration.get("task_id") or "")
        steps.append(
            AcceptanceStep(
                step="register-source-task",
                ok=bool(registration.get("should_register_task")) and bool(source_task_id),
                detail=json.dumps(registration, ensure_ascii=False),
            )
        )

        guarded = attach_promise_guard_from_payload(
            {
                "source_task_id": source_task_id,
                "promise_summary": "5分钟后同步结论",
                "followup_due_at": "2020-01-01T00:05:00+00:00",
            },
            config_path=config_path,
        )
        created = create_followup_plan_from_payload(
            {
                "source_task_id": source_task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2020-01-01T00:05:00+00:00",
                "followup_message": "5分钟后我回来同步最终结论",
                "followup_summary": "5分钟后同步最终结论",
                "main_user_content_mode": "none",
                "reply_to_id": "om_source_message",
                "thread_id": "thread_source_message",
            },
            config_path=config_path,
        )
        steps.append(
            AcceptanceStep(
                step="create-planning-tools-state",
                ok=bool(guarded.get("armed")) and bool(created.get("accepted")),
                detail=json.dumps(
                    {
                        "guarded": guarded,
                        "created": created,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        active_projection = resolve_active_task_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:main:planning-acceptance:test",
                "task_id": source_task_id,
            },
            config_path=config_path,
        )
        source_status = build_status_summary(source_task_id, config_path=config_path)
        steps.append(
            AcceptanceStep(
                step="project-future-first-immediate-output-contract",
                ok=(
                    bool(active_projection.get("found"))
                    and bool(active_projection.get("require_structured_user_content"))
                    and str(active_projection.get("main_user_content_mode") or "") == "none"
                    and str(((source_status.get("planning") or {}).get("main_user_content_mode")) or "") == "none"
                ),
                detail=json.dumps(
                    {
                        "active_projection": active_projection,
                        "source_status": {
                            "task_id": source_status.get("task_id"),
                            "planning": source_status.get("planning"),
                        },
                    },
                    ensure_ascii=False,
                ),
            )
        )

        summary_registration = register_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:main:planning-acceptance:immediate-summary",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:planning-acceptance:immediate-summary",
                "user_id": "ou_acceptance",
                "user_request": "先整理一版要点，10分钟后回来补最终结论",
                "estimated_steps": 3,
            },
            config_path=config_path,
        )
        summary_task_id = str(summary_registration.get("task_id") or "")
        synced_target = sync_source_reply_target_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:main:planning-acceptance:immediate-summary",
                "task_id": summary_task_id,
                "reply_to_id": "om_acceptance_source_message",
                "thread_id": "thread_acceptance_source_message",
            },
            config_path=config_path,
        )
        summary_plan = create_followup_plan_from_payload(
            {
                "source_task_id": summary_task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2099-01-01T00:10:00+00:00",
                "followup_message": "10分钟后回来补最终结论",
                "followup_summary": "10分钟后补最终结论",
                "main_user_content_mode": "immediate-summary",
            },
            config_path=config_path,
        )
        summary_projection = resolve_active_task_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:main:planning-acceptance:immediate-summary",
                "task_id": summary_task_id,
            },
            config_path=config_path,
        )
        summary_status = build_status_summary(summary_task_id, config_path=config_path)
        summary_scheduled = schedule_followup_from_plan_from_payload(
            {
                "source_task_id": summary_task_id,
                "plan_id": str(summary_plan.get("plan_id") or ""),
            },
            config_path=config_path,
        )
        summary_followup_task = None
        summary_followup_task_id = str(summary_scheduled.get("task_id") or "")
        if summary_followup_task_id:
            try:
                summary_followup_task = TaskStore(paths=TaskPaths.from_root(temp_dir, data_dir)).load_task(
                    summary_followup_task_id,
                    allow_archive=False,
                ).to_dict()
            except FileNotFoundError:
                summary_followup_task = None
        summary_continuation_payload = (
            ((summary_followup_task or {}).get("meta") or {}).get("continuation_payload")
            if isinstance((summary_followup_task or {}).get("meta"), dict)
            else None
        )
        summary_plan_state = (summary_status.get("planning") or {}) if isinstance(summary_status, dict) else {}
        steps.append(
            AcceptanceStep(
                step="project-immediate-summary-and-reply-target-contract",
                ok=(
                    bool(summary_registration.get("should_register_task"))
                    and bool(synced_target.get("updated"))
                    and bool(summary_plan.get("accepted"))
                    and str(summary_projection.get("main_user_content_mode") or "") == "immediate-summary"
                    and bool(summary_projection.get("require_structured_user_content"))
                    and str(summary_projection.get("reply_to_id") or "") == "om_acceptance_source_message"
                    and str(summary_projection.get("thread_id") or "") == "thread_acceptance_source_message"
                    and str(summary_plan_state.get("main_user_content_mode") or "") == "immediate-summary"
                    and bool(summary_scheduled.get("scheduled"))
                    and str((summary_continuation_payload or {}).get("reply_to_id") or "") == "om_acceptance_source_message"
                    and str((summary_continuation_payload or {}).get("thread_id") or "") == "thread_acceptance_source_message"
                ),
                detail=json.dumps(
                    {
                        "registration": summary_registration,
                        "synced_target": synced_target,
                        "plan": summary_plan,
                        "active_projection": summary_projection,
                        "planning": summary_plan_state,
                        "scheduled": summary_scheduled,
                        "continuation_payload": summary_continuation_payload,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        compound_registration = register_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:main:planning-acceptance:compound",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:planning-acceptance:compound",
                "user_id": "ou_acceptance",
                "user_request": "你先查一下天气，然后5分钟后回复我信息；",
                "estimated_steps": 2,
            },
            config_path=config_path,
        )
        compound_task_id = str(compound_registration.get("task_id") or "")
        compound_task = None
        compound_projection: dict[str, Any] = {}
        compound_status: dict[str, Any] = {}
        if compound_task_id:
            try:
                compound_task = TaskStore(paths=TaskPaths.from_root(temp_dir, data_dir)).load_task(
                    compound_task_id,
                    allow_archive=False,
                )
            except FileNotFoundError:
                compound_task = None
            compound_projection = resolve_active_task_from_payload(
                {
                    "agent_id": "main",
                    "session_key": "feishu:main:planning-acceptance:compound",
                    "task_id": compound_task_id,
                },
                config_path=config_path,
            )
            compound_status = build_status_summary(compound_task_id, config_path=config_path)
        compound_meta = compound_task.meta if compound_task is not None else {}
        compound_planning = (compound_status.get("planning") or {}) if isinstance(compound_status, dict) else {}
        steps.append(
            AcceptanceStep(
                step="compound-request-requires-structured-plan",
                ok=(
                    bool(compound_registration.get("should_register_task"))
                    and str(compound_registration.get("classification_reason") or "") == "observed-task"
                    and not compound_registration.get("continuation_due_at")
                    and "tool_followup_plan" not in compound_meta
                    and "post_run_continuation_plan" not in compound_meta
                    and not bool(compound_projection.get("require_structured_user_content"))
                    and not str(compound_projection.get("main_user_content_mode") or "").strip()
                    and not bool(compound_planning.get("has_followup_plan"))
                    and not bool(compound_planning.get("promise_guard_armed"))
                    and not str(compound_planning.get("followup_due_at") or "").strip()
                ),
                detail=json.dumps(
                    {
                        "registration": compound_registration,
                        "task_meta": compound_meta,
                        "active_projection": compound_projection,
                        "planning": compound_planning,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        promise_session_key = "feishu:main:planning-acceptance:promise-without-task"
        promise_registration = register_from_payload(
            {
                "agent_id": "main",
                "session_key": promise_session_key,
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:planning-acceptance:promise-without-task",
                "user_id": "ou_acceptance",
                "user_request": "先整理当前结论，10分钟后回来补最终同步",
                "estimated_steps": 3,
            },
            config_path=config_path,
        )
        promise_task_id = str(promise_registration.get("task_id") or "")
        promise_guarded = attach_promise_guard_from_payload(
            {
                "source_task_id": promise_task_id,
                "promise_summary": "10分钟后补最终同步",
                "followup_due_at": "2099-01-01T00:10:00+00:00",
            },
            config_path=config_path,
        )
        promise_plan = create_followup_plan_from_payload(
            {
                "source_task_id": promise_task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2099-01-01T00:10:00+00:00",
                "followup_message": "10分钟后回来补最终同步",
                "followup_summary": "10分钟后补最终同步",
                "main_user_content_mode": "none",
            },
            config_path=config_path,
        )
        promise_finalized = finalize_planned_followup_from_payload(
            {
                "source_task_id": promise_task_id,
                "plan_id": str(promise_plan.get("plan_id") or ""),
            },
            config_path=config_path,
        )
        promise_status = build_status_summary(promise_task_id, config_path=config_path)
        promise_planning = get_main_planning_summary(config_path=config_path, session_key=promise_session_key)
        promise_followup = should_send_short_followup_from_payload(
            {"task_id": promise_task_id},
            config_path=config_path,
        )
        promise_planning_state = (promise_status.get("planning") or {}) if isinstance(promise_status, dict) else {}
        steps.append(
            AcceptanceStep(
                step="promise-without-task-projects-recovery-contract",
                ok=(
                    bool(promise_registration.get("should_register_task"))
                    and bool(promise_guarded.get("armed"))
                    and bool(promise_plan.get("accepted"))
                    and not bool(promise_finalized.get("ok"))
                    and str(promise_finalized.get("reason") or "") == "promise-without-task"
                    and bool(promise_planning_state.get("promise_without_task"))
                    and str(promise_planning_state.get("anomaly") or "") == "promise-without-task"
                    and str((promise_planning.get("primary_recovery_action") or {}).get("kind") or "")
                    == "inspect-promise-without-task"
                    and bool(promise_followup.get("should_send"))
                    and str(
                        (((promise_followup.get("control_plane_message") or {}).get("metadata") or {}).get("planning_anomaly"))
                        or ""
                    )
                    == "promise-without-task"
                    and str(
                        (((promise_followup.get("control_plane_message") or {}).get("metadata") or {}).get("planning_recovery_hint"))
                        or ""
                    )
                    == "inspect-source-task-and-recreate-or-clear-promise"
                ),
                detail=json.dumps(
                    {
                        "registration": promise_registration,
                        "guarded": promise_guarded,
                        "plan": promise_plan,
                        "finalized": promise_finalized,
                        "planning": promise_planning_state,
                        "planning_summary": promise_planning,
                        "short_followup": promise_followup,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        timeout_session_key = "feishu:main:planning-acceptance:planner-timeout"
        timeout_registration = register_from_payload(
            {
                "agent_id": "main",
                "session_key": timeout_session_key,
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:planning-acceptance:planner-timeout",
                "user_id": "ou_acceptance",
                "user_request": "先整理一版要点，15分钟后回来补最终同步",
                "estimated_steps": 3,
            },
            config_path=config_path,
        )
        timeout_task_id = str(timeout_registration.get("task_id") or "")
        timeout_guarded = attach_promise_guard_from_payload(
            {
                "source_task_id": timeout_task_id,
                "promise_summary": "15分钟后补最终同步",
                "followup_due_at": "2099-01-01T00:15:00+00:00",
            },
            config_path=config_path,
        )
        timeout_plan = create_followup_plan_from_payload(
            {
                "source_task_id": timeout_task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2099-01-01T00:15:00+00:00",
                "followup_message": "15分钟后回来补最终同步",
                "followup_summary": "15分钟后补最终同步",
                "main_user_content_mode": "none",
            },
            config_path=config_path,
        )
        timeout_task = store.load_task(timeout_task_id, allow_archive=False)
        timeout_task.meta["planning_anomaly"] = "planner-timeout"
        timeout_task.meta["planning_anomaly_at"] = now_iso()
        timeout_guard_state = timeout_task.meta.get("planning_promise_guard")
        if isinstance(timeout_guard_state, dict):
            timeout_guard_state["status"] = "timeout"
            timeout_guard_state["checked_at"] = now_iso()
            timeout_task.meta["planning_promise_guard"] = timeout_guard_state
        timeout_plan_state = timeout_task.meta.get("tool_followup_plan")
        if isinstance(timeout_plan_state, dict):
            timeout_plan_state["status"] = "timeout"
            timeout_task.meta["tool_followup_plan"] = timeout_plan_state
        store.save_task(timeout_task)
        timeout_status = build_status_summary(timeout_task_id, config_path=config_path)
        timeout_planning = get_main_planning_summary(config_path=config_path, session_key=timeout_session_key)
        timeout_followup = should_send_short_followup_from_payload(
            {"task_id": timeout_task_id},
            config_path=config_path,
        )
        timeout_planning_state = (timeout_status.get("planning") or {}) if isinstance(timeout_status, dict) else {}
        steps.append(
            AcceptanceStep(
                step="planner-timeout-projects-recovery-contract",
                ok=(
                    bool(timeout_registration.get("should_register_task"))
                    and bool(timeout_guarded.get("armed"))
                    and bool(timeout_plan.get("accepted"))
                    and str(timeout_planning_state.get("anomaly") or "") == "planner-timeout"
                    and str(timeout_planning_state.get("promise_guard_status") or "") == "timeout"
                    and str(timeout_planning_state.get("plan_status") or "") == "timeout"
                    and str((timeout_planning.get("primary_recovery_action") or {}).get("kind") or "")
                    == "inspect-planner-timeout"
                    and bool(timeout_followup.get("should_send"))
                    and str(
                        (((timeout_followup.get("control_plane_message") or {}).get("metadata") or {}).get("planning_anomaly"))
                        or ""
                    )
                    == "planner-timeout"
                    and str(
                        (((timeout_followup.get("control_plane_message") or {}).get("metadata") or {}).get("planning_recovery_hint"))
                        or ""
                    )
                    == "inspect-source-task-after-planner-timeout"
                ),
                detail=json.dumps(
                    {
                        "registration": timeout_registration,
                        "guarded": timeout_guarded,
                        "plan": timeout_plan,
                        "planning": timeout_planning_state,
                        "planning_summary": timeout_planning,
                        "short_followup": timeout_followup,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        missing_session_key = "feishu:main:planning-acceptance:missing-followup-task"
        missing_registration = register_from_payload(
            {
                "agent_id": "main",
                "session_key": missing_session_key,
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:planning-acceptance:missing-followup-task",
                "user_id": "ou_acceptance",
                "user_request": "先整理当前状态，20分钟后回来补最终同步",
                "estimated_steps": 2,
            },
            config_path=config_path,
        )
        missing_task_id = str(missing_registration.get("task_id") or "")
        missing_guarded = attach_promise_guard_from_payload(
            {
                "source_task_id": missing_task_id,
                "promise_summary": "20分钟后补最终同步",
                "followup_due_at": "2099-01-01T00:20:00+00:00",
            },
            config_path=config_path,
        )
        missing_plan = create_followup_plan_from_payload(
            {
                "source_task_id": missing_task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2099-01-01T00:20:00+00:00",
                "followup_message": "20分钟后回来补最终同步",
                "followup_summary": "20分钟后补最终同步",
                "main_user_content_mode": "none",
            },
            config_path=config_path,
        )
        missing_scheduled = schedule_followup_from_plan_from_payload(
            {
                "source_task_id": missing_task_id,
                "plan_id": str(missing_plan.get("plan_id") or ""),
            },
            config_path=config_path,
        )
        missing_followup_task_id = str(missing_scheduled.get("task_id") or "")
        missing_followup_path = paths.inflight_dir / f"{missing_followup_task_id}.json"
        if missing_followup_task_id and missing_followup_path.exists():
            missing_followup_path.unlink()
        missing_status = build_status_summary(missing_task_id, config_path=config_path)
        missing_planning = get_main_planning_summary(config_path=config_path, session_key=missing_session_key)
        missing_followup = should_send_short_followup_from_payload(
            {"task_id": missing_task_id},
            config_path=config_path,
        )
        missing_planning_state = (missing_status.get("planning") or {}) if isinstance(missing_status, dict) else {}
        steps.append(
            AcceptanceStep(
                step="missing-followup-task-projects-recovery-contract",
                ok=(
                    bool(missing_registration.get("should_register_task"))
                    and bool(missing_guarded.get("armed"))
                    and bool(missing_plan.get("accepted"))
                    and bool(missing_scheduled.get("scheduled"))
                    and bool(missing_followup_task_id)
                    and not missing_followup_path.exists()
                    and bool(missing_planning_state.get("followup_task_missing"))
                    and str(missing_planning_state.get("anomaly") or "") == "followup-task-missing"
                    and str((missing_planning.get("primary_recovery_action") or {}).get("kind") or "")
                    == "inspect-missing-followup-task"
                    and bool(missing_followup.get("should_send"))
                    and str(
                        (((missing_followup.get("control_plane_message") or {}).get("metadata") or {}).get("planning_anomaly"))
                        or ""
                    )
                    == "followup-task-missing"
                    and str(
                        (((missing_followup.get("control_plane_message") or {}).get("metadata") or {}).get("planning_recovery_hint"))
                        or ""
                    )
                    == "inspect-source-task-and-relink-followup-task"
                ),
                detail=json.dumps(
                    {
                        "registration": missing_registration,
                        "guarded": missing_guarded,
                        "plan": missing_plan,
                        "scheduled": missing_scheduled,
                        "planning": missing_planning_state,
                        "planning_summary": missing_planning,
                        "short_followup": missing_followup,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        scheduled = schedule_followup_from_plan_from_payload(
            {
                "source_task_id": source_task_id,
                "plan_id": str(created.get("plan_id") or ""),
            },
            config_path=config_path,
        )
        finalized = finalize_planned_followup_from_payload(
            {
                "source_task_id": source_task_id,
                "plan_id": str(created.get("plan_id") or ""),
                "followup_task_id": str(scheduled.get("task_id") or ""),
            },
            config_path=config_path,
        )
        steps.append(
            AcceptanceStep(
                step="materialize-and-finalize-followup",
                ok=bool(scheduled.get("scheduled")) and bool(finalized.get("promise_fulfilled")),
                detail=json.dumps(
                    {
                        "scheduled": scheduled,
                        "finalized": finalized,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        claimed = claim_due_continuations_from_payload({}, config_path=config_path)
        planning = get_main_planning_summary(config_path=config_path)
        continuity = get_main_continuity_summary(config_path=config_path)
        followup_task = None
        scheduled_task_id = str(scheduled.get("task_id") or "")
        if scheduled_task_id:
            try:
                followup_task = store.load_task(scheduled_task_id, allow_archive=False).to_dict()
            except FileNotFoundError:
                followup_task = None
        steps.append(
            AcceptanceStep(
                step="claim-overdue-followup-and-project-ops",
                ok=claimed.get("claimed_count") == 1 and planning.get("planning_task_count", 0) >= 1,
                detail=json.dumps(
                    {
                        "claimed": claimed,
                        "planning": planning,
                        "continuity": continuity,
                        "followup_task": followup_task,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        return {
            "ok": all(step.ok for step in steps),
            "steps": [asdict(step) for step in steps],
            "tempDir": str(temp_dir),
            "configPath": str(config_path),
            "dataDir": str(data_dir),
        }
    finally:
        _restore_env(previous_env)
        shutil.rmtree(temp_dir, ignore_errors=True)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Planning Acceptance", "", f"- ok: {payload['ok']}"]
    for step in payload["steps"]:
        lines.append(f"- {step['step']}: {'ok' if step['ok'] else 'failed'}")
        lines.append(f"  detail: {step['detail']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    payload = run_planning_acceptance()
    if sys.argv[1:] and sys.argv[1] == "--json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
