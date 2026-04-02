from __future__ import annotations

import unittest

from runtime_loader import load_runtime_module


task_policy = load_runtime_module("task_policy")
task_config = load_runtime_module("task_config")


class TaskPolicyTests(unittest.TestCase):
    def test_short_simple_request_is_not_long_task(self) -> None:
        result = task_policy.classify_main_task("看下这个")
        self.assertFalse(result.is_long_task)
        self.assertEqual(result.confidence, "low")

    def test_multi_step_request_is_long_task(self) -> None:
        result = task_policy.classify_main_task(
            "帮我排查这个问题并修复，再顺手验证一下",
            estimated_steps=4,
            needs_verification=True,
        )
        self.assertTrue(result.is_long_task)
        self.assertIn("multi-step", result.reasons)

    def test_external_wait_marks_as_long_task(self) -> None:
        result = task_policy.classify_main_task(
            "继续跟这个问题",
            requires_external_wait=True,
        )
        self.assertTrue(result.is_long_task)
        self.assertIn("external-wait", result.reasons)

    def test_custom_thresholds_can_promote_short_request(self) -> None:
        policy = task_config.ClassificationConfig(
            min_request_length=4,
            min_reason_count=1,
            estimated_steps_threshold=2,
            keywords=("看",),
        )
        result = task_policy.classify_main_task(
            "看这个",
            min_request_length=policy.min_request_length,
            min_reason_count=policy.min_reason_count,
            estimated_steps_threshold=policy.estimated_steps_threshold,
            keywords=policy.keywords,
        )
        self.assertTrue(result.is_long_task)
        self.assertEqual(result.confidence, "medium")
