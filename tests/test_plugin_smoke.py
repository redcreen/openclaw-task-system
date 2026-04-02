from __future__ import annotations

import unittest

from runtime_loader import load_runtime_module


plugin_smoke = load_runtime_module("plugin_smoke")


class PluginSmokeTests(unittest.TestCase):
    def test_run_plugin_smoke_succeeds(self) -> None:
        payload = plugin_smoke.run_plugin_smoke()
        self.assertTrue(payload["ok"])
        step_names = [step["step"] for step in payload["steps"]]
        self.assertEqual(step_names, ["register", "resolve-active", "progress-active", "finalize-active"])

    def test_render_markdown_includes_steps(self) -> None:
        payload = plugin_smoke.run_plugin_smoke()
        rendered = plugin_smoke.render_markdown(payload)
        self.assertIn("# Plugin Smoke", rendered)
        self.assertIn("register: ok", rendered)


if __name__ == "__main__":
    unittest.main()
