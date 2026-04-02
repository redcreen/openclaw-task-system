#!/usr/bin/env python3
from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

from delivery_reconcile import reconcile_delivery_artifacts
from health_report import build_health_report
from instruction_executor import annotate_failed_instruction_metadata, retry_failed_instructions
from main_task_adapter import block_main_task, fail_main_task, finish_main_task, resume_main_task
from task_config import load_task_system_config
from task_status import list_inflight_statuses, render_overview_markdown, render_status_markdown
from task_state import TaskPaths, default_paths


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
        f"- non_retryable_failed_instruction_count: {failed_summary['non_retryable']}",
        f"- unknown_failed_instruction_count: {failed_summary['unknown']}",
        "",
        "## Next Actions",
        "",
    ]

    if blocked_main:
        task = blocked_main[0]
        lines.append(
            f"- Resume blocked main task: `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py resume {task['task_id']} --note \"继续推进并同步真实进展\"`"
        )
        lines.append(
            f"- Or fail it explicitly: `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py fail {task['task_id']} --reason \"manual close after triage\"`"
        )
    else:
        lines.append("- No blocked main task requires manual action.")

    if failed_summary["retryable"]:
        lines.append(
            "- Retry retryable failed instructions on host: `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py repair --execute-retries --execution-context host`"
        )
    else:
        lines.append("- No retryable failed instructions are waiting.")

    if failed_summary["non_retryable"]:
        lines.append("- Review non-retryable failures in `data/failed-instructions/` and correct target/auth/config before retrying.")
    else:
        lines.append("- No non-retryable failed instructions are waiting.")

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

    subparsers.add_parser("overview", help="Show task system overview.")
    subparsers.add_parser("health", help="Show main-oriented health summary.")
    subparsers.add_parser("triage", help="Show prioritized next actions for main-agent operations.")
    repair_parser = subparsers.add_parser("repair", help="Clean stale delivery state and optionally retry failed sends.")
    repair_parser.add_argument("--execute-retries", action="store_true", help="Retry retryable failed instructions.")
    repair_parser.add_argument("--openclaw-bin", default=None, help="Override openclaw binary for retry execution.")
    repair_parser.add_argument(
        "--execution-context",
        default="local",
        help="Execution context label to write into retry dispatch results.",
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
    if args.command == "overview":
        print(render_overview_markdown(config_path=config_path), end="")
        return
    if args.command == "health":
        print(render_main_health(config_path=config_path), end="")
        return
    if args.command == "triage":
        print(render_main_triage(config_path=config_path, paths=paths), end="")
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


if __name__ == "__main__":
    main()
