#!/usr/bin/env python3
from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

from delivery_reconcile import reconcile_delivery_artifacts
from instruction_executor import summarize_failed_instructions
from plugin_doctor import run_checks
from task_config import load_task_system_config
from task_state import TaskPaths, default_paths
from task_status import build_system_overview


def _issue_entry(code: str, severity: str, count: int, remediation: str) -> dict[str, object]:
    return {
        "code": code,
        "severity": severity,
        "count": count,
        "remediation": remediation,
    }


def build_health_report(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    resolved_paths = paths
    if resolved_paths is None:
        config = load_task_system_config(config_path=config_path)
        resolved_paths = config.build_paths() or default_paths()
    overview = build_system_overview(config_path=config_path, paths=paths)
    stale_findings = reconcile_delivery_artifacts(config_path=config_path, paths=paths, apply_changes=False)
    plugin_checks = run_checks()
    failed_instruction_summary = summarize_failed_instructions(paths=resolved_paths)

    failing_plugin_checks = [check.name for check in plugin_checks if not check.ok]
    issue_entries: list[dict[str, object]] = []

    if failing_plugin_checks:
        issue_entries.append(
            _issue_entry(
                code=f"plugin-checks-failed:{','.join(failing_plugin_checks)}",
                severity="error",
                count=len(failing_plugin_checks),
                remediation="Run `python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py` and fix missing plugin paths/config.",
            )
        )
    if overview["failed_instruction_count"]:
        issue_entries.append(
            _issue_entry(
                code=f"failed-instructions:{overview['failed_instruction_count']}",
                severity="error",
                count=int(overview["failed_instruction_count"]),
                remediation="Inspect `data/failed-instructions/` and `dispatch-results/`; retry only retryable transport failures with `instruction_executor.py --execute`, and fix auth/config issues before retrying non-retryable failures.",
            )
        )
    if overview["active_stale_delivery_task_count"]:
        issue_entries.append(
            _issue_entry(
                code=f"active-stale-delivery:{overview['active_stale_delivery_task_count']}",
                severity="warn",
                count=int(overview["active_stale_delivery_task_count"]),
                remediation="Run `delivery_reconcile.py` to inspect residue; if confirmed safe, run `delivery_reconcile.py --apply`.",
            )
        )
    if overview["stale_delivery_task_count"]:
        issue_entries.append(
            _issue_entry(
                code=f"global-stale-delivery:{overview['stale_delivery_task_count']}",
                severity="warn",
                count=int(overview["stale_delivery_task_count"]),
                remediation="Clean old delivery residue with `delivery_reconcile.py --apply` to keep health signals accurate.",
            )
        )
    blocked_count = int(overview["active_status_counts"].get("blocked", 0))
    if blocked_count:
        issue_entries.append(
            _issue_entry(
                code=f"blocked-active-tasks:{blocked_count}",
                severity="warn",
                count=blocked_count,
                remediation="Inspect blocked tasks with `task_status.py --overview` and resume or fail them explicitly through the host flow.",
            )
        )

    severities = {entry["severity"] for entry in issue_entries}
    if "error" in severities:
        status = "error"
    elif "warn" in severities:
        status = "warn"
    else:
        status = "ok"

    return {
        "status": status,
        "issues": [str(entry["code"]) for entry in issue_entries],
        "issue_entries": issue_entries,
        "overview": overview,
        "failed_instruction_summary": failed_instruction_summary,
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
            f"- failed_instruction_retryable_count: {report['failed_instruction_summary']['retryable']}",
            f"- failed_instruction_non_retryable_count: {report['failed_instruction_summary']['non_retryable']}",
            f"- failed_instruction_unknown_count: {report['failed_instruction_summary']['unknown']}",
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

    if report["issue_entries"]:
        lines.append("")
        lines.append("## Remediation")
        lines.append("")
        for issue in report["issue_entries"]:
            lines.append(f"- [{issue['severity']}] {issue['code']}: {issue['remediation']}")

    if report["stale_findings"]:
        lines.append("")
        lines.append("## Stale Delivery Findings")
        lines.append("")
        for finding in report["stale_findings"]:
            lines.append(f"- {finding['task_id']} | stale_count={len(finding['stale_paths'])}")

    if report["failed_instruction_summary"]["items"]:
        lines.append("")
        lines.append("## Failed Instructions")
        lines.append("")
        for item in report["failed_instruction_summary"]["items"]:
            lines.append(
                f"- {item['name']} | classification={item['failure_classification']} | retryable={item['retryable']}"
            )

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
