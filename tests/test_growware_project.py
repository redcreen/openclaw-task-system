from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.runtime_loader import load_runtime_module
from tests.growware_policy_fixtures import sync_policy


growware_project = load_runtime_module("growware_project")


class GrowwareProjectTests(unittest.TestCase):
    def test_build_summary_reads_project_and_channel_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sync_policy(root)
            growware_dir = root / ".growware"
            (growware_dir / "contracts").mkdir(parents=True)
            (growware_dir / "policies").mkdir(parents=True)
            (growware_dir / "ops").mkdir(parents=True)
            (growware_dir / "project.json").write_text(
                json.dumps(
                    {
                        "projectId": "demo",
                        "growware": {"daemon": {"agentId": "growware"}},
                    }
                ),
                encoding="utf-8",
            )
            (growware_dir / "channels.json").write_text(
                json.dumps(
                    {
                        "feedbackChannel": {"provider": "feishu", "accountId": "feishu6-chat"},
                        "runtimeSurface": {"pluginId": "openclaw-task-system"},
                    }
                ),
                encoding="utf-8",
            )
            (growware_dir / "policies" / "feedback-intake.v1.json").write_text(
                json.dumps({"defaultExecutionSource": "daemon-owned"}),
                encoding="utf-8",
            )

            summary = growware_project.build_summary(root)

        self.assertEqual(summary["projectId"], "demo")
        self.assertEqual(summary["feedbackChannel"]["accountId"], "feishu6-chat")
        self.assertEqual(summary["runtimeSurface"]["pluginId"], "openclaw-task-system")
        self.assertEqual(summary["feedbackIntake"]["defaultExecutionSource"], "daemon-owned")
        self.assertEqual(summary["policyManifest"]["schema"], "growware.policy.manifest.v1")


if __name__ == "__main__":
    unittest.main()
