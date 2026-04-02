from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


emit_task_event = load_runtime_module("emit_task_event")
consume_outbox = load_runtime_module("consume_outbox")
prepare_delivery = load_runtime_module("prepare_delivery")
delivery_dispatch = load_runtime_module("delivery_dispatch")
instruction_executor = load_runtime_module("instruction_executor")


class DeliveryFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-delivery-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.store = task_state_module.TaskStore(paths=self.paths)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_outbox_to_sent_flow(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="delivery flow",
        )
        task = self.store.start_task(task.task_id)
        event_path = emit_task_event.write_outbox(
            task.to_dict(),
            message="test message",
            paths=self.paths,
        )
        self.assertTrue(event_path.exists())

        results = consume_outbox.consume_once(paths=self.paths)
        self.assertEqual(len(results), 1)
        self.assertFalse(event_path.exists())
        sent_path = self.paths.data_dir / "sent" / f"{task.task_id}.json"
        self.assertTrue(sent_path.exists())

        sent_payload = json.loads(sent_path.read_text(encoding="utf-8"))
        self.assertEqual(sent_payload["message"], "test message")
        self.assertIn("sent_at", sent_payload)

    def test_sent_to_delivery_ready_flow(self) -> None:
        sent_dir = self.paths.data_dir / "sent"
        sent_dir.mkdir(parents=True, exist_ok=True)
        sent_file = sent_dir / "task_123.json"
        sent_file.write_text(
            json.dumps(
                {
                    "schema": "openclaw.task-system.outbox.v1",
                    "task_id": "task_123",
                    "agent_id": "main",
                    "session_key": "session:test",
                    "channel": "feishu",
                    "chat_id": "chat:test",
                    "message": "delivery message",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        written = prepare_delivery.prepare_all(paths=self.paths)
        self.assertEqual(len(written), 1)
        delivery_path = self.paths.data_dir / "delivery-ready" / "task_123.json"
        self.assertTrue(delivery_path.exists())

        payload = json.loads(delivery_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["task_id"], "task_123")
        self.assertEqual(payload["message"], "delivery message")
        self.assertEqual(payload["schema"], "openclaw.task-system.delivery.v1")

    def test_delivery_ready_to_send_instruction_flow(self) -> None:
        ready_dir = self.paths.data_dir / "delivery-ready"
        ready_dir.mkdir(parents=True, exist_ok=True)
        ready_file = ready_dir / "task_abc.json"
        ready_file.write_text(
            json.dumps(
                {
                    "schema": "openclaw.task-system.delivery.v1",
                    "task_id": "task_abc",
                    "agent_id": "main",
                    "session_key": "session:test",
                    "channel": "feishu",
                    "chat_id": "chat:test",
                    "message": "notify message",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        written = delivery_dispatch.dispatch_all(paths=self.paths)
        self.assertEqual(len(written), 1)
        instruction_path = self.paths.data_dir / "send-instructions" / "task_abc.json"
        self.assertTrue(instruction_path.exists())

        payload = json.loads(instruction_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "openclaw.task-system.send-instruction.v1")
        self.assertEqual(payload["message"], "notify message")

    def test_send_instruction_to_dispatch_result_flow(self) -> None:
        instruction_dir = self.paths.data_dir / "send-instructions"
        instruction_dir.mkdir(parents=True, exist_ok=True)
        instruction_file = instruction_dir / "task_dispatch.json"
        instruction_file.write_text(
            json.dumps(
                {
                    "schema": "openclaw.task-system.send-instruction.v1",
                    "task_id": "task_dispatch",
                    "agent_id": "main",
                    "session_key": "session:test",
                    "channel": "telegram",
                    "chat_id": "chat:test",
                    "message": "notify message",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        results = instruction_executor.execute_all(paths=self.paths, execute=False, openclaw_bin="/mock/openclaw")
        self.assertEqual(len(results), 1)
        dispatch_path = self.paths.data_dir / "dispatch-results" / "task_dispatch.json"
        self.assertTrue(dispatch_path.exists())

        payload = json.loads(dispatch_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "openclaw.task-system.dispatch-result.v1")
        self.assertEqual(payload["action"], "send")
        self.assertTrue(instruction_file.exists())


if __name__ == "__main__":
    unittest.main()
