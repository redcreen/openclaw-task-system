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
  waitForDebugEvent,
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

    assert.match(result?.appendSystemContext || "", /Do not send the first \[wd\]/);
    assert.match(result?.prependContext || "", /task: task-123/);
    assert.match(result?.prependContext || "", /ts_create_followup_plan/);
    assert.match(result?.prependContext || "", /runtime chooses none \/ immediate-summary \/ full-answer/);
    assert.doesNotMatch(result?.prependContext || "", /<task_user_content>/);
    assert.ok((result?.prependContext || "").length < 800);
    assert.ok((result?.appendSystemContext || "").length < 1200);

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

    assert.match(result?.prependContext || "", /task: task-from-truth-source/);
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
      followup_summary: "5分钟后同步天气结果",
      main_user_content_mode: "none",
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
      "resolve-active",
      "attach-promise-guard",
      "create-followup-plan",
      "schedule-followup-from-plan",
      "finalize-planned-followup",
    ]);
    const calls = await readHookCalls(callsPath);
    const createCall = calls.find((entry) => entry.command === "create-followup-plan");
    assert.equal(createCall?.payload?.followup_due_at, "2026-04-06T12:05:00+08:00");
    assert.equal(createCall?.payload?.followup_message, "5分钟后我回来同步结果");
    assert.equal(createCall?.payload?.followup_summary, "5分钟后同步天气结果");
    assert.equal(createCall?.payload?.main_user_content_mode, "none");
    assert.equal(createCall?.payload?.followup_kind, "delayed-reply");
    assert.equal(createCall?.payload?.reply_to_id, "om_source_message");
    assert.equal(createCall?.payload?.thread_id, "thread_source_message");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("finalizing planned follow-up sends runtime-owned wd scheduling confirmation", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot({
    finalizePlannedFollowupResponse: {
      ok: true,
      promise_fulfilled: true,
      status: "linked",
      followup_task_id: "task-followup-123",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      original_time_expression: "5分钟后",
      followup_summary: "5分钟后同步天气结果",
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
    assert.equal(confirmation?.text, "[wd] 已安排妥当：5分钟后同步天气结果。");
    assert.equal(confirmation?.replyToId, "om_source_message");
    assert.equal(confirmation?.threadId, "thread_source_message");

    const debugEvents = await readDebugEvents(runtimeRoot);
    const delivered = debugEvents.find((entry) => entry.event === "followup-scheduled:sent");
    assert.equal(delivered?.payload?.schedulerDecision, "sent");
    const commands = await readHookCommands(callsPath);
    assert.ok(commands.includes("sync-followup-reply-target"));
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("finalizing planned follow-up sends scheduling confirmation after binding is recovered from truth source", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot({
    finalizePlannedFollowupResponse: {
      ok: true,
      promise_fulfilled: true,
      status: "linked",
      followup_task_id: "task-followup-123",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      original_time_expression: "5分钟后",
      followup_summary: "5分钟后同步天气结果",
    },
    resolveActiveResponse: {
      found: true,
      task_id: "task-123",
      status: "running",
      channel: "feishu",
      account_id: "acct-1",
      chat_id: "chat-1",
      reply_to_id: "om_source_message",
      thread_id: "thread_source_message",
      require_structured_user_content: true,
      main_user_content_mode: "none",
      task: {
        task_id: "task-123",
        channel: "feishu",
        account_id: "acct-1",
        chat_id: "chat-1",
      },
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    const finalizeResult = await plugin.registeredTools.get("ts_finalize_planned_followup").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      plan_id: "plan-123",
    });

    assert.match(finalizeResult.content[0].text, /"promise_fulfilled": true/);
    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0]?.text, "[wd] 已安排妥当：5分钟后同步天气结果。");
    assert.equal(sentMessages[0]?.replyToId, "om_source_message");
    assert.equal(sentMessages[0]?.threadId, "thread_source_message");

    const debugEvents = await readDebugEvents(runtimeRoot);
    const recovered = debugEvents.find((entry) => entry.event === "active-task-binding:recovered");
    assert.equal(recovered?.payload?.taskId, "task-123");
    const delivered = debugEvents.find((entry) => entry.event === "followup-scheduled:sent");
    assert.equal(delivered?.payload?.schedulerDecision, "sent");
    const commands = await readHookCommands(callsPath);
    assert.ok(commands.includes("resolve-active"));
    assert.ok(commands.includes("sync-followup-reply-target"));
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("finalizing planned follow-up falls back to runtime-derived summary when explicit summary is absent", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    finalizePlannedFollowupResponse: {
      ok: true,
      promise_fulfilled: true,
      status: "linked",
      followup_task_id: "task-followup-123",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      original_time_expression: "5分钟后",
      followup_summary: "5分钟后回来继续汇报天气结果",
    },
    resolveActiveResponse: {
      found: true,
      task_id: "task-123",
      status: "running",
      channel: "feishu",
      account_id: "acct-1",
      chat_id: "chat-1",
      reply_to_id: "om_source_message",
      thread_id: "thread_source_message",
      require_structured_user_content: true,
      main_user_content_mode: "none",
      task: {
        task_id: "task-123",
        channel: "feishu",
        account_id: "acct-1",
        chat_id: "chat-1",
      },
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    const finalizeResult = await plugin.registeredTools.get("ts_finalize_planned_followup").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      plan_id: "plan-123",
    });

    assert.match(finalizeResult.content[0].text, /"promise_fulfilled": true/);
    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0]?.text, "[wd] 已安排妥当：5分钟后回来继续汇报天气结果。");
    assert.equal(sentMessages[0]?.replyToId, "om_source_message");
    assert.equal(sentMessages[0]?.threadId, "thread_source_message");
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

    await plugin.registeredTools.get("ts_create_followup_plan").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      followup_message: "5分钟后回来同步结果",
      main_user_content_mode: "full-answer",
    });
    const event = {
      content: "内部调度状态：已安排妥当。\n[[reply_to_current]] 查完了。杭州现在 28°C。",
    };
    const result = await plugin.messageSending(event, {
      sessionKey: "agent:main:feishu:acct-1:user-1",
      channelId: "feishu",
      conversationId: "chat-1",
      accountId: "acct-1",
      senderId: "user-1",
      agentId: "main",
    });

    assert.equal(event.content, "[[reply_to_current]] 查完了。 杭州现在 28°C。");
    assert.equal(result?.content, "[[reply_to_current]] 查完了。 杭州现在 28°C。");
    assert.equal(result?.cancel, undefined);
    const calls = await readHookCalls(callsPath);
    const progressCall = calls.find((entry) => entry.command === "progress-active");
    assert.equal(progressCall?.payload?.progress_note, "[[reply_to_current]] 查完了。 杭州现在 28°C。");
    const debugEvents = await readDebugEvents(runtimeRoot);
    const extracted = debugEvents.find((entry) => entry.event === "message_sending:user-content-extracted");
    assert.equal(extracted?.payload?.reason, "mode-driven-pass");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("message_sending suppresses immediate business content when main_user_content_mode is none", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "宁波天气明天2分钟后告诉我",
        body: "宁波天气明天2分钟后告诉我",
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

    await plugin.registeredTools.get("ts_create_followup_plan").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      followup_message: "2分钟后我回来同步明天天气",
      followup_summary: "2分钟后同步明天天气",
      main_user_content_mode: "none",
    });

    const event = {
      content: "查好了。明天宁波 20°C。",
    };
    const result = await plugin.messageSending(event, {
      sessionKey: "agent:main:feishu:acct-1:user-1",
      channelId: "feishu",
      conversationId: "chat-1",
      accountId: "acct-1",
      senderId: "user-1",
      agentId: "main",
    });

    assert.equal(event.content, "");
    assert.equal(result?.content, "");
    assert.equal(result?.cancel, true);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("decision case: plain immediate query without planning passes through as a normal answer", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    const event = {
      content: "杭州现在 28°C，宁波现在 22°C。",
    };
    const result = await plugin.messageSending(event, {
      sessionKey: "agent:main:feishu:acct-1:user-1",
      channelId: "feishu",
      conversationId: "chat-1",
      accountId: "acct-1",
      senderId: "user-1",
      agentId: "main",
    });

    assert.equal(event.content, "杭州现在 28°C，宁波现在 22°C。");
    assert.equal(result?.content, undefined);
    assert.equal(result?.cancel, undefined);

    const calls = await readHookCalls(callsPath);
    const progressCall = calls.find((entry) => entry.command === "progress-active");
    assert.equal(progressCall?.payload?.progress_note, "杭州现在 28°C，宁波现在 22°C。");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("decision case: future-first request uses planning state to suppress current business content", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "先查杭州和宁波天气，2分钟后告诉我杭州，3分钟后告诉我宁波",
        body: "先查杭州和宁波天气，2分钟后告诉我杭州，3分钟后告诉我宁波",
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
      promise_summary: "2分钟后同步杭州，3分钟后同步宁波",
      followup_due_at: "2026-04-06T12:05:00+08:00",
    });
    await plugin.registeredTools.get("ts_create_followup_plan").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      followup_message: "2分钟后回来同步杭州天气",
      followup_summary: "2分钟后同步杭州天气",
      main_user_content_mode: "none",
    });

    const event = {
      content: "杭州现在 28°C，宁波现在 22°C。",
    };
    const result = await plugin.messageSending(event, {
      sessionKey: "agent:main:feishu:acct-1:user-1",
      channelId: "feishu",
      conversationId: "chat-1",
      accountId: "acct-1",
      senderId: "user-1",
      agentId: "main",
    });

    assert.equal(event.content, "");
    assert.equal(result?.content, "");
    assert.equal(result?.cancel, true);

    const debugEvents = await readDebugEvents(runtimeRoot);
    const suppressed = debugEvents.find((entry) => entry.event === "message_sending:user-content-suppressed");
    assert.equal(suppressed?.payload?.reason, "main-user-content-mode-none");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("decision case: planned task with full-answer mode may send the immediate now-part answer", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "先查杭州天气现在告诉我，宁波3分钟后再告诉我",
        body: "先查杭州天气现在告诉我，宁波3分钟后再告诉我",
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

    await plugin.registeredTools.get("ts_create_followup_plan").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      followup_message: "3分钟后回来同步宁波天气",
      followup_summary: "3分钟后同步宁波天气",
      main_user_content_mode: "full-answer",
    });

    const event = {
      content:
        "内部调度状态：已安排妥当。\n杭州现在 28°C；宁波我 3 分钟后回来同步。",
    };
    const result = await plugin.messageSending(event, {
      sessionKey: "agent:main:feishu:acct-1:user-1",
      channelId: "feishu",
      conversationId: "chat-1",
      accountId: "acct-1",
      senderId: "user-1",
      agentId: "main",
    });

    assert.equal(event.content, "杭州现在 28°C；宁波我 3 分钟后回来同步。");
    assert.equal(result?.content, "杭州现在 28°C；宁波我 3 分钟后回来同步。");
    assert.equal(result?.cancel, undefined);

    const calls = await readHookCalls(callsPath);
    const progressCall = calls.find((entry) => entry.command === "progress-active");
    assert.equal(progressCall?.payload?.progress_note, "杭州现在 28°C；宁波我 3 分钟后回来同步。");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("decision case: planned task with immediate-summary mode emits one short business-facing summary", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "先查杭州天气先简短告诉我，宁波3分钟后再告诉我",
        body: "先查杭州天气先简短告诉我，宁波3分钟后再告诉我",
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

    await plugin.registeredTools.get("ts_create_followup_plan").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      followup_message: "3分钟后回来同步宁波天气",
      followup_summary: "3分钟后同步宁波天气",
      main_user_content_mode: "immediate-summary",
    });

    const event = {
      content:
        "内部调度状态：已安排妥当。\n杭州现在 28°C，天气稳定，适合轻装出门。\n宁波我 3 分钟后回来同步，详细过程我已经写进 follow-up plan，会在到点时继续处理。",
    };
    const result = await plugin.messageSending(event, {
      sessionKey: "agent:main:feishu:acct-1:user-1",
      channelId: "feishu",
      conversationId: "chat-1",
      accountId: "acct-1",
      senderId: "user-1",
      agentId: "main",
    });

    assert.equal(event.content, "杭州现在 28°C，天气稳定，适合轻装出门。");
    assert.equal(result?.content, "杭州现在 28°C，天气稳定，适合轻装出门。");
    assert.equal(result?.cancel, undefined);

    const calls = await readHookCalls(callsPath);
    const progressCall = calls.find((entry) => entry.command === "progress-active");
    assert.equal(
      progressCall?.payload?.progress_note,
      "杭州现在 28°C，天气稳定，适合轻装出门。",
    );
    const debugEvents = await readDebugEvents(runtimeRoot);
    const extracted = debugEvents.find((entry) => entry.event === "message_sending:user-content-extracted");
    assert.equal(extracted?.payload?.reason, "main-user-content-mode-immediate-summary");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("attach_promise_guard suppresses immediate business content until planning sets an explicit mode", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "2分钟后提醒我查天气，然后回来同步结果",
        body: "2分钟后提醒我查天气，然后回来同步结果",
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
      promise_summary: "2分钟后同步天气结果",
      followup_due_at: "2026-04-06T12:05:00+08:00",
    });

    const event = {
      content: "目的地按宁波算，明天天气大致 14°C~21°C。",
    };
    const result = await plugin.messageSending(event, {
      sessionKey: "agent:main:feishu:acct-1:user-1",
      channelId: "feishu",
      conversationId: "chat-1",
      accountId: "acct-1",
      senderId: "user-1",
      agentId: "main",
    });

    assert.equal(event.content, "");
    assert.equal(result?.content, "");
    assert.equal(result?.cancel, true);
    const calls = await readHookCalls(callsPath);
    const progressCall = calls.find((entry) => entry.command === "progress-active");
    assert.equal(progressCall, undefined);
    const debugEvents = await readDebugEvents(runtimeRoot);
    const suppressed = debugEvents.find((entry) => entry.event === "message_sending:user-content-suppressed");
    assert.equal(suppressed?.payload?.reason, "main-user-content-mode-none");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("message_sending suppresses immediate business content after binding is recovered from truth source", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot({
    resolveActiveResponse: {
      found: true,
      task_id: "task-123",
      status: "running",
      channel: "feishu",
      account_id: "acct-1",
      chat_id: "chat-1",
      reply_to_id: "om_source_message",
      thread_id: "thread_source_message",
      require_structured_user_content: true,
      main_user_content_mode: "none",
      task: {
        task_id: "task-123",
        channel: "feishu",
        account_id: "acct-1",
        chat_id: "chat-1",
      },
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    const event = {
      content: "目的地按宁波算，明天天气大致 14°C~21°C。",
    };
    const result = await plugin.messageSending(event, {
      sessionKey: "agent:main:feishu:acct-1:user-1",
      channelId: "feishu",
      conversationId: "chat-1",
      accountId: "acct-1",
      senderId: "user-1",
      agentId: "main",
    });

    assert.equal(event.content, "");
    assert.equal(result?.content, "");
    assert.equal(result?.cancel, true);
    const calls = await readHookCalls(callsPath);
    const progressCall = calls.find((entry) => entry.command === "progress-active");
    assert.equal(progressCall, undefined);
    const commands = await readHookCommands(callsPath);
    assert.ok(commands.includes("resolve-active"));
    const debugEvents = await readDebugEvents(runtimeRoot);
    const recovered = debugEvents.find((entry) => entry.event === "active-task-binding:recovered");
    assert.equal(recovered?.payload?.taskId, "task-123");
    const suppressed = debugEvents.find((entry) => entry.event === "message_sending:user-content-suppressed");
    assert.equal(suppressed?.payload?.reason, "main-user-content-mode-none");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_message_write suppresses transcript entries when main_user_content_mode is none", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "宁波天气明天2分钟后告诉我",
        body: "宁波天气明天2分钟后告诉我",
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

    await plugin.registeredTools.get("ts_create_followup_plan").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      followup_message: "2分钟后我回来同步明天天气",
      followup_summary: "2分钟后同步明天天气",
      main_user_content_mode: "none",
    });

    const result = plugin.beforeMessageWrite(
      {
        sessionKey: "agent:main:feishu:acct-1:user-1",
        agentId: "main",
        message: {
          role: "assistant",
          content: [
            {
              type: "text",
              text: "查好了。明天宁波 20°C。",
            },
          ],
          timestamp: Date.now(),
        },
      },
      {
        sessionKey: "agent:main:feishu:acct-1:user-1",
        agentId: "main",
      },
    );

    assert.equal(result?.block, true);
    const sanitized = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "before_message_write:user-content-sanitized",
    );
    assert.equal(sanitized?.payload?.reason, "main-user-content-mode-none");
    assert.equal(sanitized?.payload?.blocked, true);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_message_write rewrites transcript entries to the immediate-summary contract", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "先查杭州天气先简短告诉我，宁波3分钟后再告诉我",
        body: "先查杭州天气先简短告诉我，宁波3分钟后再告诉我",
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

    await plugin.registeredTools.get("ts_create_followup_plan").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      followup_message: "3分钟后回来同步宁波天气",
      followup_summary: "3分钟后同步宁波天气",
      main_user_content_mode: "immediate-summary",
    });

    const result = plugin.beforeMessageWrite(
      {
        sessionKey: "agent:main:feishu:acct-1:user-1",
        agentId: "main",
        message: {
          role: "assistant",
          content: [
            {
              type: "text",
              text:
                "内部调度状态：已安排妥当。\n杭州现在 28°C，天气稳定，适合轻装出门。\n宁波我 3 分钟后回来同步，详细过程我已经写进 follow-up plan，会在到点时继续处理。",
            },
          ],
          timestamp: Date.now(),
        },
      },
      {
        sessionKey: "agent:main:feishu:acct-1:user-1",
        agentId: "main",
      },
    );

    assert.equal(result?.block, undefined);
    assert.equal(
      result?.message?.content?.[0]?.text,
      "杭州现在 28°C，天气稳定，适合轻装出门。",
    );
    const sanitized = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "before_message_write:user-content-sanitized",
    );
    assert.equal(sanitized?.payload?.reason, "main-user-content-mode-immediate-summary");
    assert.equal(sanitized?.payload?.blocked, false);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("new session transcript stays aligned with the plain-text mode-first contract", async () => {
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

    await plugin.registeredTools.get("ts_create_followup_plan").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      followup_message: "5分钟后回来同步结果",
      main_user_content_mode: "full-answer",
    });

    const promptBuild = await plugin.beforePromptBuild(
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

    const transcriptEntries = [];
    transcriptEntries.push({
      role: "user",
      content: [{ type: "text", text: promptBuild?.prependContext || "" }],
      timestamp: Date.now(),
    });

    const sanitizedAssistant = plugin.beforeMessageWrite(
      {
        sessionKey: "agent:main:feishu:acct-1:user-1",
        agentId: "main",
        message: {
          role: "assistant",
          content: [
            {
              type: "text",
              text: "[[reply_to_current]] 查完了。杭州现在 28°C。",
            },
          ],
          timestamp: Date.now(),
        },
      },
      {
        sessionKey: "agent:main:feishu:acct-1:user-1",
        agentId: "main",
      },
    );

    if (sanitizedAssistant?.message) {
      transcriptEntries.push(sanitizedAssistant.message);
    }

    const flattenedTranscript = JSON.stringify(transcriptEntries);
    assert.doesNotMatch(flattenedTranscript, /<task_user_content>/);
    assert.match(flattenedTranscript, /runtime chooses none \/ immediate-summary \/ full-answer/);
    assert.match(flattenedTranscript, /\[\[reply_to_current\]\] 查完了。\s*杭州现在 28°C。/);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("message_sending allows unstructured full-answer content after planning tools are used", async () => {
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

    await plugin.registeredTools.get("ts_create_followup_plan").execute("run-1", {
      source_task_id: "task-123",
      session_key: "agent:main:feishu:acct-1:user-1",
      followup_due_at: "2026-04-06T12:05:00+08:00",
      followup_message: "5分钟后回来同步结果",
      main_user_content_mode: "full-answer",
    });

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

    assert.equal(event.content, "[[reply_to_current]] 查完了。 杭州现在 28°C。 我已经安排好了，5 分钟后回来同步。");
    const calls = await readHookCalls(callsPath);
    const progressCall = calls.find((entry) => entry.command === "progress-active");
    assert.equal(progressCall?.payload?.progress_note, "[[reply_to_current]] 查完了。 杭州现在 28°C。 我已经安排好了，5 分钟后回来同步。");
    const debugEvents = await readDebugEvents(runtimeRoot);
    const suppressed = debugEvents.find((entry) => entry.event === "message_sending:user-content-suppressed");
    assert.equal(suppressed, undefined);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});
