from __future__ import annotations

import unittest

from runtime_loader import load_runtime_module


main_ops_acceptance = load_runtime_module("main_ops_acceptance")


class MainOpsAcceptanceTests(unittest.TestCase):
    def test_run_main_ops_acceptance_covers_operator_recovery_samples(self) -> None:
        payload = main_ops_acceptance.run_main_ops_acceptance()

        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["steps"]), 6)
        self.assertTrue(all(step["ok"] for step in payload["steps"]))

    def test_render_markdown_includes_operator_acceptance_steps(self) -> None:
        rendered = main_ops_acceptance.render_markdown(main_ops_acceptance.run_main_ops_acceptance())

        self.assertIn("# Main Ops Acceptance", rendered)
        self.assertIn("- session-focused-dashboard-navigation-contract: ok", rendered)
        self.assertIn("- promise-without-task-projects-ops-recovery-contract: ok", rendered)
        self.assertIn("- planner-timeout-projects-ops-recovery-contract: ok", rendered)
        self.assertIn("- missing-followup-projects-ops-recovery-contract: ok", rendered)
        self.assertIn("- watchdog-blocked-projects-auto-resume-contract: ok", rendered)
        self.assertIn("- operator-snapshot-views-contract: ok", rendered)


if __name__ == "__main__":
    unittest.main()
