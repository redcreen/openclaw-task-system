from __future__ import annotations

from dataclasses import dataclass
import unittest
from unittest.mock import patch

from runtime_loader import load_runtime_module


stable_acceptance = load_runtime_module("stable_acceptance")


@dataclass(frozen=True)
class _FakeCheck:
    name: str
    ok: bool
    detail: str


class StableAcceptanceTests(unittest.TestCase):
    def _run_clean_acceptance(self) -> dict[str, object]:
        with (
            patch.object(stable_acceptance, "run_checks", return_value=[_FakeCheck("plugin_root", True, "ok")]),
            patch.object(stable_acceptance, "run_plugin_smoke", return_value={"ok": True}),
            patch.object(stable_acceptance, "run_main_acceptance", return_value={"ok": True}),
            patch.object(stable_acceptance, "run_planning_acceptance", return_value={"ok": True}),
            patch.object(stable_acceptance, "run_same_session_routing_acceptance", return_value={"ok": True}),
            patch.object(stable_acceptance, "run_channel_acceptance", return_value={"ok": True}),
            patch.object(stable_acceptance, "run_main_ops_acceptance", return_value={"ok": True}),
            patch.object(stable_acceptance, "build_health_report", return_value={"status": "ok"}),
        ):
            return stable_acceptance.run_stable_acceptance()

    def test_run_stable_acceptance_succeeds(self) -> None:
        payload = self._run_clean_acceptance()
        self.assertTrue(payload["ok"])
        step_names = [step["step"] for step in payload["steps"]]
        self.assertEqual(
            step_names,
            [
                "plugin-doctor-checks",
                "plugin-smoke",
                "main-acceptance",
                "planning-acceptance",
                "same-session-routing-acceptance",
                "channel-acceptance",
                "main-ops-acceptance",
                "retry-failed-instructions",
                "health-report-clean",
            ],
        )

    def test_render_markdown_includes_health_step(self) -> None:
        payload = self._run_clean_acceptance()
        rendered = stable_acceptance.render_markdown(payload)
        self.assertIn("# Stable Acceptance", rendered)
        self.assertIn("health-report-clean: ok", rendered)


if __name__ == "__main__":
    unittest.main()
