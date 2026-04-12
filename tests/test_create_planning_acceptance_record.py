from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from io import StringIO
from contextlib import redirect_stdout
import json

from runtime_loader import load_runtime_module


create_planning_acceptance_record = load_runtime_module("create_planning_acceptance_record")


class CreatePlanningAcceptanceRecordTests(unittest.TestCase):
    def test_create_record_writes_dated_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)
            archive_dir = docs_dir / "archive"
            template_path = docs_dir / "planning_acceptance_record_template.md"
            template_path.write_text("# Planning Acceptance Record Template\n\n- 日期：\n", encoding="utf-8")
            with (
                patch.object(create_planning_acceptance_record, "DOCS_DIR", docs_dir),
                patch.object(create_planning_acceptance_record, "TEMPLATE_PATH", template_path),
            ):
                target_path = create_planning_acceptance_record.create_record(record_date="2026-04-10")

            self.assertEqual(target_path, archive_dir / "planning_acceptance_record_2026-04-10.md")
            content = target_path.read_text(encoding="utf-8")
            self.assertIn("# Planning Acceptance Record 2026-04-10", content)
            self.assertIn("本记录由 `create_planning_acceptance_record.py` 基于模板生成", content)
            self.assertIn("../planning_acceptance_record_template.md", content)
            self.assertIn("../planning_acceptance_runbook.md", content)
            self.assertEqual(content.count("# Planning Acceptance Record 2026-04-10"), 1)

    def test_create_record_rejects_existing_file_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)
            template_path = docs_dir / "planning_acceptance_record_template.md"
            template_path.write_text("# Planning Acceptance Record Template\n", encoding="utf-8")
            existing_path = docs_dir / "archive" / "planning_acceptance_record_2026-04-10.md"
            existing_path.parent.mkdir(parents=True, exist_ok=True)
            existing_path.write_text("existing\n", encoding="utf-8")
            with (
                patch.object(create_planning_acceptance_record, "DOCS_DIR", docs_dir),
                patch.object(create_planning_acceptance_record, "TEMPLATE_PATH", template_path),
            ):
                with self.assertRaises(FileExistsError):
                    create_planning_acceptance_record.create_record(record_date="2026-04-10")

    def test_main_can_print_next_steps(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)
            template_path = docs_dir / "planning_acceptance_record_template.md"
            template_path.write_text("# Planning Acceptance Record Template\n", encoding="utf-8")
            with (
                patch.object(create_planning_acceptance_record, "DOCS_DIR", docs_dir),
                patch.object(create_planning_acceptance_record, "TEMPLATE_PATH", template_path),
                patch("sys.argv", ["create_planning_acceptance_record.py", "--date", "2026-04-10", "--print-next-steps"]),
            ):
                buffer = StringIO()
                with redirect_stdout(buffer):
                    exit_code = create_planning_acceptance_record.main()

            output = buffer.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("archive/planning_acceptance_record_2026-04-10.md", output)
            self.assertIn("Run: python3 scripts/runtime/planning_acceptance.py --json", output)

    def test_main_can_emit_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)
            template_path = docs_dir / "planning_acceptance_record_template.md"
            template_path.write_text("# Planning Acceptance Record Template\n", encoding="utf-8")
            with (
                patch.object(create_planning_acceptance_record, "DOCS_DIR", docs_dir),
                patch.object(create_planning_acceptance_record, "TEMPLATE_PATH", template_path),
                patch("sys.argv", ["create_planning_acceptance_record.py", "--date", "2026-04-10", "--json"]),
            ):
                buffer = StringIO()
                with redirect_stdout(buffer):
                    exit_code = create_planning_acceptance_record.main()

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["record_date"], "2026-04-10")
            self.assertIn("archive/planning_acceptance_record_2026-04-10.md", payload["record_path"])
            self.assertIn("Run: python3 scripts/runtime/planning_acceptance.py --json", payload["next_steps"])
            self.assertEqual(payload["created"], True)

    def test_main_json_is_idempotent_when_record_already_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)
            template_path = docs_dir / "planning_acceptance_record_template.md"
            template_path.write_text("# Planning Acceptance Record Template\n", encoding="utf-8")
            existing_path = docs_dir / "archive" / "planning_acceptance_record_2026-04-10.md"
            existing_path.parent.mkdir(parents=True, exist_ok=True)
            existing_path.write_text("existing\n", encoding="utf-8")
            with (
                patch.object(create_planning_acceptance_record, "DOCS_DIR", docs_dir),
                patch.object(create_planning_acceptance_record, "TEMPLATE_PATH", template_path),
                patch("sys.argv", ["create_planning_acceptance_record.py", "--date", "2026-04-10", "--json"]),
            ):
                buffer = StringIO()
                with redirect_stdout(buffer):
                    exit_code = create_planning_acceptance_record.main()

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["created"], False)
            self.assertEqual(payload["record_path"], str(existing_path))


if __name__ == "__main__":
    unittest.main()
