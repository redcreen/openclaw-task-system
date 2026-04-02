from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


enqueue_test_instruction = load_runtime_module("enqueue_test_instruction")


class EnqueueTestInstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-enqueue-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_instruction_includes_optional_account(self) -> None:
        payload = enqueue_test_instruction.build_instruction(
            task_id="task_test_1",
            agent_id="main",
            session_key="session:test",
            channel="slack",
            chat_id="#ops",
            message="ping",
            account_id="workspace-bot",
        )
        self.assertEqual(payload["account_id"], "workspace-bot")

    def test_enqueue_instruction_writes_send_instruction_file(self) -> None:
        payload = enqueue_test_instruction.build_instruction(
            task_id="task_test_2",
            agent_id="main",
            session_key="session:test",
            channel="telegram",
            chat_id="@example",
            message="ping",
        )
        path = enqueue_test_instruction.enqueue_instruction(payload, paths=self.paths)
        self.assertTrue(path.exists())
        written = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(written["task_id"], "task_test_2")
        self.assertEqual(written["channel"], "telegram")
