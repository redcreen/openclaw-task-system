from __future__ import annotations

import json
import unittest

from runtime_loader import load_runtime_module


plugin_doctor = load_runtime_module("plugin_doctor")


class PluginDoctorTests(unittest.TestCase):
    def test_run_checks_returns_expected_names(self) -> None:
        checks = plugin_doctor.run_checks()
        names = {check.name for check in checks}
        self.assertIn("plugin_root", names)
        self.assertIn("hooks_script", names)
        self.assertIn("config_path", names)
        self.assertIn("installed_runtime_sync", names)

    def test_build_openclaw_config_snippet_contains_plugin_entry(self) -> None:
        snippet = plugin_doctor.build_openclaw_config_snippet()
        entries = snippet["plugins"]["entries"]
        self.assertIn("openclaw-task-system", entries)

    def test_render_json_is_valid_json(self) -> None:
        payload = json.loads(plugin_doctor.render_json())
        self.assertIn("checks", payload)
        self.assertIn("installCommand", payload)


if __name__ == "__main__":
    unittest.main()
