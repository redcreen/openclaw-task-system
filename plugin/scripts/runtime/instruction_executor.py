#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from argparse import ArgumentParser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from delivery_reconcile import reconcile_delivery_artifacts
from task_config import load_task_system_config, resolve_openclaw_bin
from task_state import TaskPaths, atomic_write_json, default_paths

EXECUTION_RESULT_SCHEMA = "openclaw.task-system.dispatch-result.v1"
SUPPORTED_MESSAGE_CHANNELS = {
    "telegram",
    "discord",
    "slack",
    "signal",
    "whatsapp",
    "imessage",
    "line",
    "irc",
    "googlechat",
}
RETRYABLE_ERROR_MARKERS = ("network request", "timeout", "connection", "econnreset", "etimedout")


@dataclass(frozen=True)
class DispatchDecision:
    action: str
    reason: str
    command: list[str]


def instruction_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "send-instructions"


def result_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "dispatch-results"


def processed_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "processed-instructions"


def failed_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "failed-instructions"


def resolved_failed_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "resolved-failed-instructions"


def ensure_dirs(paths: TaskPaths) -> None:
    instruction_dir(paths).mkdir(parents=True, exist_ok=True)
    result_dir(paths).mkdir(parents=True, exist_ok=True)
    processed_dir(paths).mkdir(parents=True, exist_ok=True)
    failed_dir(paths).mkdir(parents=True, exist_ok=True)
    resolved_failed_dir(paths).mkdir(parents=True, exist_ok=True)


