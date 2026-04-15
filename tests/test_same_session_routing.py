from __future__ import annotations

import unittest

from runtime_loader import load_runtime_module, task_state_module


same_session_routing = load_runtime_module("same_session_routing")


class SameSessionRoutingTests(unittest.TestCase):
    def make_task(
        self,
        *,
        task_id: str = "task_active",
        status: str = "running",
        request: str = "Please rewrite this resume",
        monitor_state: str = "normal",
        meta: dict[str, object] | None = None,
    ) -> task_state_module.TaskState:
        return task_state_module.TaskState(
            task_id=task_id,
            run_id="run_1",
            agent_id="main",
            session_key="agent:main:feishu:direct:test",
            channel="feishu",
            chat_id="chat:test",
            task_label=request[:80],
            status=status,
            monitor_state=monitor_state,
            created_at="2026-04-11T12:00:00+08:00",
            updated_at="2026-04-11T12:00:00+08:00",
            last_user_visible_update_at="2026-04-11T12:00:00+08:00",
            last_internal_touch_at="2026-04-11T12:00:00+08:00",
            meta={"original_user_request": request, **(meta or {})},
        )

    def test_no_active_task_defaults_to_queueing(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="Check Hangzhou weather",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=None,
            recoverable_task=None,
            target_task=None,
        )
        self.assertEqual(decision["routing_status"], "decided")
        self.assertEqual(decision["classification"], "queueing")
        self.assertEqual(decision["execution_decision"], "queue-as-new-task")

    def test_same_session_plain_control_plane_rule(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="继续",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(),
            recoverable_task=None,
            target_task=None,
        )
        self.assertEqual(decision["routing_status"], "decided")
        self.assertEqual(decision["classification"], "control-plane")
        self.assertEqual(decision["execution_decision"], "handle-as-control-plane")
        self.assertEqual(decision["reason_code"], "same-session-control-plane-rule")

    def test_same_session_status_probe_rule(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="解决了么",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(request="帮我把今天的健康数据落到记录里"),
            recoverable_task=None,
            target_task=None,
        )
        self.assertEqual(decision["routing_status"], "decided")
        self.assertEqual(decision["classification"], "control-plane")
        self.assertEqual(decision["execution_decision"], "handle-as-control-plane")
        self.assertEqual(decision["reason_code"], "same-session-status-probe-rule")

    def test_collect_more_rule(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="我还没发完，先不要开始",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(status="queued"),
            recoverable_task=None,
            target_task=None,
        )
        self.assertEqual(decision["routing_status"], "decided")
        self.assertEqual(decision["classification"], "collect-more")
        self.assertEqual(decision["execution_decision"], "enter-collecting-window")

    def test_stale_observed_task_is_reused_as_prestart_takeover_target(self) -> None:
        observed = self.make_task(
            status="received",
            request="在么",
        )
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="帮我写一份简历，自己看情况写",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=None,
            recoverable_task=None,
            observed_task=observed,
            target_task=observed,
        )
        self.assertEqual(decision["routing_status"], "decided")
        self.assertTrue(decision["same_session_followup"])
        self.assertEqual(decision["classification"], "steering")
        self.assertEqual(decision["execution_decision"], "merge-before-start")
        self.assertEqual(decision["reason_code"], "stale-observed-task-takeover")
        self.assertEqual(decision["runtime_action"], "reuse-existing-task")
        self.assertEqual(decision["active_task_id"], observed.task_id)

    def test_actionable_observed_task_is_not_auto_taken_over(self) -> None:
        observed = self.make_task(
            status="received",
            request="查天气",
        )
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="帮我写一份简历，自己看情况写",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=None,
            recoverable_task=None,
            observed_task=observed,
            target_task=None,
        )
        self.assertFalse(decision["same_session_followup"])
        self.assertEqual(decision["classification"], "queueing")
        self.assertEqual(decision["execution_decision"], "queue-as-new-task")
        self.assertEqual(decision["reason_code"], "no-active-task-default-new-request")

    def test_obvious_independent_new_request_rule(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="Also check Hangzhou weather",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(request="Please rewrite this resume"),
            recoverable_task=None,
            target_task=None,
        )
        self.assertEqual(decision["routing_status"], "decided")
        self.assertEqual(decision["classification"], "queueing")
        self.assertEqual(decision["execution_decision"], "queue-as-new-task")
        self.assertEqual(decision["reason_code"], "same-session-obvious-independent-request")

    def test_explicit_same_task_followup_rule(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="需要记录啊",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(request="帮我把今天的健康数据落到记录里"),
            recoverable_task=None,
            target_task=None,
        )
        self.assertEqual(decision["routing_status"], "decided")
        self.assertEqual(decision["classification"], "steering")
        self.assertEqual(decision["execution_decision"], "interrupt-and-restart")
        self.assertEqual(decision["reason_code"], "same-session-explicit-followup-rule")

    def test_refinement_does_not_misclassify_as_independent_request(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="Also make it more conversational",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(request="Please rewrite this resume"),
            recoverable_task=None,
            target_task=None,
        )
        self.assertNotEqual(decision["reason_code"], "same-session-obvious-independent-request")
        self.assertEqual(decision["classification"], "steering")
        self.assertEqual(decision["execution_decision"], "interrupt-and-restart")
        self.assertEqual(decision["reason_code"], "active-task-safe-restart")

    def test_steering_queued_task_merges_before_start(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="Also make it more conversational",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(status="queued", request="Please rewrite this resume"),
            recoverable_task=None,
            target_task=None,
        )
        self.assertEqual(decision["classification"], "steering")
        self.assertEqual(decision["execution_decision"], "merge-before-start")
        self.assertEqual(decision["reason_code"], "active-task-not-started")

    def test_steering_running_task_with_side_effects_appends_next_step(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="Also make it more conversational",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(
                request="Please rewrite this resume",
                meta={"side_effects_started": True},
            ),
            recoverable_task=None,
            target_task=None,
        )
        self.assertEqual(decision["classification"], "steering")
        self.assertEqual(decision["active_task_stage"], "running-with-side-effects")
        self.assertEqual(decision["execution_decision"], "append-as-next-step")
        self.assertEqual(decision["reason_code"], "active-task-has-side-effects")

    def test_steering_paused_continuation_appends_non_destructively(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="Also make it more conversational",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(
                status="paused",
                request="Please rewrite this resume",
                meta={"continuation_kind": "delayed-reply"},
            ),
            recoverable_task=None,
            target_task=None,
        )
        self.assertEqual(decision["classification"], "steering")
        self.assertEqual(decision["active_task_stage"], "paused-continuation")
        self.assertEqual(decision["execution_decision"], "append-as-next-step")
        self.assertEqual(decision["reason_code"], "active-task-paused-non-destructive")

    def test_ambiguous_followup_invokes_classifier_and_uses_structured_result(self) -> None:
        captured: dict[str, object] = {}

        def classifier(payload: dict[str, object]) -> dict[str, object]:
            captured.update(payload)
            return {
                "classification": "steering",
                "confidence": 0.92,
                "needs_confirmation": False,
                "reason_code": "active-task-clarification",
                "reason_text": "The new message narrows the current task instead of creating a new goal.",
            }

        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="Target startup roles",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(request="Please rewrite this resume"),
            recoverable_task=None,
            target_task=None,
            classifier=classifier,
            queue_state={"running_count": 1, "queued_count": 2, "active_count": 3},
        )
        self.assertTrue(decision["classifier_invoked"])
        self.assertEqual(decision["decision_source"], "classifier")
        self.assertEqual(decision["classification"], "steering")
        self.assertEqual(decision["execution_decision"], "interrupt-and-restart")
        self.assertEqual(decision["reason_code"], "active-task-clarification")
        self.assertEqual(captured["active_task_stage"], "running-no-side-effects")
        self.assertEqual(captured["queue_state"], {"running_count": 1, "queued_count": 2, "active_count": 3})

    def test_low_confidence_classifier_falls_back_safely_before_task_start(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="Target startup roles",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(status="queued", request="Please rewrite this resume"),
            recoverable_task=None,
            target_task=None,
            classifier=lambda _: {
                "classification": "steering",
                "confidence": 0.31,
                "needs_confirmation": False,
                "reason_code": "uncertain-followup",
                "reason_text": "Not confident enough to decide.",
            },
        )
        self.assertTrue(decision["classifier_invoked"])
        self.assertTrue(decision["classifier_low_confidence"])
        self.assertEqual(decision["decision_source"], "classifier-fallback")
        self.assertEqual(decision["classification"], "steering")
        self.assertEqual(decision["execution_decision"], "merge-before-start")
        self.assertEqual(decision["reason_code"], "classifier-fallback-task-not-started")

    def test_classifier_error_falls_back_to_safe_queue_for_running_task(self) -> None:
        def classifier(_: dict[str, object]) -> dict[str, object]:
            raise RuntimeError("classifier timeout")

        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="Target startup roles",
            should_register_task=True,
            classification_reason="observed-task",
            active_task=self.make_task(request="Please rewrite this resume"),
            recoverable_task=None,
            target_task=None,
            classifier=classifier,
        )
        self.assertTrue(decision["classifier_invoked"])
        self.assertEqual(decision["decision_source"], "classifier-fallback")
        self.assertEqual(decision["classification"], "queueing")
        self.assertEqual(decision["execution_decision"], "queue-as-new-task")
        self.assertEqual(decision["reason_code"], "classifier-fallback-safe-queue")
        self.assertEqual(decision["classifier_error"], "classifier timeout")

    def test_collecting_window_active_keeps_buffering_followup_input(self) -> None:
        decision = same_session_routing.build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:test",
            user_request="第一条：整理目录",
            should_register_task=False,
            classification_reason="collecting-window-buffered",
            active_task=None,
            recoverable_task=None,
            target_task=None,
            collecting_state=True,
        )
        self.assertEqual(decision["routing_status"], "decided")
        self.assertEqual(decision["classification"], "collect-more")
        self.assertEqual(decision["execution_decision"], "enter-collecting-window")
        self.assertEqual(decision["reason_code"], "collecting-window-active")
