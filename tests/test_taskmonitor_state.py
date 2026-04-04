from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module


taskmonitor_state = load_runtime_module("taskmonitor_state")


class TaskMonitorStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="taskmonitor-state-tests."))
        self.data_dir = self.temp_dir / "data"
        self.config_path = self.temp_dir / "task_system.json"
        self.config_path.write_text(
            json.dumps({"taskSystem": {"storageDir": str(self.data_dir)}}, ensure_ascii=False, indent=2) + "\n",
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

    def test_taskmonitor_defaults_to_enabled(self) -> None:
        self.assertTrue(taskmonitor_state.get_taskmonitor_enabled("session:test"))

    def test_taskmonitor_can_be_disabled_and_reenabled(self) -> None:
        disabled = taskmonitor_state.set_taskmonitor_enabled("session:test", False)
        self.assertFalse(disabled["enabled"])
        self.assertFalse(taskmonitor_state.get_taskmonitor_enabled("session:test"))

        enabled = taskmonitor_state.set_taskmonitor_enabled("session:test", True)
        self.assertTrue(enabled["enabled"])
        self.assertTrue(taskmonitor_state.get_taskmonitor_enabled("session:test"))

    def test_list_taskmonitor_overrides_returns_sorted_mapping(self) -> None:
        taskmonitor_state.set_taskmonitor_enabled("session:b", False)
        taskmonitor_state.set_taskmonitor_enabled("session:a", True)

        overrides = taskmonitor_state.list_taskmonitor_overrides()

        self.assertEqual(list(overrides.keys()), ["session:a", "session:b"])
        self.assertTrue(overrides["session:a"])
        self.assertFalse(overrides["session:b"])


if __name__ == "__main__":
    unittest.main()
