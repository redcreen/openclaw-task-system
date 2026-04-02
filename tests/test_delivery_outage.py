from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


delivery_outage = load_runtime_module("delivery_outage")


class DeliveryOutageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-delivery-outage-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_acknowledge_and_find_outage(self) -> None:
        entry = delivery_outage.acknowledge_outage(
            channel="telegram",
            chat_id="8705812936",
            reason="network outage",
            paths=self.paths,
        )

        found = delivery_outage.find_outage(channel="telegram", chat_id="8705812936", paths=self.paths)

        self.assertEqual(found["reason"], "network outage")
        self.assertEqual(entry["channel"], "telegram")

    def test_clear_outage_removes_entry(self) -> None:
        delivery_outage.acknowledge_outage(
            channel="telegram",
            chat_id="8705812936",
            reason="network outage",
            paths=self.paths,
        )

        removed = delivery_outage.clear_outage(channel="telegram", chat_id="8705812936", paths=self.paths)

        self.assertEqual(removed, 1)
        self.assertIsNone(delivery_outage.find_outage(channel="telegram", chat_id="8705812936", paths=self.paths))


if __name__ == "__main__":
    unittest.main()
