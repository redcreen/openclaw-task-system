from __future__ import annotations

import json
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

    def test_register_inbound_task_observes_short_request(self) -> None:
        ctx = self.make_context("看一下")
        decision = openclaw_bridge.register_inbound_task(ctx, paths=self.paths, observe_only=True)
        self.assertTrue(decision.should_register_task)
        self.assertIsNotNone(decision.task_id)
        self.assertEqual(decision.classification_reason, "observed-task")
        self.assertEqual(decision.task_status, task_state_module.STATUS_RECEIVED)
        self.assertEqual(decision.queue_position, 1)
        self.assertEqual(decision.ahead_count, 0)

    def test_register_inbound_task_skips_bare_control_command(self) -> None:
        ctx = self.make_context("/status")
        decision = openclaw_bridge.register_inbound_task(ctx, paths=self.paths, observe_only=True)
        self.assertFalse(decision.should_register_task)
        self.assertIsNone(decision.task_id)
        self.assertEqual(decision.classification_reason, "control-command")

        store = task_state_module.TaskStore(paths=self.paths)
        self.assertEqual(store.find_inflight_tasks(agent_id="main"), [])

    def test_register_inbound_task_reports_queue_position_for_observed_tasks(self) -> None:
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
        observed = openclaw_bridge.register_inbound_task(
            self.make_context(
                "在么",
                session_key="feishu:main:chat:test-3",
                chat_id="oc_test_chat_3",
            ),
            paths=self.paths,
            observe_only=True,
        )
        self.assertEqual(first.task_status, task_state_module.STATUS_RUNNING)
        self.assertEqual(second.task_status, task_state_module.STATUS_QUEUED)
        self.assertEqual(observed.task_status, task_state_module.STATUS_RECEIVED)
        self.assertEqual(observed.queue_position, 3)
        self.assertEqual(observed.ahead_count, 2)
        self.assertEqual(observed.active_count, 3)
        self.assertEqual(observed.running_count, 1)
        self.assertEqual(observed.queued_count, 2)

    def test_observed_tasks_can_queue_with_no_running_tasks(self) -> None:
        first = openclaw_bridge.register_inbound_task(
            self.make_context("在么"),
            paths=self.paths,
            observe_only=True,
        )
        second = openclaw_bridge.register_inbound_task(
            self.make_context(
                "在么",
                session_key="feishu:main:chat:test-2",
                chat_id="oc_test_chat_2",
            ),
            paths=self.paths,
            observe_only=True,
        )
        self.assertEqual(first.task_status, task_state_module.STATUS_RECEIVED)
        self.assertEqual(first.queue_position, 1)
        self.assertEqual(first.ahead_count, 0)
        self.assertEqual(first.running_count, 0)
        self.assertEqual(first.active_count, 1)
        self.assertEqual(second.task_status, task_state_module.STATUS_RECEIVED)
        self.assertEqual(second.queue_position, 2)
        self.assertEqual(second.ahead_count, 1)
        self.assertEqual(second.running_count, 0)
        self.assertEqual(second.active_count, 2)
        self.assertEqual(second.queued_count, 2)

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

    def test_register_inbound_task_schedules_delayed_reply_continuation(self) -> None:
        decision = openclaw_bridge.register_inbound_task(
            self.make_context("1分钟后回复我ok1"),
            paths=self.paths,
            observe_only=True,
        )
        self.assertTrue(decision.should_register_task)
        self.assertIsNotNone(decision.task_id)
        self.assertEqual(decision.classification_reason, "continuation-task")
        self.assertEqual(decision.task_status, task_state_module.STATUS_PAUSED)
        self.assertIsNotNone(decision.continuation_due_at)

        store = task_state_module.TaskStore(paths=self.paths)
        task = store.load_task(decision.task_id)
        self.assertEqual(task.status, task_state_module.STATUS_PAUSED)
        self.assertEqual(task.meta["continuation_kind"], "delayed-reply")
        self.assertEqual(task.meta["continuation_payload"]["reply_text"], "ok1")

    def test_register_inbound_task_keeps_compound_followup_as_running_task(self) -> None:
        decision = openclaw_bridge.register_inbound_task(
            self.make_context("你先查一下天气，然后5分钟后回复我信息；", estimated_steps=2),
            paths=self.paths,
        )
        self.assertTrue(decision.should_register_task)
        self.assertEqual(decision.classification_reason, "long-task")
        self.assertEqual(decision.task_status, task_state_module.STATUS_RUNNING)
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.load_task(decision.task_id)
        plan = task.meta.get("post_run_continuation_plan")
        self.assertIsInstance(plan, dict)
        assert isinstance(plan, dict)
        self.assertEqual(plan["wait_seconds"], 300)

    def test_register_inbound_task_estimates_wait_from_recent_done_tasks(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        done = store.register_task(
            agent_id="main",
            session_key="feishu:main:chat:history",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="oc_history",
            user_id="ou_history",
            task_label="历史完成任务",
        )
        started = store.start_task(done.task_id)
        archived = store.complete_task(started.task_id, archive=True)
        archive_path = self.paths.archive_dir / f"{archived.task_id}.json"
        payload = json.loads(archive_path.read_text(encoding="utf-8"))
        payload["created_at"] = "2026-04-04T10:00:00+08:00"
        payload["started_at"] = "2026-04-04T10:00:10+08:00"
        payload["updated_at"] = "2026-04-04T10:00:40+08:00"
        task_state_module.atomic_write_json(archive_path, payload)

        running = openclaw_bridge.register_inbound_task(
            self.make_context("第一个长任务", estimated_steps=4, needs_verification=True),
            paths=self.paths,
        )
        queued = openclaw_bridge.register_inbound_task(
            self.make_context(
                "第二个长任务",
                estimated_steps=4,
                needs_verification=True,
                session_key="feishu:main:chat:test-2",
                chat_id="oc_test_chat_2",
            ),
            paths=self.paths,
        )

        self.assertEqual(running.task_status, task_state_module.STATUS_RUNNING)
        self.assertEqual(running.estimated_wait_seconds, 30)
        self.assertEqual(queued.task_status, task_state_module.STATUS_QUEUED)
        self.assertEqual(queued.estimated_wait_seconds, 60)

    def test_observed_task_does_not_reuse_long_task_wait_estimate(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        done = store.register_task(
            agent_id="main",
            session_key="feishu:main:chat:history",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="oc_history",
            user_id="ou_history",
            task_label="历史完成任务",
        )
        started = store.start_task(done.task_id)
        archived = store.complete_task(started.task_id, archive=True)
        archive_path = self.paths.archive_dir / f"{archived.task_id}.json"
        payload = json.loads(archive_path.read_text(encoding="utf-8"))
        payload["created_at"] = "2026-04-04T10:00:00+08:00"
        payload["started_at"] = "2026-04-04T10:00:10+08:00"
        payload["updated_at"] = "2026-04-04T10:00:40+08:00"
        task_state_module.atomic_write_json(archive_path, payload)

        observed = openclaw_bridge.register_inbound_task(
            self.make_context("在么"),
            paths=self.paths,
            observe_only=True,
        )

        self.assertEqual(observed.classification_reason, "observed-task")
        self.assertIsNone(observed.estimated_wait_seconds)

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
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.observe_task(
            agent_id="main",
            session_key="feishu:main:chat:test",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="oc_test_chat",
            user_id="ou_test_user",
            task_label="scheduled continuation",
            meta={"source": "test"},
        )
        scheduled = store.schedule_continuation(
            task.task_id,
            continuation_kind="delayed-reply",
            due_at="2099-01-01T00:00:00+08:00",
            payload={"reply_text": "ok", "wait_seconds": 60},
            reason="scheduled continuation wait",
        )
        decision = openclaw_bridge.register_inbound_task(self.make_context("继续"), paths=self.paths)
        assert decision.task_id is not None
        self.assertEqual(decision.task_id, scheduled.task_id)
        self.assertEqual(decision.task_status, task_state_module.STATUS_PAUSED)
        self.assertIsNotNone(decision.continuation_due_at)

    def test_register_inbound_task_keeps_future_continuation_paused(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.observe_task(
            agent_id="main",
            session_key="feishu:main:chat:test",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="oc_test_chat",
            user_id="ou_test_user",
            task_label="scheduled continuation",
            meta={"source": "test"},
        )
        first = store.schedule_continuation(
            task.task_id,
            continuation_kind="delayed-reply",
            due_at="2099-01-01T00:00:00+08:00",
            payload={"reply_text": "ok1", "wait_seconds": 60},
            reason="scheduled continuation wait",
        )

        second = openclaw_bridge.register_inbound_task(
            self.make_context(
                "继续处理",
            ),
            paths=self.paths,
        )
        self.assertEqual(second.task_id, first.task_id)
        self.assertEqual(second.classification_reason, "scheduled-continuation")
        self.assertEqual(second.task_status, task_state_module.STATUS_PAUSED)

    def test_register_inbound_task_creates_new_delayed_reply_when_future_continuation_exists(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.observe_task(
            agent_id="main",
            session_key="feishu:main:chat:test",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="oc_test_chat",
            user_id="ou_test_user",
            task_label="existing delayed reply",
            meta={"source": "test"},
        )
        first = store.schedule_continuation(
            task.task_id,
            continuation_kind="delayed-reply",
            due_at="2099-01-01T00:00:00+08:00",
            payload={"reply_text": "ok1", "wait_seconds": 60},
            reason="scheduled continuation wait",
        )

        second = openclaw_bridge.register_inbound_task(
            self.make_context("2分钟后回复我222"),
            paths=self.paths,
            observe_only=True,
        )
        assert second.task_id is not None
        self.assertNotEqual(second.task_id, first.task_id)
        self.assertEqual(second.classification_reason, "continuation-task")
        self.assertEqual(second.task_status, task_state_module.STATUS_PAUSED)

        registered = store.load_task(second.task_id)
        self.assertEqual(registered.meta["continuation_payload"]["reply_text"], "222")
