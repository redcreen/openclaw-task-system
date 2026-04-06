from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


main_task_adapter = load_runtime_module("main_task_adapter")


class MainTaskAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-main-adapter-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def build_context(self, request: str, **kwargs):
        return main_task_adapter.MainTaskContext(
            agent_id="main",
            session_key="agent:main:feishu:direct:test",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="oc_test_chat",
            user_request=request,
            **kwargs,
        )

    def test_decide_main_task_registers_long_task(self) -> None:
        context = self.build_context(
            "帮我排查这个问题并修复，再验证结果",
            estimated_steps=4,
            needs_verification=True,
        )
        decision = main_task_adapter.decide_main_task(context)
        self.assertTrue(decision.should_register)
        self.assertEqual(decision.reason, "long-task")

    def test_decide_main_task_observes_short_task(self) -> None:
        context = self.build_context("看一下")
        decision = main_task_adapter.decide_main_task(context)
        self.assertTrue(decision.should_register)
        self.assertEqual(decision.reason, "observed-task")

    def test_decide_main_task_marks_delayed_reply_as_continuation_task(self) -> None:
        context = self.build_context("1分钟后回复我ok1")
        decision = main_task_adapter.decide_main_task(context)
        self.assertTrue(decision.should_register)
        self.assertEqual(decision.reason, "continuation-task")
        self.assertIsNotNone(decision.continuation_plan)

    def test_decide_main_task_skips_bare_control_command(self) -> None:
        context = self.build_context("/status")
        decision = main_task_adapter.decide_main_task(context)
        self.assertFalse(decision.should_register)
        self.assertEqual(decision.reason, "control-command")

    def test_register_main_task_creates_running_task(self) -> None:
        context = self.build_context(
            "帮我整理配置并验证一下",
            estimated_steps=3,
            touches_multiple_files=True,
        )
        task = main_task_adapter.register_main_task(context, paths=self.paths)
        self.assertEqual(task.status, task_state_module.STATUS_RUNNING)
        self.assertEqual(task.agent_id, "main")

    def test_second_task_is_queued_until_first_finishes(self) -> None:
        first = main_task_adapter.register_main_task(
            self.build_context("帮我排查第一个较长任务", estimated_steps=4),
            paths=self.paths,
        )
        second = main_task_adapter.register_main_task(
            self.build_context("帮我排查第二个较长任务", estimated_steps=4),
            paths=self.paths,
        )

        self.assertEqual(first.status, task_state_module.STATUS_RUNNING)
        self.assertEqual(second.status, task_state_module.STATUS_QUEUED)

        finished = main_task_adapter.finish_main_task(first.task_id, result_summary="done", paths=self.paths)
        self.assertEqual(finished.status, task_state_module.STATUS_DONE)

        store = task_state_module.TaskStore(paths=self.paths)
        promoted = store.load_task(second.task_id)
        self.assertEqual(promoted.status, task_state_module.STATUS_RUNNING)
        self.assertEqual(promoted.meta["promotion_reason"], task_state_module.STATUS_DONE)
        self.assertEqual(promoted.meta["promoted_after"], first.task_id)

    def test_sync_finish_and_block_main_task(self) -> None:
        context = self.build_context(
            "继续处理这个任务",
            estimated_steps=3,
        )
        task = main_task_adapter.register_main_task(context, paths=self.paths)

        updated = main_task_adapter.sync_main_progress(
            task.task_id,
            progress_note="checked files",
            paths=self.paths,
        )
        self.assertEqual(updated.meta["last_progress_note"], "checked files")

        blocked = main_task_adapter.block_main_task(task.task_id, "waiting for approval", paths=self.paths)
        self.assertEqual(blocked.status, task_state_module.STATUS_BLOCKED)

        task2 = main_task_adapter.register_main_task(context, paths=self.paths)
        finished = main_task_adapter.finish_main_task(task2.task_id, result_summary="done", paths=self.paths)
        self.assertEqual(finished.status, task_state_module.STATUS_DONE)
        self.assertEqual(finished.meta["result_summary"], "done")

    def test_fail_main_task_marks_failed(self) -> None:
        context = self.build_context(
            "继续排查",
            estimated_steps=3,
        )
        task = main_task_adapter.register_main_task(context, paths=self.paths)
        failed = main_task_adapter.fail_main_task(task.task_id, "provider timeout", paths=self.paths)
        self.assertEqual(failed.status, task_state_module.STATUS_FAILED)
        self.assertEqual(failed.failure_reason, "provider timeout")

    def test_resume_queues_when_another_task_is_running(self) -> None:
        first = main_task_adapter.register_main_task(
            self.build_context("第一个任务", estimated_steps=4),
            paths=self.paths,
        )
        blocked = main_task_adapter.register_main_task(
            self.build_context("第二个任务", estimated_steps=4),
            paths=self.paths,
        )
        blocked = main_task_adapter.block_main_task(first.task_id, "waiting", paths=self.paths)
        self.assertEqual(blocked.status, task_state_module.STATUS_BLOCKED)

        resumed = main_task_adapter.resume_main_task(first.task_id, progress_note="继续", paths=self.paths)
        self.assertEqual(resumed.status, task_state_module.STATUS_QUEUED)
        self.assertEqual(resumed.meta["resume_target_status"], task_state_module.STATUS_QUEUED)

    def test_delayed_reply_text_auto_schedules_continuation(self) -> None:
        task = main_task_adapter.register_main_task(
            self.build_context("5分钟后回复我ok", requires_external_wait=True),
            paths=self.paths,
        )
        self.assertEqual(task.status, task_state_module.STATUS_PAUSED)
        self.assertEqual(task.meta["continuation_kind"], "delayed-reply")
        self.assertEqual(task.meta["continuation_payload"]["reply_text"], "ok")

    def test_delayed_reply_text_without_after_or_to_me_still_schedules_continuation(self) -> None:
        task = main_task_adapter.register_main_task(
            self.build_context("3分钟回复333"),
            paths=self.paths,
        )
        self.assertEqual(task.status, task_state_module.STATUS_PAUSED)
        self.assertEqual(task.meta["continuation_kind"], "delayed-reply")
        self.assertEqual(task.meta["continuation_payload"]["reply_text"], "333")

    def test_delayed_reply_text_tolerates_short_leading_noise(self) -> None:
        task = main_task_adapter.register_main_task(
            self.build_context("一3分钟回复333"),
            paths=self.paths,
        )
        self.assertEqual(task.status, task_state_module.STATUS_PAUSED)
        self.assertEqual(task.meta["continuation_kind"], "delayed-reply")
        self.assertEqual(task.meta["continuation_payload"]["reply_text"], "333")
