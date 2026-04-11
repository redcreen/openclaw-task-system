#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

TASK_USER_CONTENT_OPEN = "<task_user_content>"
TASK_USER_CONTENT_CLOSE = "</task_user_content>"
DEFAULT_GATEWAY_DIR = Path("/tmp/openclaw")
DEFAULT_PLUGIN_DEBUG_LOG = Path.home() / ".openclaw" / "extensions" / "openclaw-task-system" / "data" / "plugin-debug.log"
DEFAULT_AGENTS_ROOT = Path.home() / ".openclaw" / "agents"
DEFAULT_SESSION_GLOB = "*.jsonl*"


@dataclass(frozen=True)
class ScanTarget:
    name: str
    path: str
    exists: bool
    scanned: bool
    tail_lines: int | None


@dataclass(frozen=True)
class LeakHit:
    source: str
    path: str
    line_number: int
    line: str


def iso_today() -> str:
    return datetime.now().date().isoformat()


def default_gateway_log_path(record_date: str | None = None) -> Path:
    return DEFAULT_GATEWAY_DIR / f"openclaw-{record_date or iso_today()}.log"


def _line_has_marker(line: str) -> bool:
    return TASK_USER_CONTENT_OPEN in line or TASK_USER_CONTENT_CLOSE in line


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _extract_line_timestamp(line: str) -> datetime | None:
    try:
        payload = json.loads(line)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    meta = payload.get("_meta")
    if isinstance(meta, dict):
        parsed = _parse_iso_timestamp(meta.get("date"))
        if parsed is not None:
            return parsed
    parsed = _parse_iso_timestamp(payload.get("ts"))
    if parsed is not None:
        return parsed
    message = payload.get("message")
    if isinstance(message, dict):
        parsed = _parse_iso_timestamp(payload.get("timestamp"))
        if parsed is not None:
            return parsed
    return _parse_iso_timestamp(payload.get("timestamp"))


