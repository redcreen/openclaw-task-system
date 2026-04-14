#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from argparse import ArgumentParser
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


UTC = timezone.utc
DEFAULT_OPENCLAW_HOME = Path.home() / ".openclaw"


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    summary: str
    remediation: str
    count: int = 1


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_excerpt(value: Optional[str], *, limit: int = 140) -> Optional[str]:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _coerce_ms(value: Any) -> Optional[int]:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _datetime_from_ms(value: Any) -> Optional[datetime]:
    timestamp_ms = _coerce_ms(value)
    if timestamp_ms is None or timestamp_ms <= 0:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)


def _datetime_from_iso(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _render_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone().isoformat(timespec="seconds")


def _openclaw_home(path: Optional[Path]) -> Path:
    return (path or DEFAULT_OPENCLAW_HOME).expanduser().resolve()


def _load_task_rows(db_path: Path, *, recent_limit: int) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT
              task_id,
              runtime,
              source_id,
              owner_key,
              scope_kind,
              child_session_key,
              parent_task_id,
              agent_id,
              run_id,
              label,
              task,
              status,
              delivery_status,
              notify_policy,
              created_at,
              started_at,
              ended_at,
              last_event_at,
              cleanup_after,
              error,
              progress_summary,
              terminal_summary,
              terminal_outcome,
              parent_flow_id
            FROM task_runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (recent_limit,),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def _load_failed_deliveries(failed_dir: Path) -> list[dict[str, Any]]:
    if not failed_dir.exists():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(failed_dir.glob("*.json")):
        try:
            payload = _read_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        enqueued_at = _datetime_from_ms(payload.get("enqueuedAt"))
        last_attempt_at = _datetime_from_ms(payload.get("lastAttemptAt"))
        items.append(
            {
                "path": str(path),
                "id": str(payload.get("id") or path.stem),
                "channel": str(payload.get("channel") or ""),
                "to": str(payload.get("to") or ""),
                "account_id": str(payload.get("accountId") or ""),
                "retry_count": int(payload.get("retryCount") or 0),
                "enqueued_at": _render_dt(enqueued_at),
                "last_attempt_at": _render_dt(last_attempt_at),
                "last_error": _safe_excerpt(payload.get("lastError"), limit=200),
                "session_key": str(((payload.get("mirror") or {}).get("sessionKey")) or ""),
                "text_excerpt": _safe_excerpt(
                    ((payload.get("payloads") or [{}])[0] or {}).get("text"),
                    limit=120,
                ),
            }
        )
    return items


def _load_cron_run_events(cron_runs_dir: Path, *, since: datetime) -> list[dict[str, Any]]:
    if not cron_runs_dir.exists():
        return []
    events: list[dict[str, Any]] = []
    for path in sorted(cron_runs_dir.glob("*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _datetime_from_ms(payload.get("ts"))
            if ts is None or ts < since:
                continue
            events.append(
                {
                    "path": str(path),
                    "job_id": str(payload.get("jobId") or path.stem),
                    "action": str(payload.get("action") or ""),
                    "status": str(payload.get("status") or ""),
                    "ts": _render_dt(ts),
                    "error": _safe_excerpt(payload.get("error"), limit=180),
                    "summary": _safe_excerpt(payload.get("summary"), limit=180),
                    "delivery_status": str(payload.get("deliveryStatus") or ""),
                    "session_key": str(payload.get("sessionKey") or ""),
                }
            )
    events.sort(key=lambda item: item["ts"] or "", reverse=True)
    return events


def _load_config_health(config_health_path: Path) -> dict[str, Any]:
    if not config_health_path.exists():
        return {
            "status": "missing",
            "entries": 0,
            "suspicious_entry_count": 0,
            "details": [],
        }
    try:
        payload = _read_json(config_health_path)
    except (OSError, json.JSONDecodeError):
        return {
            "status": "error",
            "entries": 0,
            "suspicious_entry_count": 0,
            "details": [],
        }
    entries = payload.get("entries") if isinstance(payload.get("entries"), dict) else {}
    suspicious = []
    for path, item in entries.items():
        signature = item.get("lastObservedSuspiciousSignature") if isinstance(item, dict) else None
        if signature:
            suspicious.append({"path": path, "signature": signature})
    return {
        "status": "warn" if suspicious else "ok",
        "entries": len(entries),
        "suspicious_entry_count": len(suspicious),
        "details": suspicious,
    }


def _derive_recent_task_entry(row: dict[str, Any]) -> dict[str, Any]:
    created_at = _datetime_from_ms(row.get("created_at"))
    last_event_at = _datetime_from_ms(row.get("last_event_at"))
    request_excerpt = _safe_excerpt(row.get("label") or row.get("task"), limit=120)
    reply_excerpt = _safe_excerpt(
        row.get("terminal_summary") or row.get("progress_summary") or row.get("error") or row.get("terminal_outcome"),
        limit=160,
    )
    return {
        "task_id": str(row.get("task_id") or ""),
        "created_at": _render_dt(created_at),
        "last_event_at": _render_dt(last_event_at),
        "agent_id": str(row.get("agent_id") or ""),
        "status": str(row.get("status") or ""),
        "delivery_status": str(row.get("delivery_status") or ""),
        "request_excerpt": request_excerpt,
        "reply_excerpt": reply_excerpt,
    }


def _is_internal_task(row: dict[str, Any]) -> bool:
    combined = " ".join(
        part
        for part in [
            str(row.get("label") or ""),
            str(row.get("task") or ""),
            str(row.get("terminal_summary") or ""),
        ]
        if part
    ).lower()
    markers = (
        "begin_openclaw_internal_context",
        "[subagent context]",
        "an async command the user already approved has completed",
    )
    return any(marker in combined for marker in markers)


def _contains_user_content_marker(value: Optional[str]) -> bool:
    text = str(value or "").lower()
    return "<task_user_content>" in text or "</task_user_content>" in text


def _recent_summary(rows: list[dict[str, Any]], *, since: datetime, recent_limit: int) -> dict[str, Any]:
    recent_rows = [
        row for row in rows if (_datetime_from_ms(row.get("created_at")) or datetime.min.replace(tzinfo=UTC)) >= since
    ]
    recent_user_rows = [row for row in recent_rows if not _is_internal_task(row)]
    status_counts: dict[str, int] = {}
    delivery_counts: dict[str, int] = {}
    for row in recent_rows:
        status = str(row.get("status") or "unknown")
        delivery_status = str(row.get("delivery_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        delivery_counts[delivery_status] = delivery_counts.get(delivery_status, 0) + 1
    recent_history = [_derive_recent_task_entry(row) for row in recent_user_rows[:recent_limit]]
    return {
        "window_hours": int(((_utc_now() - since).total_seconds()) // 3600),
        "task_count": len(recent_rows),
        "user_task_count": len(recent_user_rows),
        "status_counts": status_counts,
        "delivery_status_counts": delivery_counts,
        "recent_user_visible_history": recent_history,
    }


def _stale_running_tasks(
    rows: Iterable[dict[str, Any]],
    *,
    now: datetime,
    stale_after: timedelta,
) -> list[dict[str, Any]]:
    stale: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "")
        if status not in {"running", "queued", "registered", "received"}:
            continue
        last_event_at = _datetime_from_ms(row.get("last_event_at")) or _datetime_from_ms(row.get("created_at"))
        if last_event_at is None:
            continue
        age = now - last_event_at
        if age < stale_after:
            continue
        stale.append(
            {
                "task_id": str(row.get("task_id") or ""),
                "status": status,
                "agent_id": str(row.get("agent_id") or ""),
                "last_event_at": _render_dt(last_event_at),
                "age_hours": round(age.total_seconds() / 3600, 2),
                "request_excerpt": _safe_excerpt(row.get("label") or row.get("task"), limit=120),
            }
        )
    stale.sort(key=lambda item: item["age_hours"], reverse=True)
    return stale


def build_openclaw_runtime_audit(
    *,
    openclaw_home: Optional[Path] = None,
    lookback_hours: int = 24,
    recent_limit: int = 12,
    stale_running_hours: int = 6,
) -> dict[str, Any]:
    home = _openclaw_home(openclaw_home)
    now = _utc_now()
    since = now - timedelta(hours=max(1, lookback_hours))
    rows = _load_task_rows(home / "tasks" / "runs.sqlite", recent_limit=max(recent_limit * 4, 40))
    stale_tasks = _stale_running_tasks(rows, now=now, stale_after=timedelta(hours=max(1, stale_running_hours)))
    recent = _recent_summary(rows, since=since, recent_limit=recent_limit)
    user_content_leak_rows = [
        _derive_recent_task_entry(row)
        for row in rows
        if not _is_internal_task(row)
        and _contains_user_content_marker(row.get("terminal_summary") or row.get("progress_summary") or row.get("error"))
    ]
    failed_deliveries = _load_failed_deliveries(home / "delivery-queue" / "failed")
    cron_events = _load_cron_run_events(home / "cron" / "runs", since=since)
    cron_error_events = [item for item in cron_events if item["status"] == "error"]
    config_health = _load_config_health(home / "logs" / "config-health.json")

    issues: list[Issue] = []
    if not home.exists():
        issues.append(
            Issue(
                code="openclaw-home-missing",
                severity="error",
                count=1,
                summary=f"OpenClaw home does not exist: {home}",
                remediation="Pass the correct `--openclaw-home` path or restore the OpenClaw host data directory before trusting runtime audit output.",
            )
        )
    if stale_tasks:
        issues.append(
            Issue(
                code="stale-running-tasks",
                severity="error",
                count=len(stale_tasks),
                summary=f"{len(stale_tasks)} tasks are still marked running after the stale threshold.",
                remediation="Inspect each stale task with `python3 scripts/runtime/main_ops.py show <task_id>` and then resume, fail, or purge it explicitly once the true terminal state is known.",
            )
        )
    if failed_deliveries:
        issues.append(
            Issue(
                code="failed-deliveries",
                severity="warn",
                count=len(failed_deliveries),
                summary=f"{len(failed_deliveries)} delivery items remain in `delivery-queue/failed`.",
                remediation="Review failed payloads, fix address or channel configuration, then retry only the valid items from the host delivery path.",
            )
        )
    if user_content_leak_rows:
        issues.append(
            Issue(
                code="user-visible-content-markers",
                severity="error",
                count=len(user_content_leak_rows),
                summary=f"{len(user_content_leak_rows)} recent user-visible task summaries still contain internal task content markers.",
                remediation="Inspect the affected task results and scrub task-system-only markers before treating those replies as user-safe output.",
            )
        )
    if cron_error_events:
        issues.append(
            Issue(
                code="cron-delivery-errors",
                severity="warn",
                count=len(cron_error_events),
                summary=f"{len(cron_error_events)} cron runs ended with an error in the audit window.",
                remediation="Inspect the latest cron run errors, fix missing reply targets or channel binding, and rerun the affected cron job with a known-good destination before trusting scheduled notifications.",
            )
        )
    if config_health["status"] == "warn":
        issues.append(
            Issue(
                code="config-health-suspicious",
                severity="warn",
                count=int(config_health["suspicious_entry_count"]),
                summary="Config health recorded suspicious signatures.",
                remediation="Inspect `~/.openclaw/logs/config-health.json` and compare the affected config files against the last known good signature before continuing runtime operations.",
            )
        )
    if config_health["status"] == "missing":
        issues.append(
            Issue(
                code="config-health-missing",
                severity="warn",
                count=1,
                summary="Config health log is missing.",
                remediation="Regenerate or restore config health tracking so runtime audits can detect host-side config drift.",
            )
        )

    severity_order = {"error": 2, "warn": 1, "ok": 0}
    overall_status = "ok"
    for issue in issues:
        if severity_order[issue.severity] > severity_order[overall_status]:
            overall_status = issue.severity

    return {
        "status": overall_status,
        "checked_at": _render_dt(now),
        "openclaw_home": str(home),
        "lookback_hours": lookback_hours,
        "stale_running_hours": stale_running_hours,
        "issue_entries": [asdict(issue) for issue in issues],
        "recent_tasks": recent,
        "stale_running_tasks": stale_tasks,
        "failed_deliveries": {
            "count": len(failed_deliveries),
            "items": failed_deliveries[:recent_limit],
        },
        "user_visible_output_risks": {
            "content_marker_count": len(user_content_leak_rows),
            "items": user_content_leak_rows[:recent_limit],
        },
        "cron": {
            "event_count": len(cron_events),
            "error_count": len(cron_error_events),
            "latest_events": cron_events[:recent_limit],
        },
        "config_health": config_health,
        "operator_summary": {
            "recent_task_count": recent["task_count"],
            "recent_user_task_count": recent["user_task_count"],
            "recent_success_count": int(recent["status_counts"].get("succeeded", 0)),
            "recent_running_count": int(recent["status_counts"].get("running", 0)),
            "recent_delivered_count": int(recent["delivery_status_counts"].get("delivered", 0)),
            "recent_not_applicable_delivery_count": int(recent["delivery_status_counts"].get("not_applicable", 0)),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# OpenClaw Runtime Audit",
        "",
        f"- status: {report['status']}",
        f"- checked_at: {report['checked_at']}",
        f"- openclaw_home: {report['openclaw_home']}",
        f"- lookback_hours: {report['lookback_hours']}",
        f"- stale_running_hours: {report['stale_running_hours']}",
        "",
        "## Higher-Level View",
        "",
        f"- recent_task_count: {report['operator_summary']['recent_task_count']}",
        f"- recent_user_task_count: {report['operator_summary']['recent_user_task_count']}",
        f"- recent_success_count: {report['operator_summary']['recent_success_count']}",
        f"- recent_running_count: {report['operator_summary']['recent_running_count']}",
        f"- recent_delivered_count: {report['operator_summary']['recent_delivered_count']}",
        f"- recent_not_applicable_delivery_count: {report['operator_summary']['recent_not_applicable_delivery_count']}",
        f"- failed_delivery_count: {report['failed_deliveries']['count']}",
        f"- user_visible_content_marker_count: {report['user_visible_output_risks']['content_marker_count']}",
        f"- cron_error_count: {report['cron']['error_count']}",
        f"- stale_running_task_count: {len(report['stale_running_tasks'])}",
        "",
        "## User View",
        "",
    ]
    history = report["recent_tasks"]["recent_user_visible_history"]
    if history:
        for item in history:
            lines.append(
                f"- {item['created_at']} | {item['status']} | delivery={item['delivery_status']} | request={item['request_excerpt'] or 'none'} | reply={item['reply_excerpt'] or 'none'}"
            )
    else:
        lines.append("- no recent user-visible task history")

    lines.extend(["", "## Issues", ""])
    if report["issue_entries"]:
        for issue in report["issue_entries"]:
            lines.append(
                f"- {issue['severity']} | {issue['code']} | count={issue['count']} | {issue['summary']}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## Remediation", ""])
    if report["issue_entries"]:
        for issue in report["issue_entries"]:
            lines.append(f"- {issue['code']}: {issue['remediation']}")
    else:
        lines.append("- no action required")

    if report["stale_running_tasks"]:
        lines.extend(["", "## Stale Running Tasks", ""])
        for item in report["stale_running_tasks"]:
            lines.append(
                f"- {item['task_id']} | age_hours={item['age_hours']} | last_event_at={item['last_event_at']} | {item['request_excerpt'] or 'none'}"
            )

    if report["failed_deliveries"]["items"]:
        lines.extend(["", "## Failed Deliveries", ""])
        for item in report["failed_deliveries"]["items"]:
            lines.append(
                f"- {item['channel']} | retry_count={item['retry_count']} | to={item['to'] or 'none'} | error={item['last_error'] or 'none'}"
            )

    if report["user_visible_output_risks"]["items"]:
        lines.extend(["", "## User-Visible Output Risks", ""])
        for item in report["user_visible_output_risks"]["items"]:
            lines.append(
                f"- {item['task_id']} | delivery={item['delivery_status']} | request={item['request_excerpt'] or 'none'} | reply={item['reply_excerpt'] or 'none'}"
            )

    if report["cron"]["latest_events"]:
        lines.extend(["", "## Recent Cron Events", ""])
        for item in report["cron"]["latest_events"]:
            lines.append(
                f"- {item['ts']} | status={item['status']} | job_id={item['job_id']} | error={item['error'] or 'none'} | summary={item['summary'] or 'none'}"
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = ArgumentParser(
        description="Audit real OpenClaw runtime data from ~/.openclaw and summarize operator + user-visible health.",
    )
    parser.add_argument("--openclaw-home", type=Path, default=None)
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--recent-limit", type=int, default=12)
    parser.add_argument("--stale-running-hours", type=int, default=6)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = build_openclaw_runtime_audit(
        openclaw_home=args.openclaw_home,
        lookback_hours=args.lookback_hours,
        recent_limit=args.recent_limit,
        stale_running_hours=args.stale_running_hours,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
