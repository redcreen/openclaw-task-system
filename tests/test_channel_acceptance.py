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


if __name__ == "__main__":
    unittest.main()
