from __future__ import annotations

import unittest

from runtime_loader import load_runtime_module


main_acceptance = load_runtime_module("main_acceptance")


class MainAcceptanceTests(unittest.TestCase):
    def test_run_main_acceptance_succeeds(self) -> None:
        payload = main_acceptance.run_main_acceptance()
        self.assertTrue(payload["ok"])
        step_names = [step["step"] for step in payload["steps"]]
        self.assertEqual(
            step_names,
            [
                "register-main-task",
                "sync-main-progress",
                "finalize-main-task",
                "watchdog-fallback-cycle",
            ],
        )

    def test_render_markdown_includes_watchdog_step(self) -> None:
        payload = main_acceptance.run_main_acceptance()
        rendered = main_acceptance.render_markdown(payload)
        self.assertIn("# Main Acceptance", rendered)
        self.assertIn("watchdog-fallback-cycle: ok", rendered)


if __name__ == "__main__":
    unittest.main()