def load_instruction(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def classify_failure(*, decision: DispatchDecision, exit_code: int, stderr: str) -> tuple[str, bool]:
    stderr_lower = stderr.lower()
    if decision.action == "skip":
        return ("skipped", False)
    if any(marker in stderr_lower for marker in RETRYABLE_ERROR_MARKERS):
        return ("transport-retryable", True)
    if "auth" in stderr_lower or "unauthorized" in stderr_lower or "forbidden" in stderr_lower:
        return ("auth", False)
    if "rate limit" in stderr_lower or "too many requests" in stderr_lower:
        return ("rate-limit", True)
    if exit_code != 0:
        return ("transport-nonretryable", False)
    return ("unknown", False)


def infer_failed_instruction_metadata(
    instruction: dict[str, Any],
    *,
    name: str,
    paths: TaskPaths,
    openclaw_bin: str = resolve_openclaw_bin(),
) -> tuple[Optional[str], Optional[bool]]:
    existing_classification = instruction.get("_last_failure_classification")
    existing_retryable = instruction.get("_last_failure_retryable")
    if existing_classification is not None and existing_retryable is not None:
        return (str(existing_classification), bool(existing_retryable))

    result_path = result_dir(paths) / name
    if not result_path.exists():
        return (None, None)

    result_payload = load_instruction(result_path)
    failure_classification = result_payload.get("failure_classification")
    retryable = result_payload.get("retryable")
    if failure_classification is not None and retryable is not None:
        return (str(failure_classification), bool(retryable))

    exit_code = result_payload.get("exit_code")
    stderr = str(result_payload.get("stderr") or "")
    if exit_code is None:
        return (None, None)

    decision = build_dispatch_decision(instruction, openclaw_bin=openclaw_bin)
    return classify_failure(
        decision=decision,
        exit_code=int(exit_code),
        stderr=stderr,
    )


def annotate_failed_instruction_metadata(
    *,
    paths: TaskPaths,
    openclaw_bin: str = resolve_openclaw_bin(),
) -> list[dict[str, Any]]:
    ensure_dirs(paths)
    updates: list[dict[str, Any]] = []
    for path in sorted(failed_dir(paths).glob("*.json")):
        instruction = load_instruction(path)
        classification, retryable = infer_failed_instruction_metadata(
            instruction,
            name=path.name,
            paths=paths,
            openclaw_bin=openclaw_bin,
        )
        if classification is None or retryable is None:
            continue
        if (
            instruction.get("_last_failure_classification") == classification
            and instruction.get("_last_failure_retryable") == retryable
        ):
            continue
        instruction["_last_failure_classification"] = classification
        instruction["_last_failure_retryable"] = retryable
        atomic_write_json(path, instruction)
        updates.append(
            {
                "name": path.name,
                "failure_classification": classification,
                "retryable": retryable,
            }
        )
    return updates


def summarize_failed_instructions(paths: TaskPaths) -> dict[str, Any]:
    ensure_dirs(paths)
    summary = {
        "total": 0,
        "retryable": 0,
        "persistent_retryable": 0,
        "non_retryable": 0,
        "unknown": 0,
        "items": [],
    }
    for path in sorted(failed_dir(paths).glob("*.json")):
        instruction = load_instruction(path)
        dispatch_result_path = result_dir(paths) / path.name
        dispatch_result = load_instruction(dispatch_result_path) if dispatch_result_path.exists() else {}
        stderr = str(dispatch_result.get("stderr") or "").strip()
        last_error_summary = stderr.splitlines()[0] if stderr else None
        classification, retryable = infer_failed_instruction_metadata(
            instruction,
            name=path.name,
            paths=paths,
        )
        if classification is None or retryable is None:
            summary["unknown"] += 1
        elif retryable:
            summary["retryable"] += 1
            if int(instruction.get("_retry_count", 0) or 0) > 0:
                summary["persistent_retryable"] += 1
        else:
            summary["non_retryable"] += 1
        summary["total"] += 1
        summary["items"].append(
            {
                "name": path.name,
                "task_id": instruction.get("task_id"),
                "channel": instruction.get("channel"),
                "chat_id": instruction.get("chat_id"),
                "retry_count": int(instruction.get("_retry_count", 0) or 0),
                "failure_classification": classification,
                "retryable": retryable,
                "last_error_summary": last_error_summary,
            }
        )
    return summary


def resolve_failed_instructions(
    *,
    paths: TaskPaths,
    task_ids: Optional[list[str]] = None,
    include_non_retryable: bool = False,
    include_persistent_retryable: bool = False,
    min_retry_count: int = 1,
    apply_changes: bool = False,
    reason: str = "manual failed instruction resolution",
) -> list[dict[str, Any]]:
    ensure_dirs(paths)
    wanted_task_ids = set(task_ids or [])
    findings: list[dict[str, Any]] = []

    for path in sorted(failed_dir(paths).glob("*.json")):
        instruction = load_instruction(path)
        task_id = str(instruction.get("task_id") or "")
        classification, retryable = infer_failed_instruction_metadata(
            instruction,
            name=path.name,
            paths=paths,
        )
        retry_count = int(instruction.get("_retry_count", 0) or 0)

        selected = False
        if wanted_task_ids and task_id in wanted_task_ids:
            selected = True
        if include_non_retryable and retryable is False:
            selected = True
        if include_persistent_retryable and retryable and retry_count >= min_retry_count:
            selected = True
        if not selected:
            continue

        entry = {
            "name": path.name,
            "task_id": task_id,
            "failure_classification": classification,
            "retryable": retryable,
            "retry_count": retry_count,
            "applied": apply_changes,
        }

        if apply_changes:
            payload = dict(instruction)
            payload["_resolved_at"] = datetime.now(timezone.utc).isoformat()
            payload["_resolved_reason"] = reason
            payload["_resolved_from"] = "failed-instructions"
            target = resolved_failed_dir(paths) / path.name
            atomic_write_json(target, payload)
            path.unlink(missing_ok=True)
            entry["resolved_path"] = str(target)

        findings.append(entry)

    return findings


def build_dispatch_decision(
    instruction: dict[str, Any],
    *,
    openclaw_bin: str = resolve_openclaw_bin(),
) -> DispatchDecision:
    channel = str(instruction.get("channel") or "").strip()
    chat_id = str(instruction.get("chat_id") or "").strip()
    message = str(instruction.get("message") or "").strip()
    account_id = str(instruction.get("account_id") or "").strip()

    if not message:
        return DispatchDecision(action="skip", reason="empty-message", command=[])
    if channel == "agent":
        return DispatchDecision(action="skip", reason="internal-agent-channel", command=[])
    if channel not in SUPPORTED_MESSAGE_CHANNELS:
        return DispatchDecision(action="skip", reason=f"unsupported-channel:{channel or 'unknown'}", command=[])
    if not chat_id:
        return DispatchDecision(action="skip", reason="missing-chat-id", command=[])

    command = [
        openclaw_bin,
        "message",
        "send",
        "--channel",
        channel,
    ]
    if account_id:
        command.extend(["--account", account_id])
    command.extend(["--target", chat_id, "--message", message])
    return DispatchDecision(action="send", reason="supported", command=command)


def write_dispatch_result(
    instruction: dict[str, Any],
    decision: DispatchDecision,
    *,
    name: str,
    paths: TaskPaths,
    executed: bool,
    execution_context: str,
    requested_execution_context: Optional[str] = None,
    exit_code: Optional[int] = None,
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
    failure_classification: Optional[str] = None,
    retryable: Optional[bool] = None,
) -> Path:
    ensure_dirs(paths)
    payload = {
        "schema": EXECUTION_RESULT_SCHEMA,
        "task_id": instruction.get("task_id"),
        "agent_id": instruction.get("agent_id"),
        "session_key": instruction.get("session_key"),
        "channel": instruction.get("channel"),
        "account_id": instruction.get("account_id"),
        "chat_id": instruction.get("chat_id"),
        "message": instruction.get("message"),
        "action": decision.action,
        "reason": decision.reason,
        "execution_context": execution_context,
        "requested_execution_context": requested_execution_context or execution_context,
        "command": decision.command,
        "executed": executed,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "failure_classification": failure_classification,
        "retryable": retryable,
    }
    out = result_dir(paths) / name
    atomic_write_json(out, payload)
    return out


def archive_instruction(
    source: Path,
    *,
    name: str,
    paths: TaskPaths,
    succeeded: bool,
    payload: Optional[dict[str, Any]] = None,
) -> Path:
    ensure_dirs(paths)
    target_dir = processed_dir(paths) if succeeded else failed_dir(paths)
    target = target_dir / name
    archived_payload = payload or load_instruction(source)
    atomic_write_json(target, archived_payload)
    source.unlink(missing_ok=True)
    task_id = str(archived_payload.get("task_id") or "").strip()
    if task_id:
        reconcile_delivery_artifacts(paths=paths, apply_changes=True, task_ids=[task_id])
    return target


def execute_instruction(
    instruction: dict[str, Any],
    *,
    name: str,
    source_path: Optional[Path],
    paths: TaskPaths,
    execute: bool = False,
    openclaw_bin: str = resolve_openclaw_bin(),
    max_retries: int = 2,
    retry_delay_seconds: float = 1.0,
    execution_context: str = "local",
) -> dict[str, Any]:
    import time

    decision = build_dispatch_decision(instruction, openclaw_bin=openclaw_bin)
    if not execute:
        result_execution_context = "dry-run" if not execute else execution_context
        result_path = write_dispatch_result(
            instruction,
            decision,
            name=name,
            paths=paths,
            executed=False,
            execution_context=result_execution_context,
            requested_execution_context=execution_context,
            failure_classification=None,
            retryable=None,
        )
        return {
            "decision": decision.__dict__,
            "result_path": str(result_path),
            "execution_context": result_execution_context,
            "requested_execution_context": execution_context,
        }

    if decision.action != "send":
        result_path = write_dispatch_result(
            instruction,
            decision,
            name=name,
            paths=paths,
            executed=False,
            execution_context=execution_context,
            requested_execution_context=execution_context,
            failure_classification=None,
            retryable=False,
        )
        archived_instruction_path: Optional[str] = None
        if source_path is not None:
            archived_path = archive_instruction(
                source_path,
                name=name,
                paths=paths,
                succeeded=True,
                payload=instruction,
            )
            archived_instruction_path = str(archived_path)
        return {
            "decision": decision.__dict__,
            "result_path": str(result_path),
            "archived_instruction_path": archived_instruction_path,
            "execution_context": execution_context,
            "requested_execution_context": execution_context,
        }

    archived_instruction_path: Optional[str] = None
    last_exit_code = -1
    last_stdout = ""
    last_stderr = ""
    attempt = 0

    while attempt <= max_retries:
        if attempt > 0:
            time.sleep(retry_delay_seconds * attempt)  # Exponential backoff

        completed = subprocess.run(decision.command, capture_output=True, text=True, check=False)
        last_exit_code = completed.returncode
        last_stdout = completed.stdout
        last_stderr = completed.stderr

        # Success case
        if completed.returncode == 0:
            break

        # Check if it's a retryable network error
        stderr_lower = completed.stderr.lower()
        is_network_error = any(err in stderr_lower for err in RETRYABLE_ERROR_MARKERS)

        if not is_network_error:
            break  # Non-retryable error, exit loop

        attempt += 1
        if attempt <= max_retries:
            last_stderr = f"[Retry {attempt}/{max_retries}] {last_stderr}"

    failure_classification = None
    retryable = None
    if last_exit_code != 0:
        failure_classification, retryable = classify_failure(
            decision=decision,
            exit_code=last_exit_code,
            stderr=last_stderr,
        )

    result_path = write_dispatch_result(
        instruction,
        decision,
        name=name,
        paths=paths,
        executed=True,
        execution_context=execution_context,
        requested_execution_context=execution_context,
        exit_code=last_exit_code,
        stdout=last_stdout,
        stderr=last_stderr,
        failure_classification=failure_classification,
        retryable=retryable,
    )
    if source_path is not None:
        archived_payload = dict(instruction)
        archived_payload["_archived_from"] = "send-instructions"
        archived_payload["_last_execution_context"] = execution_context
        archived_payload["_retry_count"] = int(instruction.get("_retry_count", 0))
        if last_exit_code != 0:
            archived_payload["_last_failure_classification"] = failure_classification
            archived_payload["_last_failure_retryable"] = retryable
        archived_path = archive_instruction(
            source_path,
            name=name,
            paths=paths,
            succeeded=(decision.action == "skip" or last_exit_code == 0),
            payload=archived_payload,
        )
        archived_instruction_path = str(archived_path)
    return {
        "decision": decision.__dict__,
        "result_path": str(result_path),
        "exit_code": last_exit_code,
        "archived_instruction_path": archived_instruction_path,
        "retries": attempt,
        "execution_context": execution_context,
        "requested_execution_context": execution_context,
        "failure_classification": failure_classification,
        "retryable": retryable,
    }


def execute_all(
    *,
    paths: Optional[TaskPaths] = None,
    execute: bool = False,
    openclaw_bin: str = resolve_openclaw_bin(),
    retry_failed: bool = False,
    execution_context: str = "local",
) -> list[dict[str, Any]]:
    resolved_paths = paths or default_paths()
    ensure_dirs(resolved_paths)
    results: list[dict[str, Any]] = []

    # Process new instructions
    for path in sorted(instruction_dir(resolved_paths).glob("*.json")):
        instruction = load_instruction(path)
        result = execute_instruction(
            instruction,
            name=path.name,
            source_path=path,
            paths=resolved_paths,
            execute=execute,
            openclaw_bin=openclaw_bin,
            execution_context=execution_context,
        )
        results.append(result)

    # Retry failed instructions (only when execute=True and retry_failed=True)
    if execute and retry_failed:
        failed_results = retry_failed_instructions(
            paths=resolved_paths,
            openclaw_bin=openclaw_bin,
            execution_context=execution_context,
        )
        results.extend(failed_results)

    return results


def retry_failed_instructions(
    *,
    paths: TaskPaths,
    openclaw_bin: str = resolve_openclaw_bin(),
    max_age_hours: int = 24,
    execution_context: str = "local",
) -> list[dict[str, Any]]:
    """Retry failed instructions that are younger than max_age_hours."""
    import time

    results: list[dict[str, Any]] = []
    ensure_dirs(paths)
    annotate_failed_instruction_metadata(paths=paths, openclaw_bin=openclaw_bin)
    failed_dir_path = failed_dir(paths)

    if not failed_dir_path.exists():
        return results

    now = time.time()
    max_age_seconds = max_age_hours * 3600

    for path in sorted(failed_dir_path.glob("*.json")):
        # Check if file is too old
        stat = path.stat()
        if now - stat.st_mtime > max_age_seconds:
            continue

        # Move back to instruction dir for retry
        instruction = load_instruction(path)
        if not instruction.get("_last_failure_retryable", True):
            results.append(
                {
                    "name": path.name,
                    "retry_from_failed": True,
                    "skipped_retry": True,
                    "reason": "non-retryable-failure",
                }
            )
            continue
        target_path = instruction_dir(paths) / path.name

        try:
            instruction["_retry_count"] = int(instruction.get("_retry_count", 0)) + 1
            path.replace(target_path)
            atomic_write_json(target_path, instruction)
            result = execute_instruction(
                instruction,
                name=path.name,
                source_path=target_path,
                paths=paths,
                execute=True,
                openclaw_bin=openclaw_bin,
                execution_context=execution_context,
            )
            result["retry_from_failed"] = True
            results.append(result)
        except Exception as e:
            # If move fails, log but don't crash
            results.append({
                "error": str(e),
                "name": path.name,
                "retry_from_failed": True,
            })

    return results


if __name__ == "__main__":
    parser = ArgumentParser(description="Execute or dry-run send instructions.")
    parser.add_argument("--execute", action="store_true", help="Run real openclaw message send commands.")
    parser.add_argument("--config", help="Task system config path.")
    parser.add_argument("--openclaw-bin", help="Override openclaw binary path.")
    parser.add_argument(
        "--execution-context",
        help="Label written into dispatch-results, e.g. dry-run/local/host.",
    )
    args = parser.parse_args()

    config = load_task_system_config(config_path=Path(args.config).expanduser() if args.config else None)
    execution_context = args.execution_context or os.environ.get("OPENCLAW_TASK_SYSTEM_EXECUTION_CONTEXT") or "local"
    print(
        json.dumps(
            execute_all(
                paths=config.build_paths(),
                execute=args.execute,
                openclaw_bin=args.openclaw_bin or config.delivery.openclaw_bin,
                execution_context=execution_context,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
