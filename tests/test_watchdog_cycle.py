from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


watchdog_cycle = load_runtime_module("watchdog_cycle")


class WatchdogCycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-watchdog-cycle-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.store = task_state_module.TaskStore(paths=self.paths)
        self.config_path = self.temp_dir / "task_system.json"
        self.config_path.write_text(
            json.dumps({"taskSystem": {"storageDir": str(self.paths.data_dir)}}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.previous_env = os.environ.get("OPENCLAW_TASK_SYSTEM_CONFIG")
        os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = str(self.config_path)

    def tearDown(self) -> None:
        if self.previous_env is None:
            os.environ.pop("OPENCLAW_TASK_SYSTEM_CONFIG", None)
        else:
            os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = self.previous_env
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_run_watchdog_cycle_creates_send_instruction(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="feishu:main:chat:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="overdue task",
        )
        task = self.store.start_task(task.task_id)
        stored = self.store.load_task(task.task_id)
        stored.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        self.store.save_task(stored)

        result = watchdog_cycle.run_watchdog_cycle(config_path=self.config_path)
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(len(result["send_instructions"]), 1)

        instruction_path = self.paths.data_dir / "send-instructions" / f"{task.task_id}.json"
        processed_path = self.paths.data_dir / "processed-instructions" / f"{task.task_id}.json"
        self.assertFalse(instruction_path.exists())
        self.assertTrue(processed_path.exists())
        payload = json.loads(processed_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["task_id"], task.task_id)
        self.assertEqual(payload["channel"], "feishu")

    def test_run_watchdog_cycle_can_skip_execution_and_retry_flags(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="telegram:main:chat:test",
            channel="telegram",
            chat_id="chat:test",
            task_label="overdue task",
        )
        task = self.store.start_task(task.task_id)
        stored = self.store.load_task(task.task_id)
        stored.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        self.store.save_task(stored)

        result = watchdog_cycle.run_watchdog_cycle(
            config_path=self.config_path,
            execute_instructions=False,
            retry_failed=False,
            execution_context="host",
        )

        self.assertFalse(result["execute_instructions"])
        self.assertFalse(result["retry_failed"])
        self.assertEqual(result["execution_context"], "host")
        self.assertEqual(len(result["execution_results"]), 1)
        dispatch_payload = json.loads(
            (self.paths.data_dir / "dispatch-results" / f"{task.task_id}.json").read_text(encoding="utf-8")
        )
        self.assertFalse(dispatch_payload["executed"])
        self.assertEqual(dispatch_payload["action"], "send")
        self.assertEqual(dispatch_payload["execution_context"], "dry-run")
        self.assertEqual(dispatch_payload["requested_execution_context"], "host")


if __name__ == "__main__":
    unittest.main()
