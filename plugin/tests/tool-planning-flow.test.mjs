import test from "node:test";
import assert from "node:assert/strict";

import {
  cleanupRuntime,
  createApi,
  createFakeRuntimeRoot,
  readDebugEvents,
  readHookCalls,
  readHookCommands,
  resetGlobalState,
} from "./helpers/task-system-plugin-test-helpers.mjs";

test("before_prompt_build injects planning contract and runtime context", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我继续处理",
        body: "帮我继续处理",
        channel: "feishu",
        senderId: "user-1",
      },
      {
        sessionKey: "agent:main:feishu:acct-1:user-1",
        channelId: "feishu",
        conversationId: "chat-1",
        accountId: "acct-1",
        senderId: "user-1",
        agentId: "main",
      },
    );

    const result = await plugin.beforePromptBuild(
      {
        prompt: "用户要我稍后回来时需要安排 follow-up。",
        messages: [],
      },
      {
        sessionKey: "agent:main:feishu:acct-1:user-1",
        channelId: "feishu",
        conversationId: "chat-1",
        accountId: "acct-1",
        senderId: "user-1",
        agentId: "main",
        trigger: "user",
      },
    );

    assert.match(result?.appendSystemContext || "", /Do not generate the first \[wd\]\./);
    assert.match(result?.prependContext || "", /current_task_id: task-123/);
    assert.match(result?.prependContext || "", /ts_create_followup_plan/);

    const debugEvents = await readDebugEvents(runtimeRoot);
    const injected = debugEvents.find((entry) => entry.event === "before_prompt_build:planning-contract-injected");
    assert.equal(injected?.payload?.planningMode, "tool-first-after-first-ack");
    assert.equal(injected?.payload?.taskId, "task-123");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("registered planning tools call runtime hooks", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    const attachResult = await plugin.registeredTools.get("ts_attach_promise_guard").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      promise_summary: "5分钟后回来同步结果",
      followup_due_at: "2026-04-06T12:05:00+08:00",
    });
    const createResult = await plugin.registeredTools.get("ts_create_followup_plan").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      followup_message: "5分钟后我回来同步结果",
      original_time_expression: "5分钟后",
      lead_request: "先查一下天气",
    });
    const scheduleResult = await plugin.registeredTools.get("ts_schedule_followup_from_plan").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      plan_id: "plan-123",
    });
    const finalizeResult = await plugin.registeredTools.get("ts_finalize_planned_followup").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      plan_id: "plan-123",
    });

    assert.match(attachResult.content[0].text, /"status": "armed"/);
    assert.match(createResult.content[0].text, /"plan_id": "plan-123"/);
    assert.match(scheduleResult.content[0].text, /"followup_task_id": "task-followup-123"/);
    assert.match(finalizeResult.content[0].text, /"status": "linked"/);

    const commands = await readHookCommands(callsPath);
    assert.deepEqual(commands, [
      "attach-promise-guard",
      "create-followup-plan",
      "schedule-followup-from-plan",
      "finalize-planned-followup",
    ]);
    const calls = await readHookCalls(callsPath);
    const createCall = calls.find((entry) => entry.command === "create-followup-plan");
    assert.equal(createCall?.payload?.followup_due_at, "2026-04-06T12:05:00+08:00");
    assert.equal(createCall?.payload?.followup_message, "5分钟后我回来同步结果");
    assert.equal(createCall?.payload?.followup_kind, "delayed-reply");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});
