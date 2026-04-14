from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.growware_policy_fixtures import sync_policy
from tests.runtime_loader import load_runtime_module


growware_policy_sync = load_runtime_module("growware_policy_sync")


class GrowwarePolicySyncTests(unittest.TestCase):
    def test_policy_sync_writes_compiled_policy_layer(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            result = sync_policy(root)

            self.assertTrue(result["ok"])
            self.assertTrue(result["changed"])
            self.assertTrue((root / ".policy" / "manifest.json").exists())
            self.assertTrue((root / ".policy" / "index.json").exists())
            self.assertTrue((root / ".policy" / "provenance.json").exists())
            self.assertTrue((root / ".policy" / "rules" / "growware.feedback-intake.same-session.v1.json").exists())
            self.assertTrue((root / ".policy" / "rules" / "growware.project.local-deploy.v1.json").exists())

            validate = growware_policy_sync.validate_policy_catalog(root)
            self.assertTrue(validate["ok"])
            feedback_rule = next(rule for rule in validate["rules"] if rule["id"] == "growware.feedback-intake.same-session.v1")
            self.assertEqual(feedback_rule["defaultExecutionSource"], "daemon-owned")
            self.assertIn("sameSessionClassifier", feedback_rule)
            self.assertIn("keep `inline code` intact", feedback_rule["allowed"])
            self.assertEqual({rule["id"] for rule in validate["rules"]}, {
                "growware.feedback-intake.same-session.v1",
                "growware.project.local-deploy.v1",
            })


if __name__ == "__main__":
    unittest.main()
