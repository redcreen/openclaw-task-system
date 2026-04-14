#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from growware_project import load_project_definition, resolve_project_root
from task_state import TaskPaths, TaskStore, default_paths


SESSION_HEADER_VERSION = 1


@dataclass(frozen=True)
class SessionStorePaths:
    store_path: Path
    sessions_dir: Path
    archive_dir: Path


def _now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).astimezone().isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_session_store_paths(
    project_root: Path | None = None,
    *,
    session_store_path: Path | None = None,
) -> SessionStorePaths:
    if session_store_path is not None:
        resolved = session_store_path.expanduser().resolve()
        sessions_dir = resolved.parent
        return SessionStorePaths(store_path=resolved, sessions_dir=sessions_dir, archive_dir=sessions_dir / "archive")

    project = load_project_definition(project_root)
    daemon = ((project.get("growware") or {}).get("daemon") or {})
    agent_id = str(daemon.get("agentId") or "growware").strip() or "growware"
    sessions_dir = Path.home() / ".openclaw" / "agents" / agent_id / "sessions"
    return SessionStorePaths(
        store_path=(sessions_dir / "sessions.json").resolve(),
        sessions_dir=sessions_dir.resolve(),
        archive_dir=(sessions_dir / "archive").resolve(),
    )


def resolve_runtime_task_paths(
    project_root: Path | None = None,
    *,
    task_data_dir: Path | None = None,
) -> TaskPaths:
    root = resolve_project_root(project_root)
    if task_data_dir is not None:
        return TaskPaths.from_root(root, data_dir=task_data_dir.expanduser().resolve())

    project = load_project_definition(root)
    project_id = str(project.get("projectId") or "").strip() or root.name
    installed_root = (Path.home() / ".openclaw" / "extensions" / project_id).resolve()
    installed_data_dir = installed_root / "data"
    if (installed_data_dir / "tasks").exists():
        return TaskPaths.from_root(installed_root, data_dir=installed_data_dir)
    return default_paths()


def _load_transcript_lines(path: Optional[Path]) -> list[str]:
    if path is None or not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="ignore").splitlines()


def _count_transcript_activity(lines: list[str]) -> dict[str, int]:
    message_count = 0
    tool_call_count = 0
    tool_result_count = 0
    assistant_count = 0
    user_count = 0
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("type") != "message":
            continue
        message_count += 1
        message = payload.get("message") or {}
        role = str(message.get("role") or "").strip()
        if role == "assistant":
            assistant_count += 1
        elif role == "user":
            user_count += 1
        for item in message.get("content") or []:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("type") or "").strip()
            if kind == "toolCall":
                tool_call_count += 1
            elif role == "toolResult" or kind == "toolResult":
                tool_result_count += 1
    return {
        "messageCount": message_count,
        "assistantMessageCount": assistant_count,
        "userMessageCount": user_count,
        "toolCallCount": tool_call_count,
        "toolResultCount": tool_result_count,
    }


