from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


instruction_executor = load_runtime_module("instruction_executor")


class InstructionExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-dispatch-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        (self.paths.data_dir / "send-instructions").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def write_instruction(self, name: str, payload: dict[str, object]) -> Path:
        path = self.paths.data_dir / "send-instructions" / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_build_dispatch_decision_skips_internal_agent_channel(self) -> None:
        decision = instruction_executor.build_dispatch_decision(
            {
                "channel": "agent",
                "chat_id": "chat:test",
                "message": "notify",
            }
        )
        self.assertEqual(decision.action, "skip")
        self.assertEqual(decision.reason, "internal-agent-channel")

    def test_build_dispatch_decision_for_feishu(self) -> None:
        decision = instruction_executor.build_dispatch_decision(
            {
                "channel": "telegram",
                "chat_id": "chat:test",
                "message": "notify",
            },
            openclaw_bin="/mock/openclaw",
        )
        self.assertEqual(decision.action, "send")
        self.assertEqual(
            decision.command,
            [
                "/mock/openclaw",
                "message",
                "send",
                "--channel",
                "telegram",
                "--target",
                "chat:test",
                "--message",
                "notify",
            ],
        )

    def test_build_dispatch_decision_includes_account_id_when_present(self) -> None:
        decision = instruction_executor.build_dispatch_decision(
            {
                "channel": "slack",
                "account_id": "workspace-bot",
                "chat_id": "#ops",
                "message": "notify",
            },
            openclaw_bin="/mock/openclaw",
        )
        self.assertEqual(
            decision.command,
            [
                "/mock/openclaw",
                "message",
                "send",
                "--channel",
                "slack",
                "--account",
                "workspace-bot",
                "--target",
                "#ops",
                "--message",
                "notify",
            ],
        )

    def test_classify_failure_marks_network_error_retryable(self) -> None:
        decision = instruction_executor.DispatchDecision(action="send", reason="supported", command=["mock"])
        classification, retryable = instruction_executor.classify_failure(
            decision=decision,
            exit_code=1,
            stderr="Network request failed with timeout",
        )
        self.assertEqual(classification, "transport-retryable")
        self.assertTrue(retryable)

    def test_classify_failure_marks_auth_error_nonretryable(self) -> None:
        decision = instruction_executor.DispatchDecision(action="send", reason="supported", command=["mock"])
        classification, retryable = instruction_executor.classify_failure(
            decision=decision,
            exit_code=1,
            stderr="Unauthorized: bad token",
        )
        self.assertEqual(classification, "auth")
        self.assertFalse(retryable)

    def test_execute_all_writes_dispatch_results_in_dry_run(self) -> None:
        self.write_instruction(
            "task_123.json",
            {
                "schema": "openclaw.task-system.send-instruction.v1",
                "task_id": "task_123",
                "agent_id": "main",
                "session_key": "session:test",
                "channel": "telegram",
                "chat_id": "chat:test",
                "message": "notify message",
            },
        )
        results = instruction_executor.execute_all(paths=self.paths, execute=False, openclaw_bin="/mock/openclaw")
        self.assertEqual(len(results), 1)
        result_path = self.paths.data_dir / "dispatch-results" / "task_123.json"
        self.assertTrue(result_path.exists())
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertFalse(payload["executed"])
        self.assertEqual(payload["action"], "send")
        self.assertEqual(payload["command"][0], "/mock/openclaw")
        self.assertEqual(payload["execution_context"], "dry-run")
        self.assertEqual(payload["requested_execution_context"], "local")

    def test_execute_all_marks_agent_channel_as_skip(self) -> None:
        self.write_instruction(
            "task_agent.json",
            {
                "schema": "openclaw.task-system.send-instruction.v1",
                "task_id": "task_agent",
                "agent_id": "main",
                "session_key": "agent:main:main",
                "channel": "agent",
                "chat_id": "chat:test",
                "message": "internal note",
            },
        )
        instruction_executor.execute_all(paths=self.paths, execute=False)
        payload = json.loads((self.paths.data_dir / "dispatch-results" / "task_agent.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["action"], "skip")
        self.assertEqual(payload["reason"], "internal-agent-channel")
        self.assertEqual(payload["execution_context"], "dry-run")
        self.assertEqual(payload["requested_execution_context"], "local")

    def test_execute_all_archives_skipped_instruction_when_execute_enabled(self) -> None:
        self.write_instruction(
            "task_agent.json",
            {
                "schema": "openclaw.task-system.send-instruction.v1",
                "task_id": "task_agent",
                "agent_id": "main",
                "session_key": "agent:main:main",
                "channel": "agent",
                "chat_id": "chat:test",
                "message": "internal note",
            },
        )
        results = instruction_executor.execute_all(paths=self.paths, execute=True, execution_context="host")
        self.assertEqual(len(results), 1)
        self.assertFalse((self.paths.data_dir / "send-instructions" / "task_agent.json").exists())
        self.assertTrue((self.paths.data_dir / "processed-instructions" / "task_agent.json").exists())
        payload = json.loads((self.paths.data_dir / "dispatch-results" / "task_agent.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["action"], "skip")
        self.assertEqual(payload["reason"], "internal-agent-channel")
        self.assertEqual(payload["execution_context"], "host")
        self.assertEqual(payload["requested_execution_context"], "host")

    def test_execute_all_cleans_stale_delivery_artifacts_after_archive(self) -> None:
        self.write_instruction(
            "task_agent.json",
            {
                "schema": "openclaw.task-system.send-instruction.v1",
                "task_id": "task_agent",
                "agent_id": "main",
                "session_key": "agent:main:main",
                "channel": "agent",
                "chat_id": "chat:test",
                "message": "internal note",
            },
        )
        sent_path = self.paths.data_dir / "sent" / "task_agent.json"
        sent_path.parent.mkdir(parents=True, exist_ok=True)
        sent_path.write_text(json.dumps({"task_id": "task_agent"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ready_path = self.paths.data_dir / "delivery-ready" / "task_agent.json"
        ready_path.parent.mkdir(parents=True, exist_ok=True)
        ready_path.write_text(json.dumps({"task_id": "task_agent"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        instruction_executor.execute_all(paths=self.paths, execute=True, execution_context="host")

        self.assertFalse(sent_path.exists())
        self.assertFalse(ready_path.exists())

    def test_execute_all_archives_successful_instruction_when_execute_enabled(self) -> None:
        mock_bin = self.temp_dir / "mock-openclaw"
        mock_log = self.temp_dir / "mock-openclaw.log"
        mock_bin.write_text(
            "\n".join(
                [
                    "#!/bin/sh",
                    f'printf "%s\\n" "$@" > "{mock_log}"',
                    'printf "sent\\n"',
                    "exit 0",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.chmod(mock_bin, 0o755)

        self.write_instruction(
            "task_send.json",
            {
                "schema": "openclaw.task-system.send-instruction.v1",
                "task_id": "task_send",
                "agent_id": "main",
                "session_key": "session:test",
                "channel": "telegram",
                "chat_id": "chat:test",
                "message": "notify message",
            },
        )

        results = instruction_executor.execute_all(
            paths=self.paths,
            execute=True,
            openclaw_bin=str(mock_bin),
            execution_context="host",
        )
        self.assertEqual(len(results), 1)
        self.assertFalse((self.paths.data_dir / "send-instructions" / "task_send.json").exists())
        self.assertTrue((self.paths.data_dir / "processed-instructions" / "task_send.json").exists())

        dispatch_payload = json.loads((self.paths.data_dir / "dispatch-results" / "task_send.json").read_text(encoding="utf-8"))
        self.assertTrue(dispatch_payload["executed"])
        self.assertEqual(dispatch_payload["exit_code"], 0)
        self.assertEqual(dispatch_payload["stdout"], "sent\n")
        self.assertEqual(dispatch_payload["execution_context"], "host")
        self.assertEqual(dispatch_payload["requested_execution_context"], "host")
        self.assertEqual(mock_log.read_text(encoding="utf-8").splitlines(), ["message", "send", "--channel", "telegram", "--target", "chat:test", "--message", "notify message"])

    def test_execute_all_archives_failed_instruction_when_command_fails(self) -> None:
        mock_bin = self.temp_dir / "mock-openclaw-fail"
        mock_bin.write_text(
            "\n".join(
                [
                    "#!/bin/sh",
                    'printf "send failed\\n" >&2',
                    "exit 7",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.chmod(mock_bin, 0o755)

        self.write_instruction(
            "task_fail.json",
            {
                "schema": "openclaw.task-system.send-instruction.v1",
                "task_id": "task_fail",
                "agent_id": "main",
                "session_key": "session:test",
                "channel": "telegram",
                "chat_id": "chat:test",
                "message": "notify message",
            },
        )

        results = instruction_executor.execute_all(
            paths=self.paths,
            execute=True,
            openclaw_bin=str(mock_bin),
            execution_context="local",
        )
        self.assertEqual(len(results), 1)
        self.assertFalse((self.paths.data_dir / "send-instructions" / "task_fail.json").exists())
        self.assertTrue((self.paths.data_dir / "failed-instructions" / "task_fail.json").exists())

        dispatch_payload = json.loads((self.paths.data_dir / "dispatch-results" / "task_fail.json").read_text(encoding="utf-8"))
        self.assertTrue(dispatch_payload["executed"])
        self.assertEqual(dispatch_payload["exit_code"], 7)
        self.assertEqual(dispatch_payload["stderr"], "send failed\n")
        self.assertEqual(dispatch_payload["execution_context"], "local")
        self.assertEqual(dispatch_payload["requested_execution_context"], "local")
        self.assertEqual(dispatch_payload["failure_classification"], "transport-nonretryable")
        self.assertFalse(dispatch_payload["retryable"])
        archived_payload = json.loads(
            (self.paths.data_dir / "failed-instructions" / "task_fail.json").read_text(encoding="utf-8")
        )
        self.assertEqual(archived_payload["_last_failure_classification"], "transport-nonretryable")
        self.assertFalse(archived_payload["_last_failure_retryable"])

    def test_retry_failed_instructions_retries_retryable_failure(self) -> None:
        failed_path = self.paths.data_dir / "failed-instructions" / "task_retry.json"
        failed_path.parent.mkdir(parents=True, exist_ok=True)
        failed_path.write_text(
            json.dumps(
                {
                    "task_id": "task_retry",
                    "agent_id": "main",
                    "session_key": "session:test",
                    "channel": "telegram",
                    "chat_id": "chat:test",
                    "message": "retry me",
                    "_retry_count": 0,
                    "_last_failure_retryable": True,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        mock_bin = self.temp_dir / "mock-openclaw-retry"
        mock_bin.write_text("#!/bin/sh\nprintf 'sent\\n'\nexit 0\n", encoding="utf-8")
        os.chmod(mock_bin, 0o755)

        results = instruction_executor.retry_failed_instructions(
            paths=self.paths,
            openclaw_bin=str(mock_bin),
            execution_context="host",
        )

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["retry_from_failed"])
        self.assertFalse((self.paths.data_dir / "failed-instructions" / "task_retry.json").exists())
        archived_payload = json.loads(
            (self.paths.data_dir / "processed-instructions" / "task_retry.json").read_text(encoding="utf-8")
        )
        self.assertEqual(archived_payload["_retry_count"], 1)

    def test_retry_failed_instructions_skips_nonretryable_failure(self) -> None:
        failed_path = self.paths.data_dir / "failed-instructions" / "task_no_retry.json"
        failed_path.parent.mkdir(parents=True, exist_ok=True)
        failed_path.write_text(
            json.dumps(
                {
                    "task_id": "task_no_retry",
                    "_last_failure_retryable": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        results = instruction_executor.retry_failed_instructions(paths=self.paths)

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["skipped_retry"])
        self.assertEqual(results[0]["reason"], "non-retryable-failure")
        self.assertTrue(failed_path.exists())

    def test_annotate_failed_instruction_metadata_backfills_from_dispatch_result(self) -> None:
        failed_path = self.paths.data_dir / "failed-instructions" / "task_retry.json"
        failed_path.parent.mkdir(parents=True, exist_ok=True)
        failed_path.write_text(
            json.dumps(
                {
                    "task_id": "task_retry",
                    "channel": "telegram",
                    "chat_id": "8705812936",
                    "message": "retry me",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        dispatch_path = self.paths.data_dir / "dispatch-results" / "task_retry.json"
        dispatch_path.parent.mkdir(parents=True, exist_ok=True)
        dispatch_path.write_text(
            json.dumps(
                {
                    "task_id": "task_retry",
                    "exit_code": 1,
                    "stderr": "Network request failed with timeout",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        updates = instruction_executor.annotate_failed_instruction_metadata(paths=self.paths, openclaw_bin="/mock/openclaw")

        self.assertEqual(len(updates), 1)
        payload = json.loads(failed_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["_last_failure_classification"], "transport-retryable")
        self.assertTrue(payload["_last_failure_retryable"])
