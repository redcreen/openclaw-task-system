from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.runtime_loader import load_runtime_module


growware_binding = load_runtime_module("growware_openclaw_binding")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _prepare_project(root: Path) -> None:
    _write_json(
        root / ".growware" / "project.json",
        {
            "projectRoot": str(root),
            "growware": {
                "daemon": {
                    "agentId": "growware",
                    "workspace": str(root),
                    "agentDir": str(root / ".agent"),
                }
            },
        },
    )
    _write_json(
        root / ".growware" / "channels.json",
        {
            "feedbackChannel": {
                "provider": "feishu",
                "accountId": "feishu6-chat",
                "roles": ["feedback", "approval", "notification"],
            }
        },
    )


class GrowwareOpenClawBindingTests(unittest.TestCase):
    def test_ensure_growware_binding_adds_agent_and_rewrites_feishu6_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _prepare_project(root)
            data = {
                "bindings": [
                    {
                        "agentId": "main",
                        "match": {"channel": "feishu", "accountId": "feishu6-chat"},
                    }
                ],
                "agents": {"list": []},
                "plugins": {"allow": [], "entries": {}},
            }

            updated, changed, report = growware_binding.ensure_growware_binding(data, project_root=root)

        self.assertTrue(changed)
        self.assertEqual(report["targetAgentId"], "growware")
        self.assertIn("openclaw-task-system", updated["plugins"]["allow"])
        self.assertEqual(updated["bindings"][0]["agentId"], "growware")
        self.assertTrue(any(agent["id"] == "growware" for agent in updated["agents"]["list"]))

    def test_run_binding_writes_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path = root / "openclaw.json"
            backup_dir = root / "backups"
            _prepare_project(root)
            config_path.write_text(json.dumps({"bindings": [], "agents": {"list": []}}, indent=2), encoding="utf-8")
            with mock.patch.object(growware_binding, "validate_live_config", return_value={"valid": True, "returncode": 0}):
                payload = growware_binding.run_binding(
                    config_path=config_path,
                    project_root=root,
                    write=True,
                    restart=False,
                    backup_dir=backup_dir,
                )

            written = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertTrue(payload["changed"])
        self.assertTrue(payload["validation"]["valid"])
        self.assertTrue(any(binding["agentId"] == "growware" for binding in written["bindings"]))


if __name__ == "__main__":
    unittest.main()
