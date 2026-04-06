import test from "node:test";
import assert from "node:assert/strict";

import {
  PRE_REGISTER_STATE_KEY,
  EARLY_ACK_STATE_KEY,
  buildCanonicalSnapshotEntry,
  buildEarlyAckMarker,
  buildRegisterDecision,
  buildStateKey,
  cleanupRuntime,
  createApi,
  createFakeRuntimeRoot,
  readDebugEvents,
  readHookCommands,
  resetGlobalState,
  waitForDebugEvent,
} from "./helpers/task-system-plugin-test-helpers.mjs";

// 这组测试覆盖 pre-register、early ack、queueKey 命中与 Telegram slash 回执归一化。

test("before_dispatch reuses pre-registered result and skips duplicate ack after queued early ack", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  globalThis[PRE_REGISTER_STATE_KEY].set(buildStateKey("feishu", "acct-1", "user-1"), [
    buildCanonicalSnapshotEntry({
      content: "在么",
      earlyAckSent: true,
    }),
  ]);

  try {
    await plugin.beforeDispatch(
      {
        content: "在么",
        body: "在么",
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

    const commands = await readHookCommands(callsPath);
    assert.deepEqual(commands, ["taskmonitor-status"]);
    assert.equal(sentMessages.length, 0);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_dispatch consumes structured preRegisterSnapshot entry", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  globalThis[PRE_REGISTER_STATE_KEY].set(buildStateKey("feishu", "acct-1", "user-1"), [
    buildCanonicalSnapshotEntry({
      content: "在吗，帮我继续",
      registerDecision: buildRegisterDecision({ task_id: "task-snapshot" }),
      earlyAckSent: true,
    }),
  ]);

  try {
    await plugin.beforeDispatch(
      {
        content: "在吗，帮我继续",
        body: "在吗，帮我继续",
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

    const commands = await readHookCommands(callsPath);
    const debugEvents = await readDebugEvents(runtimeRoot);
    const decisionEvent = debugEvents.find((entry) => entry.event === "immediate-ack:decision");
    assert.deepEqual(commands, ["taskmonitor-status"]);
    assert.equal(sentMessages.length, 0);
    assert.equal(decisionEvent?.payload?.producerMode, "receive-side-producer");
    assert.equal(decisionEvent?.payload?.producerConsumerAligned, true);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_dispatch prefers structured register_decision from runtime register response", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot({
    registerResponse: {
      should_register_task: true,
      classification_reason: "long-task",
      task_id: "task-flat",
      task_status: "queued",
      register_decision: {
        should_register_task: true,
        classification_reason: "continuation-task",
        task_id: "task-nested",
        task_status: "paused",
      },
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "继续处理这个长任务",
        body: "继续处理这个长任务",
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

    const commands = await readHookCommands(callsPath);
    const debugEvents = await readDebugEvents(runtimeRoot);
    const decisionEvent = debugEvents.find((entry) => entry.event === "immediate-ack:decision");
    assert.deepEqual(commands, ["taskmonitor-status", "register"]);
    assert.equal(decisionEvent?.payload?.classificationReason, "continuation-task");
    assert.equal(decisionEvent?.payload?.taskId, "task-nested");
    assert.equal(decisionEvent?.payload?.producerMode, "dispatch-side-priority-only");
    assert.equal(decisionEvent?.payload?.producerConsumerAligned, false);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_dispatch skips duplicate ack when an early ack was already queued for the chat", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  globalThis[EARLY_ACK_STATE_KEY].set(buildStateKey("feishu", "acct-1", "chat-1"), [Date.now()]);

  try {
    await plugin.beforeDispatch(
      {
        content: "继续处理",
        body: "继续处理",
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

    const commands = await readHookCommands(callsPath);
    assert.deepEqual(commands, ["taskmonitor-status", "register"]);
    assert.equal(sentMessages.length, 0);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_dispatch prefers queueKey match from structured snapshot over fallback sender key", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  globalThis[PRE_REGISTER_STATE_KEY].set(buildStateKey("feishu", "acct-1", "user-1"), [
    buildCanonicalSnapshotEntry({
      conversationId: "wrong-chat",
      content: "帮我继续",
      registerDecision: buildRegisterDecision({ task_id: "task-wrong" }),
      earlyAckSent: true,
    }),
    buildCanonicalSnapshotEntry({
      conversationId: "chat-1",
      content: "帮我继续",
      registerDecision: buildRegisterDecision({ task_id: "task-queuekey" }),
      earlyAckSent: false,
    }),
  ]);

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我继续",
        body: "帮我继续",
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

    const commands = await readHookCommands(callsPath);
    assert.deepEqual(commands, ["taskmonitor-status"]);
    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0].to, "chat-1");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_dispatch consumes structured early ack marker without duplicate ack", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  globalThis[EARLY_ACK_STATE_KEY].set(buildStateKey("feishu", "acct-1", "chat-1"), [
    buildEarlyAckMarker(),
  ]);

  try {
    await plugin.beforeDispatch(
      {
        content: "再看一下",
        body: "再看一下",
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

    const commands = await readHookCommands(callsPath);
    assert.deepEqual(commands, ["taskmonitor-status", "register"]);
    assert.equal(sentMessages.length, 0);
    const debugEvents = await readDebugEvents(runtimeRoot);
    const skippedImmediateAck = debugEvents.find((entry) => entry.event === "immediate-ack:skipped");
    assert.equal(skippedImmediateAck?.payload?.schedulerDecision, "skipped");
    assert.equal(skippedImmediateAck?.payload?.reason, "queued-early-ack-already-sent");
    assert.equal(skippedImmediateAck?.payload?.priority, "p0-receive-ack");
    assert.equal(skippedImmediateAck?.payload?.channel, "feishu");
    assert.equal(skippedImmediateAck?.payload?.chatId, "chat-1");
    assert.equal(skippedImmediateAck?.payload?.audienceKey, "feishu:acct-1:chat-1");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_dispatch normalizes telegram slash recipient for immediate ack delivery", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "我爱吃什么",
        body: "我爱吃什么",
        channel: "telegram",
        senderId: "8705812936",
      },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        channelId: "telegram",
        conversationId: "slash:8705812936",
        accountId: "default",
        senderId: "8705812936",
        agentId: "main",
      },
    );

    const commands = await readHookCommands(callsPath);
    assert.deepEqual(commands, ["taskmonitor-status", "register"]);
    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0].to, "8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_dispatch normalizes telegram slash recipient for long-task wd ack delivery", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot({
    registerResponse: buildRegisterDecision({
      classification_reason: "long-task",
      task_id: "task-long-slash",
      task_status: "queued",
    }),
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我排查一下这个长问题",
        body: "帮我排查一下这个长问题",
        channel: "telegram",
        senderId: "8705812936",
      },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        channelId: "telegram",
        conversationId: "slash:8705812936",
        accountId: "default",
        senderId: "8705812936",
        agentId: "main",
      },
    );

    const commands = await readHookCommands(callsPath);
    assert.deepEqual(commands, ["taskmonitor-status", "register"]);
    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0].to, "8705812936");
    assert.match(sentMessages[0].text, /^\[wd\]/);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("feishu wd ack replies to the original message", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    registerResponse: buildRegisterDecision({
      classification_reason: "long-task",
      task_id: "task-feishu-reply",
      task_status: "queued",
    }),
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "在么",
        body: "在么",
        channel: "feishu",
        senderId: "user-1",
        messageId: "om_reply_1",
        threadId: "thread-1",
      },
      {
        sessionKey: "agent:health:feishu:acct-1:user-1",
        channelId: "feishu",
        conversationId: "chat-1",
        accountId: "acct-1",
        senderId: "user-1",
        agentId: "health",
        messageId: "om_reply_1",
        threadId: "thread-1",
      },
    );

    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0].to, "chat-1");
    assert.equal(sentMessages[0].replyToId, "om_reply_1");
    assert.equal(sentMessages[0].threadId, "thread-1");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("feishu wd ack falls back to pre-register snapshot reply target when dispatch lacks message ids", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  globalThis[PRE_REGISTER_STATE_KEY].set(buildStateKey("feishu", "acct-1", "user-1"), [
    buildCanonicalSnapshotEntry({
      content: "在么",
      earlyAckSent: false,
      registerDecision: buildRegisterDecision({
        classification_reason: "long-task",
        task_id: "task-from-snapshot",
        task_status: "queued",
      }),
      messageId: "om_snapshot_1",
      threadId: "thread-snapshot-1",
    }),
  ]);

  try {
    await plugin.beforeDispatch(
      {
        content: "在么",
        body: "在么",
        channel: "feishu",
        senderId: "user-1",
      },
      {
        sessionKey: "agent:health:feishu:acct-1:user-1",
        channelId: "feishu",
        conversationId: "chat-1",
        accountId: "acct-1",
        senderId: "user-1",
        agentId: "health",
      },
    );

    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0].replyToId, "om_snapshot_1");
    assert.equal(sentMessages[0].threadId, "thread-snapshot-1");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("feishu short-task followup keeps replying to the original message", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    registerResponse: buildRegisterDecision({
      classification_reason: "observed-task",
      task_id: "task-short-followup-reply",
      task_status: "running",
      queue_position: 1,
      ahead_count: 0,
      running_count: 1,
      active_count: 1,
    }),
    followupResponse: {
      should_send: true,
      followup_message: "已收到你的消息，当前仍在处理中；稍后给你正式结果。",
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    shortTaskFollowupTimeoutMs: 10,
  });

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我看一下",
        body: "帮我看一下",
        channel: "feishu",
        senderId: "user-1",
        messageId: "om_followup_1",
        threadId: "thread-2",
      },
      {
        sessionKey: "agent:health:feishu:acct-1:user-1",
        channelId: "feishu",
        conversationId: "chat-1",
        accountId: "acct-1",
        senderId: "user-1",
        agentId: "health",
        messageId: "om_followup_1",
        threadId: "thread-2",
      },
    );

    await waitForDebugEvent(runtimeRoot, (entry) => entry.event === "short-task-followup:sent");
    assert.equal(sentMessages.length, 2);
    assert.equal(sentMessages[0].replyToId, "om_followup_1");
    assert.equal(sentMessages[0].threadId, "thread-2");
    assert.equal(sentMessages[1].replyToId, "om_followup_1");
    assert.equal(sentMessages[1].threadId, "thread-2");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("immediate ack skip for existing active task carries control-plane audience diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot({
    registerResponse: buildRegisterDecision({
      classification_reason: "existing-active-task",
      task_id: "task-existing-active",
      task_status: "running",
      queue_position: 1,
      ahead_count: 0,
      running_count: 1,
      active_count: 1,
    }),
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "继续处理当前任务",
        body: "继续处理当前任务",
        channel: "telegram",
        senderId: "8705812936",
      },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        channelId: "telegram",
        conversationId: "8705812936",
        accountId: "default",
        senderId: "8705812936",
        agentId: "main",
      },
    );

    const commands = await readHookCommands(callsPath);
    assert.deepEqual(commands, ["taskmonitor-status", "register"]);
    assert.equal(sentMessages.length, 0);

    const debugEvents = await readDebugEvents(runtimeRoot);
    const skippedImmediateAck = debugEvents.find(
      (entry) =>
        entry.event === "immediate-ack:skipped" && entry.payload?.reason === "existing-active-task",
    );
    assert.equal(skippedImmediateAck?.payload?.schedulerDecision, "skipped");
    assert.equal(skippedImmediateAck?.payload?.priority, "p0-receive-ack");
    assert.equal(skippedImmediateAck?.payload?.channel, "telegram");
    assert.equal(skippedImmediateAck?.payload?.chatId, "8705812936");
    assert.equal(skippedImmediateAck?.payload?.audienceKey, "telegram:default:8705812936");
    assert.equal(skippedImmediateAck?.payload?.taskId, "task-existing-active");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});
