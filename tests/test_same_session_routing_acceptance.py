from __future__ import annotations

import unittest

from runtime_loader import load_runtime_module


same_session_routing_acceptance = load_runtime_module("same_session_routing_acceptance")


class SameSessionRoutingAcceptanceTests(unittest.TestCase):
    def test_run_same_session_routing_acceptance_succeeds(self) -> None:
        payload = same_session_routing_acceptance.run_same_session_routing_acceptance()
        self.assertTrue(payload["ok"])
        self.assertEqual(
            [step["step"] for step in payload["steps"]],
            [
                "same-session-steering-prestart",
                "same-session-steering-safe-restart",
                "same-session-queueing-and-control-plane",
                "same-session-stale-observed-takeover",
                "same-session-classifier-trigger",
                "same-session-collecting-window",
            ],
        )

    def test_render_markdown_includes_collecting_window_step(self) -> None:
        payload = same_session_routing_acceptance.run_same_session_routing_acceptance()
        rendered = same_session_routing_acceptance.render_markdown(payload)
        self.assertIn("# Same-Session Routing Acceptance", rendered)
        self.assertIn("same-session-stale-observed-takeover: ok", rendered)
        self.assertIn("same-session-collecting-window: ok", rendered)
