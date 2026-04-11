#!/usr/bin/env python3
from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

import main_ops
from task_config import load_task_system_config
from task_state import TaskPaths, default_paths
from task_status import build_status_summary, render_status_markdown


SCHEMA = "openclaw.task-system.task-cli.v1"


def _resolve_paths(config_path: Optional[Path], *, paths: Optional[TaskPaths] = None) -> TaskPaths:
    if paths is not None:
        return paths
    config = load_task_system_config(config_path=config_path)
    return config.build_paths() or default_paths()


def get_task_cli_tasks(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    tasks = main_ops.list_main_tasks(config_path=config_path, paths=resolved_paths)
    return {
        "schema": SCHEMA,
        "view": "tasks",
        "task_count": len(tasks),
        "tasks": tasks,
    }


def render_task_cli_tasks(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    summary = get_task_cli_tasks(config_path=config_path, paths=paths)
    tasks = summary["tasks"]
    lines = ["# Task CLI", "", f"- view: {summary['view']}", f"- task_count: {summary['task_count']}"]
    if not tasks:
        lines.extend(["", "## Tasks", "", "- none"])
        return "\n".join(lines) + "\n"
    lines.extend(["", "## Tasks", ""])
    for task in tasks:
        lines.append(
            f"- {task['task_id']} | {task['status']} | user_status={task['user_facing_status']} | session={task['session_key']} | {task['task_label']}"
        )
    return "\n".join(lines) + "\n"


def get_task_cli_task(
    task_id: str,
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    return {
        "schema": SCHEMA,
        "view": "task",
        "task": build_status_summary(task_id, paths=resolved_paths, config_path=config_path),
    }


def render_task_cli_task(
    task_id: str,
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    return render_status_markdown(task_id, paths=_resolve_paths(config_path, paths=paths), config_path=config_path)


def get_task_cli_session(
    session_key: str,
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    dashboard = main_ops.get_main_dashboard_summary(
        config_path=config_path,
        paths=resolved_paths,
        session_key=session_key,
        compact=True,
    )
    tasks = [
        task
        for task in main_ops.list_main_tasks(config_path=config_path, paths=resolved_paths)
        if str(task.get("session_key") or "") == session_key
    ]
    return {
        "schema": SCHEMA,
        "view": "session",
        "session_key": session_key,
        "task_count": len(tasks),
        "tasks": tasks,
        "dashboard": dashboard["compact_summary"],
        "continuity": dashboard["continuity"],
        "queues": dashboard["queues"],
        "lanes": dashboard["lanes"],
        "taskmonitor": dashboard["taskmonitor"],
        "suggested_next_commands": dashboard["suggested_next_commands"],
    }


def render_task_cli_session(
    session_key: str,
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    summary = get_task_cli_session(session_key, config_path=config_path, paths=paths)
    dashboard = summary["dashboard"]
    continuity = summary["continuity"]
    queues = summary["queues"]
    lanes = summary["lanes"]
    lines = [
        "# Task CLI",
        "",
        f"- view: {summary['view']}",
        f"- session_key: {summary['session_key']}",
        f"- status: {dashboard['status']}",
        f"- task_count: {summary['task_count']}",
        f"- queue_count: {queues['queue_count']}",
        f"- lane_agent_count: {lanes['agent_count']}",
        f"- continuity_auto_resumable_task_count: {continuity['auto_resumable_task_count']}",
        f"- continuity_manual_review_task_count: {continuity['manual_review_task_count']}",
        "",
        "## Tasks",
        "",
    ]
    if not summary["tasks"]:
        lines.append("- none")
    else:
        for task in summary["tasks"]:
            lines.append(
                f"- {task['task_id']} | {task['status']} | user_status={task['user_facing_status']} | {task['task_label']}"
            )
    lines.extend(
        [
            "",
            "## Next",
            "",
        ]
    )
    for command in summary["suggested_next_commands"]:
        lines.append(f"- {command}")
    return "\n".join(lines) + "\n"


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Short task-system CLI for common task/session queries.")
    parser.add_argument("--config", help="Optional task system config path.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    tasks_parser = subparsers.add_parser("tasks", help="List current main tasks.")
    tasks_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")

    task_parser = subparsers.add_parser("task", help="Show one task detail.")
    task_parser.add_argument("task_id")
    task_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")

    session_parser = subparsers.add_parser("session", help="Show one session's task/continuity/queue/lane summary.")
    session_parser.add_argument("session_key")
    session_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config_path = Path(args.config).expanduser() if args.config else None

    if args.command == "tasks":
        if args.json:
            print(json.dumps(get_task_cli_tasks(config_path=config_path), ensure_ascii=False, indent=2))
            return 0
        print(render_task_cli_tasks(config_path=config_path), end="")
        return 0
    if args.command == "task":
        if args.json:
            print(json.dumps(get_task_cli_task(args.task_id, config_path=config_path), ensure_ascii=False, indent=2))
            return 0
        print(render_task_cli_task(args.task_id, config_path=config_path), end="")
        return 0
    if args.command == "session":
        if args.json:
            print(json.dumps(get_task_cli_session(args.session_key, config_path=config_path), ensure_ascii=False, indent=2))
            return 0
        print(render_task_cli_session(args.session_key, config_path=config_path), end="")
        return 0
    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
