from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.runtime_loader import load_runtime_module
from tests.growware_policy_fixtures import sync_policy


classifier_module = load_runtime_module("growware_feedback_classifier")


class GrowwareFeedbackClassifierTests(unittest.TestCase):
    def test_feedback_about_wording_is_classified_as_same_task_refinement(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sync_policy(root)

            result = classifier_module.classify(
                {
                    "new_message": "这个不是很自然语言，你把它改成正常人说话的方式。",
                    "active_task_summary": "调整 task system 的飞书反馈话术",
                    "recent_user_messages": ["把回复改自然一点"],
                },
                project_root=root,
            )

        self.assertEqual(result["classification"], "steering")
        self.assertEqual(result["execution_source"], "daemon-owned")
        self.assertEqual(result["reason_code"], "growware-feedback-wording-refinement")

    def test_feedback_with_new_goal_is_classified_as_new_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sync_policy(root)

            result = classifier_module.classify(
                {
                    "new_message": "另外再加一个 telegram 通知入口。",
                    "active_task_summary": "修正文案",
                    "recent_user_messages": ["先把飞书反馈通道接好"],
                },
                project_root=root,
            )

        self.assertEqual(result["classification"], "queueing")
        self.assertEqual(result["reason_code"], "growware-feedback-independent-request")


if __name__ == "__main__":
    unittest.main()
