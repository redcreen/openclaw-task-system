#!/usr/bin/env python3
from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

from delivery_outage import find_outage, load_outages
from delivery_reconcile import reconcile_delivery_artifacts
from instruction_executor import summarize_failed_instructions
from plugin_install_drift import build_install_drift_report
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


def _planning_primary_recovery_action(overview: dict[str, object]) -> Optional[dict[str, object]]:
    planning = overview.get("planning") if isinstance(overview.get("planning"), dict) else {}
    recovery_action = planning.get("primary_recovery_action")
    if isinstance(recovery_action, dict) and str(recovery_action.get("kind") or "").strip() not in {"", "none"}:
        return recovery_action
    return None


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
    install_drift = build_install_drift_report()
    failed_instruction_summary = summarize_failed_instructions(paths=resolved_paths)
    acknowledged_outages = load_outages(paths=resolved_paths)

    failing_plugin_checks = [check.name for check in plugin_checks if not check.ok and check.name != "installed_runtime_sync"]
    issue_entries: list[dict[str, object]] = []

    if failing_plugin_checks:
        issue_entries.append(
            _issue_entry(
                code=f"plugin-checks-failed:{','.join(failing_plugin_checks)}",
                severity="error",
                count=len(failing_plugin_checks),
                remediation="Run `python3 scripts/runtime/plugin_doctor.py` from the task-system root and fix missing plugin paths/config.",
            )
        )
    if not bool(install_drift["ok"]):
        issue_entries.append(
            _issue_entry(
                code=f"plugin-install-drift:{len(install_drift['missing_in_installed'])}",
                severity="warn",
                count=len(install_drift["missing_in_installed"]),
                remediation="Run `python3 scripts/runtime/plugin_install_drift.py --json` to inspect install drift; current OpenClaw local install may be blocked by dangerous-code detection, so do not assume `openclaw plugins install ./plugin` will refresh the installed runtime.",
            )
        )
    acknowledged_failed_items = [
        item
        for item in failed_instruction_summary["items"]
        if find_outage(
            channel=str(item.get("channel") or ""),
            chat_id=str(item.get("chat_id") or ""),
            paths=resolved_paths,
        )
    ]

    if overview["failed_instruction_count"]:
        all_failed_are_acknowledged = len(acknowledged_failed_items) == int(overview["failed_instruction_count"])
        issue_entries.append(
            _issue_entry(
                code=f"failed-instructions:{overview['failed_instruction_count']}",
                severity="warn" if all_failed_are_acknowledged else "error",
                count=int(overview["failed_instruction_count"]),
                remediation=(
                    "Known external delivery outage acknowledged; restore host connectivity and then rerun `main_ops.py repair --execute-retries --execution-context host`."
                    if all_failed_are_acknowledged
                    else "Inspect `data/failed-instructions/` and `dispatch-results/`; retry only retryable transport failures with `instruction_executor.py --execute`, and fix auth/config issues before retrying non-retryable failures."
                ),
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
    planning = overview.get("planning") if isinstance(overview.get("planning"), dict) else {}
    planning_health = planning.get("health") if isinstance(planning.get("health"), dict) else {}
    planning_recovery_action = _planning_primary_recovery_action(overview)
    promise_without_task_count = int(planning.get("promise_without_task_count", 0) or 0)
    overdue_followup_count = int(planning.get("overdue_followup_count", 0) or 0)
    planning_pending_count = int(planning.get("planning_pending_task_count", 0) or 0)
    planning_timeout_count = int(planning_health.get("timeout_count", 0) or 0)
    if promise_without_task_count:
        issue_entries.append(
            _issue_entry(
                code=f"planning-promise-without-task:{promise_without_task_count}",
                severity="error",
                count=promise_without_task_count,
                remediation=(
                    f"{planning_recovery_action['summary']} "
                    f"Start with `{planning_recovery_action['command']}`."
                    if planning_recovery_action and planning_recovery_action.get("command")
                    else "Inspect planning anomalies in `main_ops.py dashboard --json` or `task_status.py --overview`; fix the tool path so every future promise materializes a real follow-up task before finalize."
                ),
            )
        )
    if overdue_followup_count:
        issue_entries.append(
            _issue_entry(
                code=f"planning-overdue-followups:{overdue_followup_count}",
                severity="warn",
                count=overdue_followup_count,
                remediation=(
                    f"{planning_recovery_action['summary']} "
                    f"Start with `{planning_recovery_action['command']}`."
                    if planning_recovery_action
                    and planning_recovery_action.get("kind") == "inspect-overdue-followup"
                    and planning_recovery_action.get("command")
                    else "Inspect overdue planned follow-ups in `main_ops.py continuity --json` and ensure the continuation runner is progressing or recover the affected sessions."
                ),
            )
        )
    if planning_timeout_count:
        issue_entries.append(
            _issue_entry(
                code=f"planning-timeouts:{planning_timeout_count}",
                severity="warn",
                count=planning_timeout_count,
                remediation=(
                    f"{planning_recovery_action['summary']} "
                    f"Start with `{planning_recovery_action['command']}`."
                    if planning_recovery_action
                    and planning_recovery_action.get("kind") == "inspect-planner-timeout"
                    and planning_recovery_action.get("command")
                    else "Inspect `main_ops.py planning --json` to find recent planner timeouts; downgrade planning-dependent behavior until the planner path is stable again."
                ),
            )
        )
    if planning_pending_count and not promise_without_task_count:
        issue_entries.append(
            _issue_entry(
                code=f"planning-pending:{planning_pending_count}",
                severity="warn",
                count=planning_pending_count,
                remediation=(
                    f"{planning_recovery_action['summary']} "
                    f"Start with `{planning_recovery_action['command']}`."
                    if planning_recovery_action
                    and planning_recovery_action.get("kind") == "inspect-pending-plan"
                    and planning_recovery_action.get("command")
                    else "Review pending planning tasks to confirm follow-up plans are materialized and finalized as expected."
                ),
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
        "acknowledged_delivery_outages": acknowledged_outages,
        "acknowledged_failed_instruction_count": len(acknowledged_failed_items),
        "stale_findings": stale_findings,
        "plugin_checks": [
            {
                "name": check.name,
                "ok": check.ok,
                "detail": check.detail,
            }
            for check in plugin_checks
        ],
        "plugin_install_drift": install_drift,
        "planning_primary_recovery_action": planning_recovery_action,
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
            f"- acknowledged_failed_instruction_count: {report['acknowledged_failed_instruction_count']}",
            f"- resolved_failed_instruction_count: {overview['resolved_failed_instruction_count']}",
            f"- failed_instruction_retryable_count: {report['failed_instruction_summary']['retryable']}",
            f"- failed_instruction_persistent_retryable_count: {report['failed_instruction_summary']['persistent_retryable']}",
            f"- failed_instruction_non_retryable_count: {report['failed_instruction_summary']['non_retryable']}",
            f"- failed_instruction_unknown_count: {report['failed_instruction_summary']['unknown']}",
            f"- active_stale_delivery_task_count: {overview['active_stale_delivery_task_count']}",
            f"- stale_delivery_task_count: {overview['stale_delivery_task_count']}",
            f"- planning_tool_path_task_count: {overview['planning']['tool_path_task_count']}",
            f"- planning_pending_task_count: {overview['planning']['planning_pending_task_count']}",
            f"- planning_promise_without_task_count: {overview['planning']['promise_without_task_count']}",
            f"- planning_overdue_followup_count: {overview['planning']['overdue_followup_count']}",
        ]
    )
    planning_health = overview["planning"].get("health") if isinstance(overview["planning"].get("health"), dict) else None
    if isinstance(planning_health, dict):
        lines.extend(
            [
                f"- planning_health_status: {planning_health['status']}",
                f"- planning_health_primary_reason: {planning_health['primary_reason']}",
                f"- planning_health_sample_task_count: {planning_health['sample_task_count']}",
                f"- planning_health_success_rate: {planning_health['success_rate']}",
                f"- planning_health_timeout_rate: {planning_health['timeout_rate']}",
                f"- planning_health_tool_call_completion_rate: {planning_health['tool_call_completion_rate']}",
                f"- planning_health_promise_without_task_rate: {planning_health['promise_without_task_rate']}",
            ]
        )
    planning_recovery_action = report.get("planning_primary_recovery_action")
    if isinstance(planning_recovery_action, dict):
        lines.extend(
            [
                f"- planning_primary_recovery_action_kind: {planning_recovery_action.get('kind')}",
                f"- planning_primary_recovery_action_command: {planning_recovery_action.get('command') or 'none'}",
            ]
        )
    if overview["planning"]["anomaly_counts"]:
        lines.append(f"- planning_anomaly_counts: {json.dumps(overview['planning']['anomaly_counts'], ensure_ascii=False)}")

    lines.append("")
    lines.append("## Plugin Checks")
    lines.append("")
    for check in report["plugin_checks"]:
        status = "ok" if check["ok"] else "missing"
        lines.append(f"- {check['name']}: {status} ({check['detail']})")

    drift = report.get("plugin_install_drift", {})
    if isinstance(drift, dict):
        lines.append("")
        lines.append("## Installed Runtime Drift")
        lines.append("")
        lines.append(f"- ok: {drift.get('ok')}")
        lines.append(f"- installed_runtime_exists: {drift.get('installed_runtime_exists')}")
        lines.append(f"- missing_in_installed: {json.dumps(drift.get('missing_in_installed', []), ensure_ascii=False)}")
        lines.append(f"- extra_in_installed: {json.dumps(drift.get('extra_in_installed', []), ensure_ascii=False)}")

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

    if report["acknowledged_delivery_outages"]:
        lines.append("")
        lines.append("## Acknowledged Delivery Outages")
        lines.append("")
        for outage in report["acknowledged_delivery_outages"]:
            lines.append(
                f"- {outage['channel']}:{outage['chat_id']} | reason={outage['reason']}"
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