def build_session_report(
    session_key: str,
    *,
    project_root: Path | None = None,
    session_store_path: Path | None = None,
    task_data_dir: Path | None = None,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    paths = resolve_session_store_paths(root, session_store_path=session_store_path)
    store = _load_json(paths.store_path) if paths.store_path.exists() else {}
    entry = store.get(session_key)
    if not isinstance(entry, dict):
        return {
            "ok": False,
            "projectRoot": str(root),
            "sessionStorePath": str(paths.store_path),
            "sessionKey": session_key,
            "exists": False,
        }

    transcript_path = Path(str(entry.get("sessionFile") or "")).expanduser().resolve() if entry.get("sessionFile") else None
    transcript_lines = _load_transcript_lines(transcript_path)
    counts = _count_transcript_activity(transcript_lines)
    active_task_ids: list[str] = []
    if paths.store_path.exists():
        task_store = TaskStore(paths=resolve_runtime_task_paths(root, task_data_dir=task_data_dir))
        try:
            for task_path in task_store.list_inflight():
                task = task_store.load_task(task_path.stem, allow_archive=False)
                if str(task.session_key or "").strip() != session_key:
                    continue
                if str(task.status or "").strip() in {"done", "failed", "cancelled"}:
                    continue
                active_task_ids.append(task.task_id)
        except Exception:
            active_task_ids = []

    return {
        "ok": True,
        "projectRoot": str(root),
        "sessionStorePath": str(paths.store_path),
        "sessionKey": session_key,
        "exists": True,
        "sessionId": entry.get("sessionId"),
        "sessionFile": str(transcript_path) if transcript_path else None,
        "status": entry.get("status"),
        "systemSent": bool(entry.get("systemSent")),
        "abortedLastRun": bool(entry.get("abortedLastRun")),
        "updatedAt": entry.get("updatedAt"),
        "deliveryContext": entry.get("deliveryContext"),
        "origin": entry.get("origin"),
        "transcript": counts,
        "activeTaskIds": active_task_ids,
    }


def _build_reset_entry(entry: dict[str, Any], *, next_session_id: str, next_session_file: Path) -> dict[str, Any]:
    preserved_fields = [
        "thinkingLevel",
        "fastMode",
        "verboseLevel",
        "reasoningLevel",
        "elevatedLevel",
        "ttsAuto",
        "execHost",
        "execSecurity",
        "execAsk",
        "execNode",
        "responseUsage",
        "providerOverride",
        "modelOverride",
        "authProfileOverride",
        "authProfileOverrideSource",
        "authProfileOverrideCompactionCount",
        "groupActivation",
        "groupActivationNeedsSystemIntro",
        "chatType",
        "sendPolicy",
        "queueMode",
        "queueDebounceMs",
        "queueCap",
        "queueDrop",
        "spawnedBy",
        "spawnedWorkspaceDir",
        "parentSessionKey",
        "forkedFromParent",
        "spawnDepth",
        "subagentRole",
        "subagentControlScope",
        "label",
        "displayName",
        "channel",
        "groupId",
        "subject",
        "groupChannel",
        "space",
        "deliveryContext",
        "cliSessionBindings",
        "cliSessionIds",
        "claudeCliSessionId",
        "lastChannel",
        "lastTo",
        "lastAccountId",
        "lastThreadId",
        "skillsSnapshot",
        "acp",
        "origin",
        "contextTokens",
        "model",
        "modelProvider",
        "compactionCount",
    ]
    next_entry = {
        "sessionId": next_session_id,
        "sessionFile": str(next_session_file),
        "updatedAt": _now_ms(),
        "systemSent": False,
        "abortedLastRun": False,
        "inputTokens": 0,
        "outputTokens": 0,
        "totalTokens": 0,
        "totalTokensFresh": True,
    }
    for field in preserved_fields:
        if field in entry:
            next_entry[field] = entry[field]
    return next_entry


def _write_session_header(path: Path, *, cwd: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = {
        "type": "session",
        "version": SESSION_HEADER_VERSION,
        "id": path.stem,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "cwd": str(cwd),
    }
    path.write_text(json.dumps(header, ensure_ascii=False) + "\n", encoding="utf-8")


def reset_session(
    session_key: str,
    *,
    project_root: Path | None = None,
    session_store_path: Path | None = None,
    task_data_dir: Path | None = None,
    fail_task_id: str | None = None,
    failure_reason: str = "session-hygiene-reset",
    restart_gateway: bool = False,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    paths = resolve_session_store_paths(root, session_store_path=session_store_path)
    store = _load_json(paths.store_path)
    entry = store.get(session_key)
    if not isinstance(entry, dict):
        raise KeyError(f"missing session key: {session_key}")

    old_session_id = str(entry.get("sessionId") or "").strip()
    old_session_file = Path(str(entry.get("sessionFile") or "")).expanduser() if entry.get("sessionFile") else None
    next_session_id = str(uuid.uuid4())
    next_session_file = (paths.sessions_dir / f"{next_session_id}.jsonl").resolve()

    archived_transcript = None
    if old_session_file and old_session_file.exists():
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        paths.archive_dir.mkdir(parents=True, exist_ok=True)
        archived_transcript = paths.archive_dir / f"{old_session_id or old_session_file.stem}.reset-{timestamp}.jsonl"
        shutil.move(str(old_session_file), str(archived_transcript))

    store[session_key] = _build_reset_entry(entry, next_session_id=next_session_id, next_session_file=next_session_file)
    _write_json(paths.store_path, store)
    _write_session_header(next_session_file, cwd=root)

    failed_task = None
    if fail_task_id:
        task_store = TaskStore(paths=resolve_runtime_task_paths(root, task_data_dir=task_data_dir))
        failed = task_store.fail_task(
            fail_task_id,
            failure_reason,
            archive=True,
            meta={
                "session_hygiene_reset_at": _now_iso(),
                "session_hygiene_reset_session_key": session_key,
                "session_hygiene_reset_previous_session_id": old_session_id or None,
                "execution_source": "daemon-owned",
            },
        )
        failed_task = failed.to_dict()

    restart_payload = None
    if restart_gateway:
        import subprocess

        result = subprocess.run(
            ["openclaw", "gateway", "restart", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
        restart_payload = {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }

    return {
        "ok": True,
        "projectRoot": str(root),
        "sessionKey": session_key,
        "sessionStorePath": str(paths.store_path),
        "previousSessionId": old_session_id or None,
        "nextSessionId": next_session_id,
        "nextSessionFile": str(next_session_file),
        "archivedTranscript": str(archived_transcript) if archived_transcript else None,
        "failedTask": failed_task,
        "restart": restart_payload,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect or repair Growware production session hygiene.")
    parser.add_argument("--project-root", type=Path, default=resolve_project_root())
    parser.add_argument("--session-key", required=True)
    parser.add_argument("--session-store-path", type=Path, default=None)
    parser.add_argument("--task-data-dir", type=Path, default=None)
    parser.add_argument("--fail-task-id", default=None)
    parser.add_argument("--failure-reason", default="session-hygiene-reset")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def render_report(payload: dict[str, Any]) -> str:
    lines = ["# Growware Session Hygiene", ""]
    for key in (
        "ok",
        "projectRoot",
        "sessionStorePath",
        "sessionKey",
        "exists",
        "sessionId",
        "status",
        "systemSent",
        "abortedLastRun",
        "sessionFile",
    ):
        if key in payload:
            lines.append(f"- {key}: {payload[key]}")
    transcript = payload.get("transcript")
    if isinstance(transcript, dict):
        lines.append("- transcript:")
        for name, value in transcript.items():
            lines.append(f"  - {name}: {value}")
    active_task_ids = payload.get("activeTaskIds")
    if isinstance(active_task_ids, list):
        lines.append(f"- activeTaskIds: {active_task_ids}")
    return "\n".join(lines) + "\n"


def render_reset(payload: dict[str, Any]) -> str:
    lines = ["# Growware Session Reset", ""]
    for key in (
        "ok",
        "projectRoot",
        "sessionKey",
        "previousSessionId",
        "nextSessionId",
        "nextSessionFile",
        "archivedTranscript",
    ):
        lines.append(f"- {key}: {payload.get(key)}")
    failed_task = payload.get("failedTask")
    if isinstance(failed_task, dict):
        lines.append(f"- failedTaskId: {failed_task.get('task_id')}")
        lines.append(f"- failedTaskStatus: {failed_task.get('status')}")
    restart = payload.get("restart")
    if isinstance(restart, dict):
        lines.append(f"- restartReturnCode: {restart.get('returncode')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    if args.reset:
        payload = reset_session(
            args.session_key,
            project_root=args.project_root,
            session_store_path=args.session_store_path,
            task_data_dir=args.task_data_dir,
            fail_task_id=args.fail_task_id,
            failure_reason=args.failure_reason,
            restart_gateway=args.restart,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(render_reset(payload), end="")
        return 0

    payload = build_session_report(
        args.session_key,
        project_root=args.project_root,
        session_store_path=args.session_store_path,
        task_data_dir=args.task_data_dir,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_report(payload), end="")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
