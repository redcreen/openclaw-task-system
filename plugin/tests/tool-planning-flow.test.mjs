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
    assert.match(result?.prependContext || "", /<task_user_content>/);

    const debugEvents = await readDebugEvents(runtimeRoot);
    const injected = debugEvents.find((entry) => entry.event === "before_prompt_build:planning-contract-injected");
    assert.equal(injected?.payload?.planningMode, "tool-first-after-first-ack");
    assert.equal(injected?.payload?.taskId, "task-123");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_prompt_build falls back to resolve-active when in-memory task binding is missing", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot({
    resolveActiveResponse: {
      found: true,
      task_id: "task-from-truth-source",
      status: "running",
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    const result = await plugin.beforePromptBuild(
      {
        prompt: "用户要我5分钟后回来同步结果。",
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

    assert.match(result?.prependContext || "", /current_task_id: task-from-truth-source/);
    const commands = await readHookCommands(callsPath);
    assert.ok(commands.includes("resolve-active"));
    const debugEvents = await readDebugEvents(runtimeRoot);
    const injected = debugEvents.find((entry) => entry.event === "before_prompt_build:planning-contract-injected");
    assert.equal(injected?.payload?.taskId, "task-from-truth-source");
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
      reply_to_id: "om_source_message",
      thread_id: "thread_source_message",
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
    assert.equal(createCall?.payload?.reply_to_id, "om_source_message");
    assert.equal(createCall?.payload?.thread_id, "thread_source_message");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("finalizing planned follow-up sends runtime-owned wd scheduling confirmation", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    finalizePlannedFollowupResponse: {
      ok: true,
      promise_fulfilled: true,
      status: "linked",
      followup_task_id: "task-followup-123",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      original_time_expression: "5分钟后",
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我查天气，5分钟后同步结果",
        body: "帮我查天气，5分钟后同步结果",
        channel: "feishu",
        senderId: "user-1",
        messageId: "om_source_message",
        threadId: "thread_source_message",
      },
      {
        sessionKey: "agent:main:feishu:acct-1:user-1",
        channelId: "feishu",
        conversationId: "chat-1",
        accountId: "acct-1",
        senderId: "user-1",
        agentId: "main",
        messageId: "om_source_message",
        threadId: "thread_source_message",
      },
    );

    const finalizeResult = await plugin.registeredTools.get("ts_finalize_planned_followup").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      plan_id: "plan-123",
    });

    assert.match(finalizeResult.content[0].text, /"promise_fulfilled": true/);
    assert.equal(sentMessages.length, 2);
    const confirmation = sentMessages[1];
    assert.match(confirmation?.text || "", /^\[wd\] 已安排妥当/);
    assert.equal(confirmation?.replyToId, "om_source_message");
    assert.equal(confirmation?.threadId, "thread_source_message");

    const debugEvents = await readDebugEvents(runtimeRoot);
    const delivered = debugEvents.find((entry) => entry.event === "followup-scheduled:sent");
    assert.equal(delivered?.payload?.schedulerDecision, "sent");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("message_sending only forwards structured user content after planning tools are used", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我查天气，然后 5 分钟后回来同步",
        body: "帮我查天气，然后 5 分钟后回来同步",
        channel: "feishu",
        senderId: "user-1",
        messageId: "om_source_message",
        threadId: "thread_source_message",
      },
      {
        sessionKey: "agent:main:feishu:acct-1:user-1",
        channelId: "feishu",
        conversationId: "chat-1",
        accountId: "acct-1",
        senderId: "user-1",
        agentId: "main",
        messageId: "om_source_message",
        threadId: "thread_source_message",
      },
    );

    await plugin.registeredTools.get("ts_attach_promise_guard").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      promise_summary: "5分钟后回来同步结果",
      followup_due_at: "2026-04-06T12:05:00+08:00",
    });
    const event = {
      content:
        "内部调度状态：已安排妥当。\n<task_user_content>[[reply_to_current]] 查完了。杭州现在 28°C。</task_user_content>",
    };
    await plugin.messageSending(event, {
      sessionKey: "agent:main:feishu:acct-1:user-1",
      channelId: "feishu",
      conversationId: "chat-1",
      accountId: "acct-1",
      senderId: "user-1",
      agentId: "main",
    });

    assert.equal(event.content, "[[reply_to_current]] 查完了。杭州现在 28°C。");
    const calls = await readHookCalls(callsPath);
    const progressCall = calls.find((entry) => entry.command === "progress-active");
    assert.equal(progressCall?.payload?.progress_note, "[[reply_to_current]] 查完了。杭州现在 28°C。");
    const debugEvents = await readDebugEvents(runtimeRoot);
    const extracted = debugEvents.find((entry) => entry.event === "message_sending:user-content-extracted");
    assert.equal(extracted?.payload?.reason, "task-user-content-block");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("message_sending suppresses unstructured content after planning tools are used", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我查天气，然后 5 分钟后回来同步",
        body: "帮我查天气，然后 5 分钟后回来同步",
        channel: "feishu",
        senderId: "user-1",
        messageId: "om_source_message",
        threadId: "thread_source_message",
      },
      {
        sessionKey: "agent:main:feishu:acct-1:user-1",
        channelId: "feishu",
        conversationId: "chat-1",
        accountId: "acct-1",
        senderId: "user-1",
        agentId: "main",
        messageId: "om_source_message",
        threadId: "thread_source_message",
      },
    );

    await plugin.registeredTools.get("ts_finalize_planned_followup").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      plan_id: "plan-123",
    });

    const event = {
      content: "[[reply_to_current]] 查完了。杭州现在 28°C。 我已经安排好了，5 分钟后回来同步。",
    };
    await plugin.messageSending(event, {
      sessionKey: "agent:main:feishu:acct-1:user-1",
      channelId: "feishu",
      conversationId: "chat-1",
      accountId: "acct-1",
      senderId: "user-1",
      agentId: "main",
    });

    assert.equal(event.content, "");
    const calls = await readHookCalls(callsPath);
    const progressCall = calls.find((entry) => entry.command === "progress-active");
    assert.equal(progressCall, undefined);
    const debugEvents = await readDebugEvents(runtimeRoot);
    const extracted = debugEvents.find((entry) => entry.event === "message_sending:user-content-extracted");
    assert.equal(extracted?.payload?.reason, "missing-task-user-content-block");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});
