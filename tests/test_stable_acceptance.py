from __future__ import annotations

import unittest

from runtime_loader import load_runtime_module


stable_acceptance = load_runtime_module("stable_acceptance")


class StableAcceptanceTests(unittest.TestCase):
    def test_run_stable_acceptance_succeeds(self) -> None:
        payload = stable_acceptance.run_stable_acceptance()
        self.assertTrue(payload["ok"])
        step_names = [step["step"] for step in payload["steps"]]
        self.assertEqual(
            step_names,
            [
                "plugin-doctor-checks",
                "plugin-smoke",
                "main-acceptance",
                "channel-acceptance",
                "retry-failed-instructions",
                "health-report-clean",
            ],
        )

    def test_render_markdown_includes_health_step(self) -> None:
        payload = stable_acceptance.run_stable_acceptance()
        rendered = stable_acceptance.render_markdown(payload)
        self.assertIn("# Stable Acceptance", rendered)
        self.assertIn("health-report-clean: ok", rendered)


if __name__ == "__main__":
    unittest.main()
