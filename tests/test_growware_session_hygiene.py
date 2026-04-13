from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.runtime_loader import load_runtime_module, task_state_module


growware_session_hygiene = load_runtime_module("growware_session_hygiene")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _prepare_project(root: Path) -> None:
    _write_json(
        root / ".growware" / "project.json",
        {
            "projectRoot": str(root),
            "growware": {
                "daemon": {
                    "agentId": "growware",
                    "workspace": str(root),
                    "agentDir": str(root / ".agent"),
                }
            },
        },
    )
    _write_json(
        root / ".growware" / "channels.json",
        {
            "feedbackChannel": {
                "provider": "feishu",
                "accountId": "feishu6-chat",
                "roles": ["feedback", "approval", "notification"],
            }
        },
    )


def _write_session_store(root: Path, session_key: str, session_id: str) -> Path:
    sessions_dir = root / ".openclaw" / "agents" / "growware" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    session_file = sessions_dir / f"{session_id}.jsonl"
    session_file.write_text(
        json.dumps({"type": "session", "version": 1, "id": session_id}) + "\n"
        + json.dumps({"type": "message", "message": {"role": "user", "content": [{"type": "text", "text": "hello"}]}})
        + "\n"
        + json.dumps(
            {
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "toolCall", "name": "exec", "arguments": {"command": "pytest"}}],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    store_path = sessions_dir / "sessions.json"
    _write_json(
        store_path,
        {
            session_key: {
                "sessionId": session_id,
                "sessionFile": str(session_file),
                "updatedAt": 1,
                "status": "running",
                "systemSent": True,
                "abortedLastRun": False,
                "deliveryContext": {"channel": "feishu", "accountId": "feishu6-chat"},
                "origin": {"provider": "feishu"},
                "model": "gpt-5.4",
                "modelProvider": "openai-codex",
            }
        },
    )
    return store_path


class GrowwareSessionHygieneTests(unittest.TestCase):
    def test_build_session_report_reads_transcript_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _prepare_project(root)
            session_key = "agent:growware:feishu:direct:ou_test"
            store_path = _write_session_store(root, session_key, "session-old")

            report = growware_session_hygiene.build_session_report(
                session_key,
                project_root=root,
                session_store_path=store_path,
            )

        self.assertTrue(report["ok"])
        self.assertEqual(report["sessionId"], "session-old")
        self.assertEqual(report["transcript"]["messageCount"], 2)
        self.assertEqual(report["transcript"]["toolCallCount"], 1)

    def test_reset_session_rotates_transcript_and_fails_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _prepare_project(root)
            session_key = "agent:growware:feishu:direct:ou_test"
            store_path = _write_session_store(root, session_key, "session-old")

            paths = task_state_module.TaskPaths.from_root(root, root / "data")
            store = task_state_module.TaskStore(paths=paths)
            task = store.register_task(
                agent_id="growware",
                session_key=session_key,
                channel="feishu",
                account_id="feishu6-chat",
                chat_id="ou_test",
                task_label="fix the message",
            )
            store.start_task(task.task_id)

            result = growware_session_hygiene.reset_session(
                session_key,
                project_root=root,
                session_store_path=store_path,
                task_data_dir=paths.data_dir,
                fail_task_id=task.task_id,
                failure_reason="session-polluted",
                restart_gateway=False,
            )

            store_payload = json.loads(store_path.read_text(encoding="utf-8"))
            archived_task = store.load_task(task.task_id, allow_archive=True)

            self.assertTrue(result["ok"])
            self.assertNotEqual(result["previousSessionId"], result["nextSessionId"])
            self.assertTrue(Path(result["nextSessionFile"]).exists())
            self.assertTrue(Path(result["archivedTranscript"]).exists())
            self.assertEqual(store_payload[session_key]["sessionId"], result["nextSessionId"])
            self.assertFalse(store_payload[session_key]["systemSent"])
            self.assertEqual(archived_task.status, task_state_module.STATUS_FAILED)
            self.assertEqual(archived_task.failure_reason, "session-polluted")


if __name__ == "__main__":
    unittest.main()
