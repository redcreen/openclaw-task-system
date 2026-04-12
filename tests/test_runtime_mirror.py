from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module


runtime_mirror = load_runtime_module("runtime_mirror")


class RuntimeMirrorTests(unittest.TestCase):
    def test_build_runtime_mirror_report_detects_missing_extra_and_changed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            canonical = root / "canonical"
            mirror = root / "mirror"
            canonical.mkdir()
            mirror.mkdir()
            (canonical / "a.py").write_text("print('a')\n", encoding="utf-8")
            (canonical / "b.py").write_text("print('b')\n", encoding="utf-8")
            (mirror / "a.py").write_text("print('different')\n", encoding="utf-8")
            (mirror / "c.py").write_text("print('extra')\n", encoding="utf-8")

            report = runtime_mirror.build_runtime_mirror_report(
                canonical_dir=canonical,
                mirror_dir=mirror,
            )

        self.assertFalse(report["ok"])
        self.assertEqual(report["missing_in_mirror"], ["b.py"])
        self.assertEqual(report["extra_in_mirror"], ["c.py"])
        self.assertEqual(report["changed_files"], ["a.py"])

    def test_sync_runtime_mirror_copies_canonical_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            canonical = root / "canonical"
            mirror = root / "mirror"
            canonical.mkdir()
            (canonical / "nested").mkdir()
            (canonical / "a.py").write_text("print('a')\n", encoding="utf-8")
            (canonical / "nested" / "b.py").write_text("print('b')\n", encoding="utf-8")

            payload = runtime_mirror.sync_runtime_mirror(
                canonical_dir=canonical,
                mirror_dir=mirror,
            )

            self.assertTrue(payload["ok"])
            self.assertTrue((mirror / "a.py").exists())
            self.assertTrue((mirror / "nested" / "b.py").exists())


if __name__ == "__main__":
    unittest.main()
