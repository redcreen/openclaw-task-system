from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime_loader import load_runtime_module


plugin_install_drift = load_runtime_module("plugin_install_drift")


class PluginInstallDriftTests(unittest.TestCase):
    def test_build_install_drift_report_detects_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            installed_dir = root / "installed"
            source_dir.mkdir()
            installed_dir.mkdir()
            (source_dir / "a.py").write_text("", encoding="utf-8")
            (source_dir / "b.py").write_text("", encoding="utf-8")
            (installed_dir / "a.py").write_text("", encoding="utf-8")
            with (
                patch.object(plugin_install_drift, "SOURCE_RUNTIME_DIR", source_dir),
                patch.object(plugin_install_drift, "INSTALLED_RUNTIME_DIR", installed_dir),
            ):
                payload = plugin_install_drift.build_install_drift_report()

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["missing_in_installed"], ["b.py"])
            self.assertEqual(payload["extra_in_installed"], [])

    def test_render_markdown_reports_missing_files(self) -> None:
        rendered = plugin_install_drift.render_markdown(
            {
                "ok": False,
                "installed_runtime_exists": True,
                "source_runtime_dir": "/tmp/source",
                "installed_runtime_dir": "/tmp/installed",
                "source_file_count": 2,
                "installed_file_count": 1,
                "missing_in_installed": ["b.py"],
                "extra_in_installed": [],
            }
        )
        self.assertIn("# Plugin Install Drift", rendered)
        self.assertIn("missing_in_installed: b.py", rendered)


if __name__ == "__main__":
    unittest.main()
