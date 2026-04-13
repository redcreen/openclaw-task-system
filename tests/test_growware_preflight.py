from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.runtime_loader import load_runtime_module


growware_preflight = load_runtime_module("growware_preflight")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class GrowwarePreflightTests(unittest.TestCase):
    def test_preflight_passes_for_valid_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_json(
                root / ".growware" / "project.json",
                {
                    "projectRoot": str(root),
                    "growware": {"daemon": {"agentId": "growware"}},
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
            for relative in (
                "contracts/feedback-event.v1.json",
                "contracts/incident-record.v1.json",
                "policies/judge.v1.json",
                "policies/deploy-gate.v1.json",
                "ops/daemon-interface.v1.json",
            ):
                _write_json(root / ".growware" / relative, {"ok": True})

            payload = growware_preflight.build_preflight_report(root)

        self.assertTrue(payload["ok"])

    def test_preflight_fails_when_feedback_channel_does_not_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_json(
                root / ".growware" / "project.json",
                {
                    "projectRoot": str(root),
                    "growware": {"daemon": {"agentId": "growware"}},
                },
            )
            _write_json(
                root / ".growware" / "channels.json",
                {
                    "feedbackChannel": {
                        "provider": "telegram",
                        "accountId": "fallback",
                        "roles": ["feedback"],
                    }
                },
            )
            for relative in (
                "contracts/feedback-event.v1.json",
                "contracts/incident-record.v1.json",
                "policies/judge.v1.json",
                "policies/deploy-gate.v1.json",
                "ops/daemon-interface.v1.json",
            ):
                _write_json(root / ".growware" / relative, {"ok": True})

            payload = growware_preflight.build_preflight_report(root)

        self.assertFalse(payload["ok"])
        self.assertTrue(any(check["check"] == "feedback-channel" and not check["ok"] for check in payload["checks"]))


if __name__ == "__main__":
    unittest.main()
