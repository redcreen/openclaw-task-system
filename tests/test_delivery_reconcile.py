from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


delivery_reconcile = load_runtime_module("delivery_reconcile")


class DeliveryReconcileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-delivery-reconcile-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.store = task_state_module.TaskStore(paths=self.paths)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_artifact(self, directory: str, task_id: str, payload: dict[str, object]) -> Path:
        target = self.paths.data_dir / directory / f"{task_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return target

    def test_reconcile_reports_stale_intermediate_artifacts(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="telegram",
            chat_id="chat:test",
            task_label="reconcile task",
        )
        self._write_artifact("processed-instructions", task.task_id, {"task_id": task.task_id})
        stale_path = self._write_artifact("send-instructions", task.task_id, {"task_id": task.task_id})

        findings = delivery_reconcile.reconcile_delivery_artifacts(paths=self.paths, apply_changes=False)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["task_id"], task.task_id)
        self.assertIn(str(stale_path), findings[0]["stale_paths"])
        self.assertTrue(stale_path.exists())

    def test_reconcile_apply_removes_stale_intermediate_artifacts(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="telegram",
            chat_id="chat:test",
            task_label="reconcile apply task",
        )
        self._write_artifact("failed-instructions", task.task_id, {"task_id": task.task_id})
        stale_sent = self._write_artifact("sent", task.task_id, {"task_id": task.task_id})
        stale_ready = self._write_artifact("delivery-ready", task.task_id, {"task_id": task.task_id})

        findings = delivery_reconcile.reconcile_delivery_artifacts(paths=self.paths, apply_changes=True)

        self.assertEqual(len(findings), 1)
        self.assertFalse(stale_sent.exists())
        self.assertFalse(stale_ready.exists())

    def test_render_markdown_reports_clean_state(self) -> None:
        markdown = delivery_reconcile.render_markdown([])
        self.assertIn("- clean", markdown)


if __name__ == "__main__":
    unittest.main()
