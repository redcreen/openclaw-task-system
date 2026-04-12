#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from openclaw_hooks import claim_due_collecting_windows_from_payload, register_from_payload
from session_state import SessionStateStore
from task_state import TaskPaths, TaskStore


@dataclass(frozen=True)
class SameSessionAcceptanceStep:
    step: str
    ok: bool
    detail: str


def _write_config(path: Path, data_dir: Path, classifier_command: list[str]) -> None:
    path.write_text(
        json.dumps(
            {
                "taskSystem": {
                    "storageDir": str(data_dir),
                    "agents": {
                        "main": {
                            "sameSessionRouting": {
                                "collectingWindowSeconds": 5,
                                "classifier": {
                                    "enabled": True,
                                    "command": classifier_command,
                                    "timeoutMs": 1000,
                                    "minConfidence": 0.75,
                                },
                            }
                        }
                    },
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _set_env(config_path: Path) -> str | None:
    previous = os.environ.get("OPENCLAW_TASK_SYSTEM_CONFIG")
    os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = str(config_path)
    return previous


def _restore_env(previous: str | None) -> None:
    if previous is None:
        os.environ.pop("OPENCLAW_TASK_SYSTEM_CONFIG", None)
    else:
        os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = previous


def run_same_session_routing_acceptance() -> dict[str, Any]:
    temp_dir = Path(tempfile.mkdtemp(prefix="task-system-same-session-acceptance."))
    data_dir = temp_dir / "data"
    config_path = temp_dir / "task_system.json"
    classifier_script = temp_dir / "same_session_classifier.py"
    classifier_script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import sys",
                "payload = json.load(sys.stdin)",
                "message = str(payload.get('new_message') or '')",
                "if 'another version' in message.lower():",
                "    print(json.dumps({'classification': 'queueing', 'confidence': 0.91, 'needs_confirmation': False, 'reason_code': 'acceptance-independent-followup', 'reason_text': 'Acceptance classifier treated the follow-up as a separate goal.'}, ensure_ascii=False))",
                "else:",
                "    print(json.dumps({'classification': 'steering', 'confidence': 0.91, 'needs_confirmation': False, 'reason_code': 'acceptance-active-task-clarification', 'reason_text': 'Acceptance classifier treated the follow-up as a refinement.'}, ensure_ascii=False))",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    _write_config(config_path, data_dir, [sys.executable, str(classifier_script)])
    previous_env = _set_env(config_path)
    steps: list[SameSessionAcceptanceStep] = []
    try:
        register_from_payload(
            {
                "agent_id": "steering-prestart-agent",
                "session_key": "session:acceptance:steering-prestart:blocker",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:steering-prestart:blocker",
                "user_id": "ou_acceptance",
                "user_request": "Block the agent with another long task",
                "estimated_steps": 4,
            },
            config_path=config_path,
        )
        steering_first = register_from_payload(
            {
                "agent_id": "steering-prestart-agent",
                "session_key": "session:acceptance:steering-prestart",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:steering-prestart",
                "user_id": "ou_acceptance",
                "user_request": "Help me rewrite this resume",
                "estimated_steps": 4,
            },
            config_path=config_path,
        )
        steering_second = register_from_payload(
            {
                "agent_id": "steering-prestart-agent",
                "session_key": "session:acceptance:steering-prestart",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:steering-prestart",
                "user_id": "ou_acceptance",
                "user_request": "Also make it more conversational",
            },
            config_path=config_path,
        )
        steps.append(
            SameSessionAcceptanceStep(
                step="same-session-steering-prestart",
                ok=steering_second.get("routing_decision", {}).get("execution_decision") == "merge-before-start",
                detail=json.dumps(
                    {"first": steering_first, "second": steering_second},
                    ensure_ascii=False,
                ),
            )
        )

        running_first = register_from_payload(
            {
                "agent_id": "steering-running-agent",
                "session_key": "session:acceptance:steering-running",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:steering-running",
                "user_id": "ou_acceptance",
                "user_request": "Help me rewrite this resume",
                "estimated_steps": 4,
            },
            config_path=config_path,
        )
        running_second = register_from_payload(
            {
                "agent_id": "steering-running-agent",
                "session_key": "session:acceptance:steering-running",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:steering-running",
                "user_id": "ou_acceptance",
                "user_request": "Also make it more conversational",
                "observe_only": True,
            },
            config_path=config_path,
        )
        steps.append(
            SameSessionAcceptanceStep(
                step="same-session-steering-safe-restart",
                ok=running_second.get("routing_decision", {}).get("execution_decision") == "interrupt-and-restart",
                detail=json.dumps(
                    {"first": running_first, "second": running_second},
                    ensure_ascii=False,
                ),
            )
        )

        queue_first = register_from_payload(
            {
                "agent_id": "queueing-agent",
                "session_key": "session:acceptance:queueing",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:queueing",
                "user_id": "ou_acceptance",
                "user_request": "Please rewrite this resume",
                "estimated_steps": 4,
            },
            config_path=config_path,
        )
        queue_second = register_from_payload(
            {
                "agent_id": "queueing-agent",
                "session_key": "session:acceptance:queueing",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:queueing",
                "user_id": "ou_acceptance",
                "user_request": "Also check Hangzhou weather",
                "observe_only": True,
            },
            config_path=config_path,
        )
        control_plane = register_from_payload(
            {
                "agent_id": "queueing-agent",
                "session_key": "session:acceptance:queueing",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:queueing",
                "user_id": "ou_acceptance",
                "user_request": "/status",
            },
            config_path=config_path,
        )
        steps.append(
            SameSessionAcceptanceStep(
                step="same-session-queueing-and-control-plane",
                ok=queue_second.get("routing_decision", {}).get("classification") == "queueing"
                and control_plane.get("routing_decision", {}).get("classification") == "control-plane",
                detail=json.dumps(
                    {"first": queue_first, "queue_second": queue_second, "control_plane": control_plane},
                    ensure_ascii=False,
                ),
            )
        )

        stale_observed_first = register_from_payload(
            {
                "agent_id": "stale-observed-agent",
                "session_key": "session:acceptance:stale-observed",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:stale-observed",
                "user_id": "ou_acceptance",
                "user_request": "在么",
                "observe_only": True,
            },
            config_path=config_path,
        )
        stale_observed_second = register_from_payload(
            {
                "agent_id": "stale-observed-agent",
                "session_key": "session:acceptance:stale-observed",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:stale-observed",
                "user_id": "ou_acceptance",
                "user_request": "帮我写一份简历，自己看情况写",
                "observe_only": True,
            },
            config_path=config_path,
        )
        steps.append(
            SameSessionAcceptanceStep(
                step="same-session-stale-observed-takeover",
                ok=stale_observed_second.get("task_id") == stale_observed_first.get("task_id")
                and stale_observed_second.get("routing_decision", {}).get("execution_decision") == "merge-before-start"
                and stale_observed_second.get("routing_decision", {}).get("reason_code") == "stale-observed-task-takeover",
                detail=json.dumps(
                    {"first": stale_observed_first, "second": stale_observed_second},
                    ensure_ascii=False,
                ),
            )
        )

        classifier_first = register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:acceptance:classifier",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:classifier",
                "user_id": "ou_acceptance",
                "user_request": "Please rewrite this resume",
                "estimated_steps": 4,
            },
            config_path=config_path,
        )
        classifier_second = register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:acceptance:classifier",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:classifier",
                "user_id": "ou_acceptance",
                "user_request": "Give me another version",
                "observe_only": True,
            },
            config_path=config_path,
        )
        steps.append(
            SameSessionAcceptanceStep(
                step="same-session-classifier-trigger",
                ok=bool(classifier_second.get("routing_decision", {}).get("classifier_invoked"))
                and classifier_second.get("routing_decision", {}).get("decision_source") == "classifier",
                detail=json.dumps(
                    {"first": classifier_first, "second": classifier_second},
                    ensure_ascii=False,
                ),
            )
        )

        collect_activation = register_from_payload(
            {
                "agent_id": "collecting-agent",
                "session_key": "session:acceptance:collecting",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:collecting",
                "user_id": "ou_acceptance",
                "user_request": "I'm going to send three messages, don't start yet",
            },
            config_path=config_path,
        )
        register_from_payload(
            {
                "agent_id": "collecting-agent",
                "session_key": "session:acceptance:collecting",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:collecting",
                "user_id": "ou_acceptance",
                "user_request": "First: organize the directory",
            },
            config_path=config_path,
        )
        register_from_payload(
            {
                "agent_id": "collecting-agent",
                "session_key": "session:acceptance:collecting",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:acceptance:collecting",
                "user_id": "ou_acceptance",
                "user_request": "Second: update the README",
            },
            config_path=config_path,
        )
        session_store = SessionStateStore(paths=TaskPaths.from_root(temp_dir, data_dir))
        state = session_store.load("session:acceptance:collecting") or {}
        collecting = state.get("same_session_collecting") if isinstance(state.get("same_session_collecting"), dict) else {}
        collecting["expires_at"] = (datetime.now(timezone.utc).astimezone() - timedelta(seconds=1)).isoformat()
        state["same_session_collecting"] = collecting
        session_store.save(state)
        collect_claim = claim_due_collecting_windows_from_payload({}, config_path=config_path)
        store = TaskStore(paths=TaskPaths.from_root(temp_dir, data_dir))
        materialized_task = None
        if collect_claim.get("tasks"):
            task_id = str(collect_claim["tasks"][0].get("task_id") or "")
            materialized_task = store.load_task(task_id, allow_archive=False).to_dict() if task_id else None
        steps.append(
            SameSessionAcceptanceStep(
                step="same-session-collecting-window",
                ok=collect_activation.get("routing_decision", {}).get("execution_decision") == "enter-collecting-window"
                and collect_claim.get("claimed_count") == 1,
                detail=json.dumps(
                    {
                        "activation": collect_activation,
                        "claim": collect_claim,
                        "materialized_task": materialized_task,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        return {
            "ok": all(step.ok for step in steps),
            "steps": [asdict(step) for step in steps],
            "tempDir": str(temp_dir),
            "configPath": str(config_path),
            "dataDir": str(data_dir),
        }
    finally:
        _restore_env(previous_env)
        shutil.rmtree(temp_dir, ignore_errors=True)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Same-Session Routing Acceptance", "", f"- ok: {payload['ok']}"]
    for step in payload["steps"]:
        lines.append(f"- {step['step']}: {'ok' if step['ok'] else 'failed'}")
        lines.append(f"  detail: {step['detail']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    payload = run_same_session_routing_acceptance()
    if sys.argv[1:] and sys.argv[1] == "--json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
