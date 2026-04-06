from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from runtime_loader import load_runtime_module


configure_openclaw_plugin = load_runtime_module("configure_openclaw_plugin")


class ConfigureOpenClawPluginTests(unittest.TestCase):
    def test_apply_minimal_plugin_config_adds_allow_and_entry(self) -> None:
        payload, changed = configure_openclaw_plugin.apply_minimal_plugin_config({})
        self.assertTrue(changed)
        self.assertIn("plugins", payload)
        self.assertIn("openclaw-task-system", payload["plugins"]["allow"])
        self.assertTrue(payload["plugins"]["entries"]["openclaw-task-system"]["enabled"])

    def test_apply_minimal_plugin_config_is_idempotent(self) -> None:
        first, _ = configure_openclaw_plugin.apply_minimal_plugin_config({})
        second, changed = configure_openclaw_plugin.apply_minimal_plugin_config(first)
        self.assertFalse(changed)
        self.assertEqual(first, second)

    def test_configure_openclaw_plugin_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "openclaw.json"
            result = configure_openclaw_plugin.configure_openclaw_plugin(path=config_path, write=True)
            self.assertTrue(config_path.exists())
            self.assertTrue(result.plugin_enabled)
            data = json.loads(config_path.read_text(encoding="utf-8"))
            entry = data["plugins"]["entries"]["openclaw-task-system"]
            self.assertEqual(entry["config"]["defaultAgentId"], "main")
            self.assertTrue(entry["config"]["pythonBin"])

    def test_render_json_is_machine_readable(self) -> None:
        result = configure_openclaw_plugin.ConfigureResult(
            config_path=Path("/tmp/openclaw.json"),
            changed=True,
            plugin_enabled=True,
            allow_contains_plugin=True,
        )
        payload = json.loads(configure_openclaw_plugin.render_json(result))
        self.assertEqual(payload["pluginId"], "openclaw-task-system")
        self.assertTrue(payload["changed"])

    def test_detect_python_bin_prefers_python3_on_path(self) -> None:
        with mock.patch.object(configure_openclaw_plugin.shutil, "which", side_effect=lambda name: {
            "python3": "/opt/homebrew/bin/python3",
            "python": "/usr/bin/python",
        }.get(name)), mock.patch.object(configure_openclaw_plugin.sys, "executable", "/usr/bin/python3"):
            detected = configure_openclaw_plugin.detect_python_bin()
        self.assertTrue(detected.endswith("python3") or detected.endswith("python3.14"))


if __name__ == "__main__":
    unittest.main()
