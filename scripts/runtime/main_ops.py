#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from delivery_reconcile import reconcile_delivery_artifacts
from delivery_outage import acknowledge_outage, clear_outage
from health_report import build_health_report
from instruction_executor import (
    annotate_failed_instruction_metadata,
    resolve_failed_instructions,
    retry_failed_instructions,
)
from main_task_adapter import block_main_task, fail_main_task, finish_main_task, resume_main_task
from task_config import load_task_system_config
from task_status import list_inflight_statuses, render_overview_markdown, render_status_markdown
from task_state import STATUS_QUEUED, STATUS_RUNNING, TaskPaths, TaskStore, default_paths


def _resolve_paths(config_path: Optional[Path], *, paths: Optional[TaskPaths] = None) -> TaskPaths:
    if paths is not None:
        return paths
    config = load_task_system_config(config_path=config_path)
    return config.build_paths() or default_paths()


def list_main_tasks(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> list[dict[str, object]]:
    return [
        status
        for status in list_inflight_statuses(config_path=config_path, paths=paths)
        if status["agent_id"] == "main"
    ]


def render_main_list(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    tasks = list_main_tasks(config_path=config_path, paths=paths)
    if not tasks:
        return "# Main Tasks\n\n- none\n"
    lines = ["# Main Tasks", ""]
    for task in tasks:
        lines.append(
            f"- {task['task_id']} | {task['status']} | delivery={task['delivery']['state']} | {task['task_label']}"
        )
    return "\n".join(lines) + "\n"


def render_main_health(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    report = build_health_report(config_path=config_path, paths=paths)
    overview = report["overview"]
    blocked_main = [
        task for task in overview["active_tasks"] if task["agent_id"] == "main" and task["status"] == "blocked"
    ]
    lines = [
        "# Main Ops Health",
        "",
        f"- status: {report['status']}",
        f"- main_active_task_count: {len([task for task in overview['active_tasks'] if task['agent_id'] == 'main'])}",
        f"- main_blocked_task_count: {len(blocked_main)}",
        f"- failed_instruction_count: {overview['failed_instruction_count']}",
        f"- active_stale_delivery_task_count: {overview['active_stale_delivery_task_count']}",
    ]
    if blocked_main:
        lines.append("")
        lines.append("## Blocked Main Tasks")
        lines.append("")
        for task in blocked_main:
            lines.append(f"- {task['task_id']} | {task['task_label']}")
    return "\n".join(lines) + "\n"


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _blocked_age_minutes(task: dict[str, object], *, now: Optional[datetime] = None) -> Optional[int]:
    anchor = _parse_iso8601(str(task.get("updated_at") or task.get("started_at") or task.get("created_at") or ""))
    if anchor is None:
        return None
    current = now or datetime.now(timezone.utc).astimezone(anchor.tzinfo)
    return max(0, int((current - anchor).total_seconds() // 60))


def sweep_main_tasks(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    fail_stale_blocked_after_minutes: Optional[int] = None,
    reason: str = "automatic stale blocked cleanup",
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    blocked_tasks = [task for task in list_main_tasks(config_path=config_path, paths=resolved_paths) if task["status"] == "blocked"]
    actions: list[dict[str, object]] = []
    for task in blocked_tasks:
        blocked_age = _blocked_age_minutes(task)
        should_fail = (
            fail_stale_blocked_after_minutes is not None
            and blocked_age is not None
            and blocked_age >= fail_stale_blocked_after_minutes
        )
        if should_fail:
            updated = fail_main_task(str(task["task_id"]), reason, paths=resolved_paths)
            actions.append(
                {
                    "task_id": updated.task_id,
                    "action": "failed",
                    "blocked_age_minutes": blocked_age,
                    "reason": reason,
                }
            )
        else:
            actions.append(
                {
                    "task_id": str(task["task_id"]),
                    "action": "noop",
                    "blocked_age_minutes": blocked_age,
                }
            )
    return {
        "blocked_main_task_count": len(blocked_tasks),
        "actions": actions,
    }


def resolve_main_failures(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    task_ids: Optional[list[str]] = None,
    include_non_retryable: bool = False,
    include_persistent_retryable: bool = False,
    min_retry_count: int = 1,
    apply_changes: bool = False,
    reason: str = "manual failed instruction resolution",
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    findings = resolve_failed_instructions(
        paths=resolved_paths,
        task_ids=task_ids,
        include_non_retryable=include_non_retryable,
        include_persistent_retryable=include_persistent_retryable,
        min_retry_count=min_retry_count,
        apply_changes=apply_changes,
        reason=reason,
    )
    return {
        "apply_changes": apply_changes,
        "resolved_count": len(findings),
        "findings": findings,
    }


def render_delivery_diagnose(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    report = build_health_report(config_path=config_path, paths=paths)
    config = load_task_system_config(config_path=config_path)
    failed_summary = report["failed_instruction_summary"]
    retryable_items = [item for item in failed_summary["items"] if item["retryable"]]

    lines = [
        "# Delivery Diagnose",
        "",
        f"- openclaw_bin: {config.delivery.openclaw_bin}",
        f"- retryable_failed_instruction_count: {failed_summary['retryable']}",
        f"- persistent_retryable_failed_instruction_count: {failed_summary['persistent_retryable']}",
    ]

    if not retryable_items:
        lines.extend(
            [
                "",
                "## Status",
                "",
                "- No retryable delivery failure needs host diagnosis.",
            ]
        )
        return "\n".join(lines) + "\n"

    probe = retryable_items[0]
    probe_target = probe.get("chat_id") or "<chat-id>"
    probe_channel = probe.get("channel") or "telegram"

    lines.extend(
        [
            "",
            "## Probe Target",
            "",
            f"- task_id: {probe.get('task_id')}",
            f"- channel: {probe_channel}",
            f"- chat_id: {probe_target}",
            f"- retry_count: {probe.get('retry_count')}",
        ]
    )
    if probe.get("last_error_summary"):
        lines.append(f"- last_error: {probe['last_error_summary']}")

    probe_command = (
        f"{config.delivery.openclaw_bin} message send --channel {probe_channel} "
        f"--target {probe_target} --message \"task system network probe\""
    )
    lines.extend(
        [
            "",
            "## Suggested Checks",
            "",
            f"- Run host probe command: `{probe_command}`",
            "- If the probe fails with the same network message, investigate the host network path or Telegram connectivity before retrying task-system delivery.",
            "- If the probe succeeds, rerun `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py repair --execute-retries --execution-context host`.",
        ]
    )
    return "\n".join(lines) + "\n"


def acknowledge_delivery_outage(
    *,
    channel: str,
    chat_id: str,
    reason: str,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    return acknowledge_outage(channel=channel, chat_id=chat_id, reason=reason, paths=resolved_paths)


def clear_delivery_outage(
    *,
    channel: str,
    chat_id: str,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    removed = clear_outage(channel=channel, chat_id=chat_id, paths=resolved_paths)
    return {
        "channel": channel,
        "chat_id": chat_id,
        "removed": removed,
    }


def render_main_triage(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    report = build_health_report(config_path=config_path, paths=paths)
    overview = report["overview"]
    blocked_main = [
        task for task in overview["active_tasks"] if task["agent_id"] == "main" and task["status"] == "blocked"
    ]
    failed_summary = report["failed_instruction_summary"]

    lines = [
        "# Main Ops Triage",
        "",
        f"- status: {report['status']}",
        f"- blocked_main_task_count: {len(blocked_main)}",
        f"- retryable_failed_instruction_count: {failed_summary['retryable']}",
        f"- persistent_retryable_failed_instruction_count: {failed_summary['persistent_retryable']}",
        f"- non_retryable_failed_instruction_count: {failed_summary['non_retryable']}",
        f"- unknown_failed_instruction_count: {failed_summary['unknown']}",
        "",
        "## Next Actions",
        "",
    ]

    if blocked_main:
        task = blocked_main[0]
        blocked_age = _blocked_age_minutes(task)
        lines.append(
            f"- Resume blocked main task: `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py resume {task['task_id']} --note \"继续推进并同步真实进展\"`"
        )
        lines.append(
            f"- Or fail it explicitly: `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py fail {task['task_id']} --reason \"manual close after triage\"`"
        )
        if blocked_age is not None:
            lines.append(f"- Current blocked age: {blocked_age} minute(s)")
            if blocked_age >= 60:
                lines.append(
                    f"- Optional stale cleanup: `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py sweep --fail-stale-blocked-after-minutes 60 --reason \"stale blocked main task\"`"
                )
    else:
        lines.append("- No blocked main task requires manual action.")

    persistent_retryable_items = [
        item for item in failed_summary["items"] if item["retryable"] and item["retry_count"] > 0
    ]

    if failed_summary["retryable"] and not persistent_retryable_items:
        lines.append(
            "- Retry retryable failed instructions on host: `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py repair --execute-retries --execution-context host`"
        )
    elif persistent_retryable_items:
        lines.append(
            "- Persistent retryable failures detected. Investigate host network/connectivity before running more retries."
        )
    else:
        lines.append("- No retryable failed instructions are waiting.")

    if failed_summary["non_retryable"]:
        lines.append("- Review non-retryable failures in `data/failed-instructions/` and correct target/auth/config before retrying.")
    else:
        lines.append("- No non-retryable failed instructions are waiting.")

    retryable_items = [item for item in failed_summary["items"] if item["retryable"]]
    non_retryable_items = [item for item in failed_summary["items"] if item["retryable"] is False]

    if retryable_items:
        lines.append("")
        lines.append("## Retryable Failed Instructions")
        lines.append("")
        for item in retryable_items:
            lines.append(
                f"- {item['name']} | classification={item['failure_classification']} | retry_count={item['retry_count']}"
            )
            if item.get("last_error_summary"):
                lines.append(f"  last_error: {item['last_error_summary']}")

    if non_retryable_items:
        lines.append("")
        lines.append("## Non-Retryable Failed Instructions")
        lines.append("")
        for item in non_retryable_items:
            lines.append(
                f"- {item['name']} | classification={item['failure_classification']} | chat_id={item['chat_id']}"
            )
            if item.get("last_error_summary"):
                lines.append(f"  last_error: {item['last_error_summary']}")

    return "\n".join(lines) + "\n"


def repair_system(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    execute_retries: bool = False,
    openclaw_bin: Optional[str] = None,
    execution_context: str = "local",
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    health_before = build_health_report(config_path=config_path, paths=resolved_paths)
    stale_cleanup = reconcile_delivery_artifacts(paths=resolved_paths, apply_changes=True)
    annotated_failures = annotate_failed_instruction_metadata(
        paths=resolved_paths,
        openclaw_bin=openclaw_bin or load_task_system_config(config_path=config_path).delivery.openclaw_bin,
    )
    retry_results: list[dict[str, object]] = []
    if execute_retries:
        retry_results = retry_failed_instructions(
            paths=resolved_paths,
            openclaw_bin=openclaw_bin or load_task_system_config(config_path=config_path).delivery.openclaw_bin,
            execution_context=execution_context,
        )
    health_after = build_health_report(config_path=config_path, paths=resolved_paths)
    return {
        "health_before": health_before,
        "stale_cleanup": stale_cleanup,
        "annotated_failures": annotated_failures,
        "retry_results": retry_results,
        "health_after": health_after,
    }


def _cancel_host_session(
    *,
    session_key: str,
    openclaw_bin: str,
) -> dict[str, object]:
    command = [openclaw_bin, "tasks", "cancel", session_key]
    result = subprocess.run(command, capture_output=True, text=True)
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "ok": result.returncode == 0,
    }


def stop_main_queue(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    openclaw_bin: Optional[str] = None,
    reason: str = "user requested stop",
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=resolved_paths)
    running_tasks = store.find_running_tasks(agent_id="main")
    queued_tasks = store.find_queued_tasks(agent_id="main")

    selected = running_tasks[0] if running_tasks else (queued_tasks[0] if queued_tasks else None)
    if selected is None:
        return {
            "action": "noop",
            "reason": "no-main-task-to-stop",
            "remaining_running_count": 0,
            "remaining_queued_count": 0,
            "remaining_active_count": 0,
            "suggestion": "当前没有可停止的 main 任务。",
        }

    host_cancel = None
    if selected.status == STATUS_RUNNING:
        host_cancel = _cancel_host_session(
            session_key=selected.session_key,
            openclaw_bin=openclaw_bin or config.delivery.openclaw_bin,
        )
        if not host_cancel["ok"]:
            return {
                "action": "host-cancel-failed",
                "task_id": selected.task_id,
                "status": selected.status,
                "host_cancel": host_cancel,
            }

    cancelled = store.cancel_task(selected.task_id, reason, archive=True)
    remaining_running = store.find_running_tasks(agent_id="main")
    remaining_queued = store.find_queued_tasks(agent_id="main")
    return {
        "action": "stopped-current" if selected.status == STATUS_RUNNING else "stopped-queued-head",
        "task_id": cancelled.task_id,
        "stopped_status": selected.status,
        "host_cancel": host_cancel,
        "remaining_running_count": len(remaining_running),
        "remaining_queued_count": len(remaining_queued),
        "remaining_active_count": len(remaining_running) + len(remaining_queued),
        "next_running_task_id": remaining_running[0].task_id if remaining_running else None,
        "suggestion": (
            f"已停止 1 个任务；当前前面还有 {len(remaining_running) + len(remaining_queued)} 个号。"
            " 如果希望停止全部，请回复“停止全部”。"
        ),
    }


def stop_all_main_queue(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    openclaw_bin: Optional[str] = None,
    reason: str = "user requested stop all",
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=resolved_paths)

    queued_tasks = store.find_queued_tasks(agent_id="main")
    running_tasks = store.find_running_tasks(agent_id="main")
    cancelled_tasks: list[dict[str, object]] = []
    host_cancels: list[dict[str, object]] = []

    for task in queued_tasks:
        cancelled = store.cancel_task(task.task_id, reason, archive=True)
        cancelled_tasks.append(
            {
                "task_id": cancelled.task_id,
                "status": STATUS_QUEUED,
            }
        )

    for task in running_tasks:
        host_cancel = _cancel_host_session(
            session_key=task.session_key,
            openclaw_bin=openclaw_bin or config.delivery.openclaw_bin,
        )
        host_cancels.append({"task_id": task.task_id, **host_cancel})
        if host_cancel["ok"]:
            cancelled = store.cancel_task(task.task_id, reason, archive=True)
            cancelled_tasks.append(
                {
                    "task_id": cancelled.task_id,
                    "status": STATUS_RUNNING,
                }
            )

    remaining_running = store.find_running_tasks(agent_id="main")
    remaining_queued = store.find_queued_tasks(agent_id="main")
    return {
        "action": "stopped-all",
        "cancelled_count": len(cancelled_tasks),
        "cancelled_tasks": cancelled_tasks,
        "host_cancels": host_cancels,
        "remaining_running_count": len(remaining_running),
        "remaining_queued_count": len(remaining_queued),
        "remaining_active_count": len(remaining_running) + len(remaining_queued),
        "suggestion": "已停止当前执行任务，并清空剩余队列。",
    }


def main() -> None:
    parser = ArgumentParser(description="Operate and inspect main-agent tasks.")
    parser.add_argument("--config", help="Optional task system config path.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List active main tasks.")
    show_parser = subparsers.add_parser("show", help="Show one main task.")
    show_parser.add_argument("task_id")

    resume_parser = subparsers.add_parser("resume", help="Resume a blocked main task.")
    resume_parser.add_argument("task_id")
    resume_parser.add_argument("--note", default=None)

    block_parser = subparsers.add_parser("block", help="Mark a main task blocked.")
    block_parser.add_argument("task_id")
    block_parser.add_argument("--reason", required=True)

    fail_parser = subparsers.add_parser("fail", help="Mark a main task failed.")
    fail_parser.add_argument("task_id")
    fail_parser.add_argument("--reason", required=True)

    complete_parser = subparsers.add_parser("complete", help="Mark a main task completed.")
    complete_parser.add_argument("task_id")
    complete_parser.add_argument("--summary", default=None)
    stop_parser = subparsers.add_parser("stop", help="Stop the current running main task or the head of the queue.")
    stop_parser.add_argument("--reason", default="user requested stop")
    stop_parser.add_argument("--openclaw-bin", default=None)
    stop_all_parser = subparsers.add_parser("stop-all", help="Stop the running main task and clear the remaining queue.")
    stop_all_parser.add_argument("--reason", default="user requested stop all")
    stop_all_parser.add_argument("--openclaw-bin", default=None)

    subparsers.add_parser("overview", help="Show task system overview.")
    subparsers.add_parser("health", help="Show main-oriented health summary.")
    subparsers.add_parser("triage", help="Show prioritized next actions for main-agent operations.")
    subparsers.add_parser("diagnose-delivery", help="Show host-side delivery diagnosis steps for retryable failures.")
    ack_parser = subparsers.add_parser("ack-delivery-outage", help="Acknowledge a known external delivery outage.")
    ack_parser.add_argument("--channel", required=True)
    ack_parser.add_argument("--chat-id", required=True)
    ack_parser.add_argument("--reason", required=True)
    clear_parser = subparsers.add_parser("clear-delivery-outage", help="Clear an acknowledged external delivery outage.")
    clear_parser.add_argument("--channel", required=True)
    clear_parser.add_argument("--chat-id", required=True)
    repair_parser = subparsers.add_parser("repair", help="Clean stale delivery state and optionally retry failed sends.")
    repair_parser.add_argument("--execute-retries", action="store_true", help="Retry retryable failed instructions.")
    repair_parser.add_argument("--openclaw-bin", default=None, help="Override openclaw binary for retry execution.")
    repair_parser.add_argument(
        "--execution-context",
        default="local",
        help="Execution context label to write into retry dispatch results.",
    )
    sweep_parser = subparsers.add_parser("sweep", help="Inspect or fail stale blocked main tasks.")
    sweep_parser.add_argument(
        "--fail-stale-blocked-after-minutes",
        type=int,
        default=None,
        help="If set, blocked main tasks older than this threshold will be failed.",
    )
    sweep_parser.add_argument(
        "--reason",
        default="automatic stale blocked cleanup",
        help="Reason recorded when failing stale blocked tasks.",
    )
    resolve_parser = subparsers.add_parser("resolve-failures", help="Inspect or resolve failed instructions.")
    resolve_parser.add_argument("--task-id", action="append", default=None, help="Specific failed task id to resolve.")
    resolve_parser.add_argument("--non-retryable", action="store_true", help="Select non-retryable failed instructions.")
    resolve_parser.add_argument(
        "--persistent-retryable",
        action="store_true",
        help="Select retryable failed instructions that already retried at least once.",
    )
    resolve_parser.add_argument(
        "--min-retry-count",
        type=int,
        default=1,
        help="Minimum retry count used with --persistent-retryable.",
    )
    resolve_parser.add_argument("--apply", action="store_true", help="Actually move selected failures out of active failed-instructions.")
    resolve_parser.add_argument(
        "--reason",
        default="manual failed instruction resolution",
        help="Reason recorded when applying failed instruction resolution.",
    )

    args = parser.parse_args()
    config_path = Path(args.config).expanduser() if args.config else None
    paths = _resolve_paths(config_path, paths=None)

    if args.command == "list":
        print(render_main_list(config_path=config_path), end="")
        return
    if args.command == "show":
        print(render_status_markdown(args.task_id, paths=paths), end="")
        return
    if args.command == "resume":
        task = resume_main_task(args.task_id, progress_note=args.note, paths=paths)
        print(json.dumps(task.to_dict(), ensure_ascii=False, indent=2))
        return
    if args.command == "block":
        task = block_main_task(args.task_id, args.reason, paths=paths)
        print(json.dumps(task.to_dict(), ensure_ascii=False, indent=2))
        return
    if args.command == "fail":
        task = fail_main_task(args.task_id, args.reason, paths=paths)
        print(json.dumps(task.to_dict(), ensure_ascii=False, indent=2))
        return
    if args.command == "complete":
        task = finish_main_task(args.task_id, result_summary=args.summary, paths=paths)
        print(json.dumps(task.to_dict(), ensure_ascii=False, indent=2))
        return
    if args.command == "stop":
        result = stop_main_queue(
            config_path=config_path,
            paths=paths,
            openclaw_bin=args.openclaw_bin,
            reason=args.reason,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "stop-all":
        result = stop_all_main_queue(
            config_path=config_path,
            paths=paths,
            openclaw_bin=args.openclaw_bin,
            reason=args.reason,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "overview":
        print(render_overview_markdown(config_path=config_path), end="")
        return
    if args.command == "health":
        print(render_main_health(config_path=config_path), end="")
        return
    if args.command == "triage":
        print(render_main_triage(config_path=config_path, paths=paths), end="")
        return
    if args.command == "diagnose-delivery":
        print(render_delivery_diagnose(config_path=config_path, paths=paths), end="")
        return
    if args.command == "ack-delivery-outage":
        print(
            json.dumps(
                acknowledge_delivery_outage(
                    channel=args.channel,
                    chat_id=args.chat_id,
                    reason=args.reason,
                    config_path=config_path,
                    paths=paths,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.command == "clear-delivery-outage":
        print(
            json.dumps(
                clear_delivery_outage(
                    channel=args.channel,
                    chat_id=args.chat_id,
                    config_path=config_path,
                    paths=paths,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.command == "repair":
        result = repair_system(
            config_path=config_path,
            paths=paths,
            execute_retries=args.execute_retries,
            openclaw_bin=args.openclaw_bin,
            execution_context=args.execution_context,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "sweep":
        result = sweep_main_tasks(
            config_path=config_path,
            paths=paths,
            fail_stale_blocked_after_minutes=args.fail_stale_blocked_after_minutes,
            reason=args.reason,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "resolve-failures":
        result = resolve_main_failures(
            config_path=config_path,
            paths=paths,
            task_ids=args.task_id,
            include_non_retryable=args.non_retryable,
            include_persistent_retryable=args.persistent_retryable,
            min_retry_count=args.min_retry_count,
            apply_changes=args.apply,
            reason=args.reason,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
