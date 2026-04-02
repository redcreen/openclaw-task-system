from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


openclaw_bridge = load_runtime_module("openclaw_bridge")
task_config = load_runtime_module("task_config")


class OpenClawBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-bridge-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def make_context(self, request: str, **kwargs):
        payload = {
            "agent_id": "main",
            "session_key": "feishu:main:chat:test",
            "channel": "feishu",
            "account_id": "feishu1-main",
            "chat_id": "oc_test_chat",
            "user_id": "ou_test_user",
            "user_request": request,
        }
        payload.update(kwargs)
        return openclaw_bridge.OpenClawInboundContext(
            **payload,
        )

    def test_register_inbound_task_skips_short_request(self) -> None:
        ctx = self.make_context("看一下")
        decision = openclaw_bridge.register_inbound_task(ctx, paths=self.paths)
        self.assertFalse(decision.should_register_task)
        self.assertIsNone(decision.task_id)

    def test_register_inbound_task_registers_long_request(self) -> None:
        ctx = self.make_context(
            "帮我排查这个问题并修复，再验证结果",
            estimated_steps=4,
            needs_verification=True,
        )
        decision = openclaw_bridge.register_inbound_task(ctx, paths=self.paths)
        self.assertTrue(decision.should_register_task)
        self.assertIsNotNone(decision.task_id)
        self.assertEqual(decision.task_status, task_state_module.STATUS_RUNNING)
        self.assertEqual(decision.queue_position, 1)
        self.assertEqual(decision.ahead_count, 0)

        store = task_state_module.TaskStore(paths=self.paths)
        task = store.load_task(decision.task_id)
        self.assertEqual(task.status, task_state_module.STATUS_RUNNING)
        self.assertEqual(task.chat_id, "oc_test_chat")

    def test_second_long_request_queues_until_first_completes(self) -> None:
        first = openclaw_bridge.register_inbound_task(
            self.make_context("第一个长任务", estimated_steps=4, needs_verification=True),
            paths=self.paths,
        )
        second = openclaw_bridge.register_inbound_task(
            self.make_context(
                "第二个长任务",
                estimated_steps=4,
                needs_verification=True,
                session_key="feishu:main:chat:test-2",
                chat_id="oc_test_chat_2",
            ),
            paths=self.paths,
        )
        assert first.task_id is not None
        assert second.task_id is not None

        store = task_state_module.TaskStore(paths=self.paths)
        self.assertEqual(store.load_task(first.task_id).status, task_state_module.STATUS_RUNNING)
        self.assertEqual(store.load_task(second.task_id).status, task_state_module.STATUS_QUEUED)
        self.assertEqual(second.task_status, task_state_module.STATUS_QUEUED)
        self.assertEqual(second.queue_position, 2)
        self.assertEqual(second.ahead_count, 1)

        openclaw_bridge.record_completed(first.task_id, result_summary="done", paths=self.paths)
        promoted = store.load_task(second.task_id)
        self.assertEqual(promoted.status, task_state_module.STATUS_RUNNING)
        self.assertEqual(promoted.meta["promoted_after"], first.task_id)

    def test_record_lifecycle_methods(self) -> None:
        ctx = self.make_context(
            "继续处理这个长任务",
            estimated_steps=3,
        )
        decision = openclaw_bridge.register_inbound_task(ctx, paths=self.paths)
        task_id = decision.task_id
        assert task_id is not None

        updated = openclaw_bridge.record_progress(
            task_id,
            progress_note="checked routing",
            paths=self.paths,
        )
        self.assertEqual(updated.meta["last_progress_note"], "checked routing")

        blocked = openclaw_bridge.record_blocked(task_id, "waiting for oauth", paths=self.paths)
        self.assertEqual(blocked.status, task_state_module.STATUS_BLOCKED)

        decision2 = openclaw_bridge.register_inbound_task(ctx, paths=self.paths)
        task_id2 = decision2.task_id
        assert task_id2 is not None
        failed = openclaw_bridge.record_failed(task_id2, "provider timeout", paths=self.paths)
        self.assertEqual(failed.status, task_state_module.STATUS_FAILED)

        decision3 = openclaw_bridge.register_inbound_task(ctx, paths=self.paths)
        task_id3 = decision3.task_id
        assert task_id3 is not None
        done = openclaw_bridge.record_completed(task_id3, result_summary="finished", paths=self.paths)
        self.assertEqual(done.status, task_state_module.STATUS_DONE)

    def test_register_inbound_task_respects_disabled_agent_config(self) -> None:
        ctx = self.make_context("帮我排查这个问题并修复，再验证结果", estimated_steps=4)
        config = task_config.TaskSystemConfig(
            enabled=True,
            storage_dir=self.paths.data_dir,
            agents={"main": task_config.AgentTaskConfig(enabled=False)},
        )
        decision = openclaw_bridge.register_inbound_task(ctx, paths=self.paths, config=config)
        self.assertFalse(decision.should_register_task)
        self.assertEqual(decision.classification_reason, "agent-disabled")

    def test_register_inbound_task_resumes_blocked_task(self) -> None:
        ctx = self.make_context(
            "帮我排查这个问题并修复，再验证结果",
            estimated_steps=4,
            needs_verification=True,
        )
        decision = openclaw_bridge.register_inbound_task(ctx, paths=self.paths)
        assert decision.task_id is not None
        blocked = openclaw_bridge.record_blocked(decision.task_id, "watchdog blocked", paths=self.paths)
        self.assertEqual(blocked.status, task_state_module.STATUS_BLOCKED)

        resumed = openclaw_bridge.register_inbound_task(
            self.make_context(
                "继续处理这个较长任务并分阶段同步",
                estimated_steps=4,
                needs_verification=True,
            ),
            paths=self.paths,
        )
        self.assertTrue(resumed.should_register_task)
        self.assertEqual(resumed.task_id, decision.task_id)
        self.assertEqual(resumed.classification_reason, "resume-blocked-task")

        store = task_state_module.TaskStore(paths=self.paths)
        task = store.load_task(decision.task_id)
        self.assertEqual(task.status, task_state_module.STATUS_RUNNING)

    def test_register_inbound_task_reports_scheduled_continuation(self) -> None:
        decision = openclaw_bridge.register_inbound_task(
            self.make_context(
                "1分钟后回复我ok",
                requires_external_wait=True,
            ),
            paths=self.paths,
        )
        assert decision.task_id is not None
        self.assertEqual(decision.task_status, task_state_module.STATUS_PAUSED)
        self.assertIsNotNone(decision.continuation_due_at)
