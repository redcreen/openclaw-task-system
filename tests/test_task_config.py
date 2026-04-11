from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module


task_config = load_runtime_module("task_config")


class TaskConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-config-tests."))
        self.config_path = self.temp_dir / "task_system.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def write_config(self, payload: dict[str, object]) -> None:
        self.config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_missing_config_uses_defaults(self) -> None:
        config = task_config.load_task_system_config(config_path=self.config_path)
        self.assertTrue(config.enabled)
        self.assertEqual(config.delivery.mode, "session-aware")
        self.assertTrue(config.delivery.auto_execute_instructions)
        self.assertFalse(config.delivery.retry_failed_instructions)
        self.assertEqual(config.delivery.execution_context, "local")

    def test_load_config_resolves_relative_storage_dir(self) -> None:
        self.write_config(
            {
                "taskSystem": {
                    "storageDir": "./workspace/openclaw-task-system/data-test",
                    "delivery": {
                        "autoExecuteInstructions": False,
                        "retryFailedInstructions": True,
                        "executionContext": "host",
                    },
                    "agents": {
                        "main": {
                            "enabled": True,
                            "classification": {
                                "minRequestLength": 12,
                                "minReasonCount": 1,
                            },
                            "silenceMonitor": {
                                "enabled": True,
                                "silentTimeoutSeconds": 45,
                                "resendIntervalSeconds": 90,
                            },
                        }
                    },
                }
            }
        )
        config = task_config.load_task_system_config(config_path=self.config_path)
        self.assertTrue(str(config.storage_dir).endswith("workspace/openclaw-task-system/data-test"))
        self.assertFalse(config.delivery.auto_execute_instructions)
        self.assertTrue(config.delivery.retry_failed_instructions)
        self.assertEqual(config.delivery.execution_context, "host")
        agent = config.agent_config("main")
        self.assertEqual(agent.classification.min_request_length, 12)
        self.assertEqual(agent.silence_monitor.silent_timeout_seconds, 45)

    def test_planning_prompt_contract_has_stable_defaults(self) -> None:
        config = task_config.load_task_system_config(config_path=self.config_path)
        planning = config.agent_config("main").planning
        self.assertTrue(planning.enabled)
        self.assertEqual(planning.mode, "tool-first-after-first-ack")
        self.assertIn("Do not generate the first [wd].", planning.system_prompt_contract)
        self.assertIn("main_user_content_mode=none", planning.system_prompt_contract)
        self.assertIn("followup_summary", planning.system_prompt_contract)
        self.assertIn("all other future-action planning: tool-first", planning.system_prompt_contract)
        self.assertNotIn("<task_user_content>", planning.system_prompt_contract)

    def test_planning_prompt_contract_can_be_overridden_by_user_config(self) -> None:
        self.write_config(
            {
                "taskSystem": {
                    "agents": {
                        "main": {
                            "planning": {
                                "enabled": True,
                                "mode": "tool-first-after-first-ack",
                                "systemPromptContract": "custom contract for review and rollout"
                            }
                        }
                    }
                }
            }
        )
        config = task_config.load_task_system_config(config_path=self.config_path)
        planning = config.agent_config("main").planning
        self.assertTrue(planning.enabled)
        self.assertEqual(planning.mode, "tool-first-after-first-ack")
        self.assertEqual(planning.system_prompt_contract, "custom contract for review and rollout")


if __name__ == "__main__":
    unittest.main()
