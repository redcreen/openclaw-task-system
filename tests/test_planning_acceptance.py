from __future__ import annotations

import unittest

from runtime_loader import load_runtime_module


planning_acceptance = load_runtime_module("planning_acceptance")


class PlanningAcceptanceTests(unittest.TestCase):
    def test_run_planning_acceptance_succeeds(self) -> None:
        payload = planning_acceptance.run_planning_acceptance()

        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["steps"]), 10)
        self.assertTrue(all(step["ok"] for step in payload["steps"]))

    def test_render_markdown_includes_planning_steps(self) -> None:
        payload = planning_acceptance.run_planning_acceptance()

        rendered = planning_acceptance.render_markdown(payload)

        self.assertIn("# Planning Acceptance", rendered)
        self.assertIn("- register-source-task: ok", rendered)
        self.assertIn("- project-future-first-immediate-output-contract: ok", rendered)
        self.assertIn("- project-immediate-summary-and-reply-target-contract: ok", rendered)
        self.assertIn("- compound-request-requires-structured-plan: ok", rendered)
        self.assertIn("- promise-without-task-projects-recovery-contract: ok", rendered)
        self.assertIn("- planner-timeout-projects-recovery-contract: ok", rendered)
        self.assertIn("- missing-followup-task-projects-recovery-contract: ok", rendered)
        self.assertIn("- materialize-and-finalize-followup: ok", rendered)
        self.assertIn("- claim-overdue-followup-and-project-ops: ok", rendered)


if __name__ == "__main__":
    unittest.main()
