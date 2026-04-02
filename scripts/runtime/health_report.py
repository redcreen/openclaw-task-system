#!/usr/bin/env python3
from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

from delivery_reconcile import reconcile_delivery_artifacts
from plugin_doctor import run_checks
from task_status import build_system_overview


def build_health_report(*, config_path: Optional[Path] = None) -> dict[str, object]:
    overview = build_system_overview(config_path=config_path)
    stale_findings = reconcile_delivery_artifacts(config_path=config_path, apply_changes=False)
    plugin_checks = run_checks()

    failing_plugin_checks = [check.name for check in plugin_checks if not check.ok]
    health_issues: list[str] = []

    if failing_plugin_checks:
        health_issues.append(f"plugin-checks-failed:{','.join(failing_plugin_checks)}")
    if overview["failed_instruction_count"]:
        health_issues.append(f"failed-instructions:{overview['failed_instruction_count']}")
    if overview["active_stale_delivery_task_count"]:
        health_issues.append(f"active-stale-delivery:{overview['active_stale_delivery_task_count']}")
    if overview["stale_delivery_task_count"]:
        health_issues.append(f"global-stale-delivery:{overview['stale_delivery_task_count']}")
    if overview["active_status_counts"].get("blocked", 0):
        health_issues.append(f"blocked-active-tasks:{overview['active_status_counts']['blocked']}")

    if health_issues:
        status = "warn"
    else:
        status = "ok"

    return {
        "status": status,
        "issues": health_issues,
        "overview": overview,
        "stale_findings": stale_findings,
        "plugin_checks": [
            {
                "name": check.name,
                "ok": check.ok,
                "detail": check.detail,
            }
            for check in plugin_checks
        ],
    }


def render_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Task System Health",
        "",
        f"- status: {report['status']}",
        f"- issue_count: {len(report['issues'])}",
    ]
    if report["issues"]:
        lines.append(f"- issues: {json.dumps(report['issues'], ensure_ascii=False)}")

    overview = report["overview"]
    lines.extend(
        [
            f"- active_task_count: {overview['active_task_count']}",
            f"- blocked_active_tasks: {overview['active_status_counts'].get('blocked', 0)}",
            f"- failed_instruction_count: {overview['failed_instruction_count']}",
            f"- active_stale_delivery_task_count: {overview['active_stale_delivery_task_count']}",
            f"- stale_delivery_task_count: {overview['stale_delivery_task_count']}",
        ]
    )

    lines.append("")
    lines.append("## Plugin Checks")
    lines.append("")
    for check in report["plugin_checks"]:
        status = "ok" if check["ok"] else "missing"
        lines.append(f"- {check['name']}: {status} ({check['detail']})")

    if report["stale_findings"]:
        lines.append("")
        lines.append("## Stale Delivery Findings")
        lines.append("")
        for finding in report["stale_findings"]:
            lines.append(f"- {finding['task_id']} | stale_count={len(finding['stale_paths'])}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = ArgumentParser(description="Summarize task-system health, delivery residue, and plugin readiness.")
    parser.add_argument("config", nargs="?", default=None, help="Optional task system config path")
    parser.add_argument("--json", action="store_true", help="Render JSON output")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser() if args.config else None
    report = build_health_report(config_path=config_path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