def resolve_latest_session_file(session_dir: Path) -> Path | None:
    if not session_dir.exists():
        return None
    candidates = sorted(
        [path for path in session_dir.glob(DEFAULT_SESSION_GLOB) if path.is_file()],
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    if not candidates:
        return None
    return candidates[-1]


def collect_marker_hits(
    path: Path,
    source: str,
    *,
    tail_lines: int | None = None,
    max_hits: int = 20,
    since: datetime | None = None,
) -> list[LeakHit]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if tail_lines is not None and tail_lines > 0:
        start_line = max(len(lines) - tail_lines, 0)
        lines = lines[start_line:]
    else:
        start_line = 0
    hits: list[LeakHit] = []
    for offset, line in enumerate(lines, start=1):
        if since is not None:
            line_ts = _extract_line_timestamp(line)
            if line_ts is not None and line_ts < since:
                continue
        if not _line_has_marker(line):
            continue
        hits.append(
            LeakHit(
                source=source,
                path=str(path),
                line_number=start_line + offset,
                line=line[:400],
            )
        )
        if len(hits) >= max_hits:
            break
    return hits


def _resolve_latest_main_session_file() -> Path | None:
    return resolve_latest_session_file(DEFAULT_AGENTS_ROOT / "main" / "sessions")


def _collect_session_files(
    *,
    session_file: Path | None = None,
    latest_only: bool = True,
    agents_root: Path | None = None,
) -> list[Path]:
    resolved_agents_root = agents_root or DEFAULT_AGENTS_ROOT
    if session_file is not None:
        return [session_file]
    if latest_only:
        latest = _resolve_latest_main_session_file()
        return [latest] if latest is not None else []
    files: list[Path] = []
    if not resolved_agents_root.exists():
        return files
    for session_dir in sorted(resolved_agents_root.glob("*/sessions")):
        files.extend(path for path in sorted(session_dir.glob(DEFAULT_SESSION_GLOB)) if path.is_file())
    return files


def _build_targets(
    *,
    gateway_path: Path,
    plugin_debug_path: Path,
    session_paths: list[Path],
    latest_only: bool,
    tail_lines: int,
) -> list[ScanTarget]:
    targets = [
        ScanTarget(
            name="gateway_log",
            path=str(gateway_path),
            exists=gateway_path.exists(),
            scanned=True,
            tail_lines=tail_lines,
        ),
        ScanTarget(
            name="plugin_debug_log",
            path=str(plugin_debug_path),
            exists=plugin_debug_path.exists(),
            scanned=True,
            tail_lines=tail_lines,
        ),
    ]
    if latest_only:
        session_path = session_paths[0] if session_paths else None
        targets.append(
            ScanTarget(
                name="latest_main_session",
                path=str(session_path) if session_path is not None else str(DEFAULT_AGENTS_ROOT / "main" / "sessions" / "<latest-session-not-found>"),
                exists=session_path.exists() if session_path is not None else False,
                scanned=session_path is not None,
                tail_lines=None,
            )
        )
    else:
        targets.append(
            ScanTarget(
                name="all_agent_sessions",
                path=str(DEFAULT_AGENTS_ROOT),
                exists=DEFAULT_AGENTS_ROOT.exists(),
                scanned=True,
                tail_lines=None,
            )
        )
    return targets


def run_audit(
    *,
    record_date: str | None = None,
    gateway_log: Path | None = None,
    session_file: Path | None = None,
    plugin_debug_log: Path | None = None,
    tail_lines: int = 400,
    latest_only: bool = True,
    since: datetime | None = None,
) -> dict[str, Any]:
    gateway_path = gateway_log or default_gateway_log_path(record_date)
    plugin_debug_path = plugin_debug_log or DEFAULT_PLUGIN_DEBUG_LOG
    session_paths = _collect_session_files(session_file=session_file, latest_only=latest_only)
    targets = _build_targets(
        gateway_path=gateway_path,
        plugin_debug_path=plugin_debug_path,
        session_paths=session_paths,
        latest_only=latest_only,
        tail_lines=tail_lines,
    )

    hits: list[LeakHit] = []
    hits.extend(collect_marker_hits(gateway_path, "gateway_log", tail_lines=tail_lines, since=since))
    hits.extend(collect_marker_hits(plugin_debug_path, "plugin_debug_log", tail_lines=tail_lines, since=since))
    session_source = "latest_main_session" if latest_only else "historical_sessions"
    for path in session_paths:
        hits.extend(collect_marker_hits(path, session_source, since=since))

    counts = {
        "gateway_log": sum(1 for hit in hits if hit.source == "gateway_log"),
        "plugin_debug_log": sum(1 for hit in hits if hit.source == "plugin_debug_log"),
        "session_hits": sum(1 for hit in hits if hit.source in {"latest_main_session", "historical_sessions"}),
    }
    counts["total"] = sum(counts.values())

    return {
        "ok": counts["total"] == 0,
        "record_date": record_date or iso_today(),
        "marker": TASK_USER_CONTENT_OPEN,
        "tail_lines": tail_lines,
        "since": since.isoformat() if since is not None else None,
        "scan_mode": "latest" if latest_only else "history",
        "targets": [asdict(target) for target in targets],
        "counts": counts,
        "hits": [asdict(hit) for hit in hits],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Task User Content Leak Check",
        "",
        f"- ok: {payload['ok']}",
        f"- scan_mode: {payload['scan_mode']}",
        f"- marker: {payload['marker']}",
        f"- record_date: {payload['record_date']}",
        f"- tail_lines: {payload['tail_lines']}",
        f"- since: {payload['since']}",
        "",
        "## Targets",
        "",
    ]
    for target in payload["targets"]:
        lines.append(
            f"- {target['name']}: {'present' if target['exists'] else 'missing'} "
            f"(scanned={target['scanned']}, tail_lines={target['tail_lines']}, path={target['path']})"
        )
    lines.extend(
        [
            "",
            "## Counts",
            "",
            f"- gateway_log: {payload['counts']['gateway_log']}",
            f"- plugin_debug_log: {payload['counts']['plugin_debug_log']}",
            f"- session_hits: {payload['counts']['session_hits']}",
            f"- total: {payload['counts']['total']}",
        ]
    )
    if payload["hits"]:
        lines.extend(["", "## Hits", ""])
        for hit in payload["hits"]:
            lines.append(
                f"- {hit['source']}:{hit['line_number']} "
                f"([{Path(hit['path']).name}]({hit['path']})): {hit['line']}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check OpenClaw logs and sessions for raw <task_user_content> leakage.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown.")
    parser.add_argument("--date", default=None, help="Date for the default gateway log path (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--gateway-log", default=None, help="Override the gateway log path.")
    parser.add_argument("--session-file", default=None, help="Override the session file path.")
    parser.add_argument("--plugin-debug-log", default=None, help="Override the plugin debug log path.")
    parser.add_argument("--tail-lines", type=int, default=400, help="Only scan the last N lines for rolling logs.")
    parser.add_argument("--all-history", action="store_true", help="Scan all agent session history instead of only the latest main session.")
    parser.add_argument("--since", default=None, help="Only count hits at or after this ISO timestamp, e.g. 2026-04-11T12:18:34+08:00.")
    args = parser.parse_args()

    since = _parse_iso_timestamp(args.since)
    if args.since and since is None:
        raise SystemExit("--since must be a valid ISO timestamp")

    payload = run_audit(
        record_date=args.date,
        gateway_log=Path(args.gateway_log).expanduser() if args.gateway_log else None,
        session_file=Path(args.session_file).expanduser() if args.session_file else None,
        plugin_debug_log=Path(args.plugin_debug_log).expanduser() if args.plugin_debug_log else None,
        tail_lines=args.tail_lines,
        latest_only=not args.all_history,
        since=since,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
