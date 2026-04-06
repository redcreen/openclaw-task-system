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

    def test_parse_delayed_reply_request_detects_minutes(self) -> None:
        plan = task_policy.parse_delayed_reply_request("5分钟后回复我ok")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.kind, "delayed-reply")
        self.assertEqual(plan.wait_seconds, 300)
        self.assertEqual(plan.reply_text, "ok")

    def test_parse_delayed_reply_request_accepts_optional_after_and_to_me(self) -> None:
        plan = task_policy.parse_delayed_reply_request("3分钟回复333")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.wait_seconds, 180)
        self.assertEqual(plan.reply_text, "333")

    def test_parse_delayed_reply_request_tolerates_short_leading_noise(self) -> None:
        plan = task_policy.parse_delayed_reply_request("一3分钟回复333")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.wait_seconds, 180)
        self.assertEqual(plan.reply_text, "333")

    def test_parse_delayed_reply_request_does_not_match_embedded_prompt_text(self) -> None:
        plan = task_policy.parse_delayed_reply_request(
            "这是一个已经到达计划时间的延迟任务，请你现在继续执行。\n原始用户请求：1分钟后回复我ok1\n你现在必须直接回复以下最终内容：ok1"
        )
        self.assertIsNone(plan)

    def test_parse_post_run_delayed_followup_request_extracts_leading_work(self) -> None:
        plan = task_policy.parse_post_run_delayed_followup_request("你先查一下天气，然后5分钟后回复我信息；")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.wait_seconds, 300)
        self.assertEqual(plan.lead_request, "你先查一下天气")
        self.assertIn("你先查一下天气", plan.reply_text)
