from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module


session_latency_audit = load_runtime_module("session_latency_audit")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


class SessionLatencyAuditTests(unittest.TestCase):
    def test_build_session_latency_audit_breaks_down_llm_and_tool_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            session_path = root / "session.jsonl"
            _write_jsonl(
                session_path,
                [
                    {"type": "session", "version": 3, "id": "sess-1", "timestamp": "2026-04-15T15:45:51.000Z", "cwd": "/"},
                    {
                        "type": "message",
                        "id": "u1",
                        "timestamp": "2026-04-15T15:45:52.000Z",
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "A new session was started via /new or /reset. hello"}],
                        },
                    },
                    {
                        "type": "message",
                        "id": "a1",
                        "timestamp": "2026-04-15T15:46:02.000Z",
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "toolCall", "name": "read", "arguments": {"path": "/tmp/SOUL.md"}}],
                            "usage": {"input": 100, "output": 10, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 110, "cost": {"total": 0.1}},
                            "stopReason": "toolUse",
                        },
                    },
                    {
                        "type": "message",
                        "id": "tr1",
                        "timestamp": "2026-04-15T15:46:04.000Z",
                        "message": {
                            "role": "toolResult",
                            "toolName": "read",
                            "content": [{"type": "text", "text": "SOUL CONTENT"}],
                        },
                    },
                    {
                        "type": "message",
                        "id": "a2",
                        "timestamp": "2026-04-15T15:46:10.000Z",
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "我在线。"}],
                            "usage": {"input": 30, "output": 5, "cacheRead": 20, "cacheWrite": 0, "totalTokens": 55, "cost": {"total": 0.02}},
                            "stopReason": "stop",
                        },
                    },
                    {
                        "type": "message",
                        "id": "u2",
                        "timestamp": "2026-04-15T15:46:15.000Z",
                        "message": {
                            "role": "user",
                            "content": [{"type": "text", "text": "wrapper data\n\n我是谁"}],
                        },
                    },
                    {
                        "type": "message",
                        "id": "a3",
                        "timestamp": "2026-04-15T15:46:27.000Z",
                        "message": {
                            "role": "assistant",
                            "content": [{"type": "text", "text": "你是刘超。"}],
                            "usage": {"input": 200, "output": 8, "cacheRead": 50, "cacheWrite": 0, "totalTokens": 258, "cost": {"total": 0.03}},
                            "stopReason": "stop",
                        },
                    },
                ],
            )
            metadata = {
                "sessionId": "sess-1",
                "modelProvider": "openai-codex",
                "model": "gpt-5.4-mini",
                "systemPromptReport": {
                    "provider": "openai-codex",
                    "model": "gpt-5.4-mini",
                    "bootstrapMaxChars": 20000,
                    "bootstrapTotalMaxChars": 150000,
                    "systemPrompt": {"chars": 30000},
                    "skills": {"promptChars": 10000, "entries": [{"name": "coding-agent", "blockChars": 800}]},
                    "tools": {
                        "listChars": 10000,
                        "schemaChars": 25000,
                        "entries": [{"name": "message", "summaryChars": 200, "schemaChars": 6000, "propertiesCount": 50}],
                    },
                    "injectedWorkspaceFiles": [{"name": "AGENTS.md", "path": "/tmp/AGENTS.md", "injectedChars": 7000, "truncated": False}],
                },
            }

            payload = session_latency_audit.build_session_latency_audit(
                session_jsonl=session_path,
                session_key="agent:main:telegram:direct:test",
                session_metadata=metadata,
            )

            self.assertEqual(payload["schema"], "openclaw.task-system.session-latency-audit.v1")
            self.assertEqual(payload["summary"]["turnCount"], 2)
            self.assertEqual(payload["summary"]["startupTranscriptCarryoverChars"], 67)
            self.assertEqual(payload["turns"][0]["durationS"], 18.0)
            self.assertEqual(payload["turns"][0]["llmDurationS"], 16.0)
            self.assertEqual(payload["turns"][0]["toolDurationS"], 2.0)
            self.assertEqual(payload["turns"][0]["toolPhases"][0]["llmBeforeS"], 10.0)
            self.assertEqual(payload["turns"][0]["toolPhases"][0]["llmAfterS"], 6.0)
            self.assertEqual(payload["turns"][1]["likelyBottleneck"], "llm")
            self.assertEqual(payload["staticContext"]["staticTotalChars"], 82000)
            self.assertEqual(payload["slowestTurns"][0]["turnIndex"], 1)

    def test_load_session_metadata_can_resolve_by_session_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            sessions_dir = root / "agents" / "main" / "sessions"
            sessions_dir.mkdir(parents=True)
            session_path = sessions_dir / "abc.jsonl"
            session_path.write_text("", encoding="utf-8")
            sessions_file = sessions_dir / "sessions.json"
            sessions_file.write_text(
                json.dumps(
                    {
                        "agent:main:telegram:direct:test": {
                            "sessionId": "abc",
                            "sessionFile": str(session_path),
                            "modelProvider": "openai-codex",
                            "model": "gpt-5.4-mini",
                        }
                    }
                ),
                encoding="utf-8",
            )

            session_key, metadata, resolved_sessions_file = session_latency_audit._load_session_metadata(
                session_key="agent:main:telegram:direct:test",
                session_jsonl=None,
                openclaw_home=root,
                sessions_file=None,
            )

            self.assertEqual(session_key, "agent:main:telegram:direct:test")
            self.assertEqual(metadata["sessionId"], "abc")
            self.assertEqual(resolved_sessions_file, sessions_file.resolve())


if __name__ == "__main__":
    unittest.main()
