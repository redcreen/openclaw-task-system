from __future__ import annotations

import unittest

from runtime_loader import load_runtime_module


channel_acceptance = load_runtime_module("channel_acceptance")


class ChannelAcceptanceTests(unittest.TestCase):
    def test_build_channel_acceptance_summary_reports_phase_complete(self) -> None:
        summary = channel_acceptance.build_channel_acceptance_summary()
        self.assertEqual(summary["schema"], "openclaw.task-system.channel-acceptance.v1")
        self.assertEqual(summary["phase_status"], "complete")
        self.assertTrue(summary["phase_complete"])
        self.assertTrue(summary["channels_meet_current_contract"])
        self.assertIn("feishu", summary["validated_channels"])
        self.assertIn("telegram", summary["bounded_channels"])
        self.assertIn("webchat", summary["bounded_channels"])

    def test_build_channel_acceptance_summary_can_focus_channel(self) -> None:
        summary = channel_acceptance.build_channel_acceptance_summary(channel="feishu")
        self.assertEqual(summary["focus_channel"], "feishu")
        self.assertEqual(summary["focus_rollout_status"], "validated")
        self.assertEqual(summary["channel_count"], 1)
        self.assertEqual(summary["entries"][0]["acceptance_scope"], "receive-side-contract")

    def test_render_channel_acceptance_summary_includes_phase_status(self) -> None:
        rendered = channel_acceptance.render_channel_acceptance_summary(
            channel_acceptance.build_channel_acceptance_summary()
        )
        self.assertIn("# Channel Acceptance", rendered)
        self.assertIn("- phase_status: complete", rendered)
        self.assertIn("feishu", rendered)

    def test_run_channel_acceptance_covers_sample_contracts(self) -> None:
        payload = channel_acceptance.run_channel_acceptance()

        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["steps"]), 4)
        self.assertTrue(all(step["ok"] for step in payload["steps"]))

    def test_render_markdown_includes_sample_steps(self) -> None:
        rendered = channel_acceptance.render_markdown(channel_acceptance.run_channel_acceptance())

        self.assertIn("# Channel Acceptance Samples", rendered)
        self.assertIn("- channel-matrix-contract: ok", rendered)
        self.assertIn("- feishu-session-focus-contract: ok", rendered)
        self.assertIn("- telegram-session-focus-contract: ok", rendered)
        self.assertIn("- observed-channel-fallback-contract: ok", rendered)


if __name__ == "__main__":
    unittest.main()
