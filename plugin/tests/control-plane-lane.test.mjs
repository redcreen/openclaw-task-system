import test from "node:test";
import assert from "node:assert/strict";

import {
  buildRegisterDecision,
  cleanupRuntime,
  createApi,
  createFakeRuntimeRoot,
  readDebugEvents,
  readHookCommands,
  resetGlobalState,
  waitForDebugEvent,
} from "./helpers/task-system-plugin-test-helpers.mjs";

// 这组测试覆盖 control-plane lane：优先级、终态拦截、管理命令、发送出口。

test("short-task followup is dropped after task reaches terminal state", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    registerResponse: buildRegisterDecision({
      classification_reason: "short-task",
      task_id: "task-short-race",
      task_status: "running",
      queue_position: 1,
      ahead_count: 0,
      running_count: 0,
      active_count: 1,
    }),
    followupResponse: {
      should_send: true,
      followup_message: "还在处理，我先同步一下进展。",
    },
    followupDelayMs: 60,
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    shortTaskFollowupTimeoutMs: 10,
  });

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我看一下这个短任务",
        body: "帮我看一下这个短任务",
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

    await new Promise((resolve) => setTimeout(resolve, 30));
    await plugin.agentEnd(
      {
        success: true,
        messages: [{ role: "assistant", content: "已经处理完成。" }],
        durationMs: 50,
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
    await new Promise((resolve) => setTimeout(resolve, 220));

    assert.equal(sentMessages.length, 1);
    assert.match(sentMessages[0].text, /^\[wd\]/);
    assert.doesNotMatch(sentMessages[0].text, /还在处理/);
    const debugEvents = await readDebugEvents(runtimeRoot);
    const terminalArmed = debugEvents.find(
      (entry) => entry.event === "agent_end:terminal-state-armed" && entry.payload?.taskId === "task-short-race",
    );
    const pendingFollowupCleared = debugEvents.find(
      (entry) => entry.event === "agent_end:pending-followup-cleared" && entry.payload?.taskId === "task-short-race",
    );
    const droppedForTerminalState = debugEvents.find(
      (entry) =>
        entry.event === "short-task-followup:dropped" &&
        entry.payload?.reason === "terminal-control-plane-state",
    );
    assert.equal(terminalArmed?.payload?.terminalEventName, "agent-settled");
    assert.equal(pendingFollowupCleared?.payload?.reason, "terminal-agent-end");
    if (droppedForTerminalState) {
      assert.equal(droppedForTerminalState.payload?.dropCategory, "terminal");
      assert.equal(droppedForTerminalState.payload?.blockerScope, "task-terminal-committed");
      assert.equal(droppedForTerminalState.payload?.blockingTaskId, "task-short-race");
      assert.equal(typeof droppedForTerminalState.payload?.blockedByEnqueueToken, "number");
      assert.equal(droppedForTerminalState.payload?.blockedByPriority, "p1-task-management");
      assert.equal(droppedForTerminalState.payload?.blockedByTerminalPhase, "committed");
    }
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("taskmonitor control command is delivered through control-plane lane", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    const result = await plugin.beforeDispatch(
      {
        content: "/taskmonitor off",
        body: "/taskmonitor off",
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
    assert.deepEqual(commands, ["taskmonitor-control"]);
    assert.equal(result?.handled, true);
    assert.equal(result?.text, undefined);
    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0].to, "8705812936");
    assert.match(sentMessages[0].text, /已关闭当前会话的 taskmonitor/);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_dispatch taskmonitor-disabled carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "taskmonitor off",
        body: "taskmonitor off",
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

    const disabled = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "before_dispatch:taskmonitor-disabled",
      1500,
    );
    assert.equal(disabled?.payload?.schedulerDecision, "skipped");
    assert.equal(disabled?.payload?.reason, "taskmonitor-disabled");
    assert.equal(disabled?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("agent_end delivers finalize failure control-plane message when runtime returns one", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot({
    finalizeActiveResponse: {
      updated: true,
      control_plane_message: {
        schema: "openclaw.task-system.control-plane.v1",
        kind: "task-failed",
        event_name: "task-failed",
        priority: "p1-task-management",
        task_id: "task-123",
        text: "当前任务已失败：agent_end failure",
      },
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我继续排查这个问题",
        body: "帮我继续排查这个问题",
        channel: "telegram",
        senderId: "8705812936",
        messageId: "msg-source-1",
        threadId: "thread-source-1",
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

    await plugin.agentEnd(
      {
        success: false,
        messages: [],
        error: "agent_end failure",
        durationMs: 50,
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
    const debugEvents = await readDebugEvents(runtimeRoot);
    const terminalArmed = debugEvents.find(
      (entry) => entry.event === "agent_end:terminal-state-armed" && entry.payload?.taskId === "task-123",
    );
    const terminalPendingArmed = debugEvents.find(
      (entry) => entry.event === "task-failed:terminal-pending-armed" && entry.payload?.taskId === "task-123",
    );
    const terminalCommitted = debugEvents.find(
      (entry) => entry.event === "task-failed:terminal-state-committed" && entry.payload?.taskId === "task-123",
    );
    const terminalCleared = debugEvents.find(
      (entry) => entry.event === "agent_end:terminal-state-cleared" && entry.payload?.taskId === "task-123",
    );
    assert.deepEqual(commands, ["taskmonitor-status", "register", "finalize-active"]);
    assert.equal(sentMessages.length, 2);
    assert.match(sentMessages[0].text, /^\[wd\]/);
    assert.match(sentMessages[1].text, /当前任务已失败：agent_end failure/);
    assert.equal(sentMessages[0].replyToId, "msg-source-1");
    assert.equal(sentMessages[1].replyToId, "msg-source-1");
    assert.equal(sentMessages[0].threadId, "thread-source-1");
    assert.equal(sentMessages[1].threadId, "thread-source-1");
    assert.equal(terminalArmed?.payload?.terminalPhase, "armed");
    assert.equal(terminalArmed?.payload?.terminalEventName, "agent-failed");
    assert.equal(terminalPendingArmed?.payload?.terminalPhase, "pending");
    assert.equal(terminalPendingArmed?.payload?.pendingTerminalEventByTask, "task-failed");
    assert.equal(terminalCommitted?.payload?.terminalPhase, "committed");
    assert.equal(terminalCommitted?.payload?.blockedBy, "task-failed");
    assert.equal(terminalCleared?.payload?.terminalPhase, "cleared");
    assert.equal(terminalCleared?.payload?.reason, "finalize-active-complete");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("control-plane lane does not stay blocked after a timed-out send in the same audience", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    taskmonitorControlResponse: {
      ok: true,
      enabled: true,
      message: "taskmonitor 已开启。",
      control_plane_message: {
        schema: "openclaw.task-system.control-plane.v1",
        kind: "taskmonitor-updated",
        event_name: "taskmonitor-updated",
        priority: "p1-task-management",
        text: "taskmonitor 已开启。",
      },
    },
    mainContinuityResponse: {
      runbook_status: "ok",
      primary_action_kind: "none",
      control_plane_message: {
        schema: "openclaw.task-system.control-plane.v1",
        kind: "continuity-summary",
        event_name: "continuity-summary",
        priority: "p1-task-management",
        text: "当前没有需要立即处理的 continuity 风险。",
      },
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    outboundSendTimeoutMs: 20,
    outboundSendModeSequence: ["hang", "ok"],
  });

  try {
    await plugin.beforeDispatch(
      {
        content: "/taskmonitor on",
        body: "/taskmonitor on",
        channel: "telegram",
        senderId: "8705812936",
        messageId: "msg-timeout-1",
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

    await plugin.beforeDispatch(
      {
        content: "/status",
        body: "/status",
        channel: "telegram",
        senderId: "8705812936",
        messageId: "msg-timeout-2",
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

    const firstError = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "taskmonitor-updated:error" || entry.event === "taskmonitor-control:error",
      1500,
    );
    const secondSent = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "continuity-summary:sent",
      1500,
    );
    assert.equal(firstError?.payload?.reason, "control-plane-send-failed");
    assert.equal(secondSent?.payload?.schedulerDecision, "sent");
    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0]?.replyToId, "msg-timeout-2");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("status command sends continuity summary through control-plane lane without entering register flow", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    const result = await plugin.beforeDispatch(
      {
        content: "/status",
        body: "/status",
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
    assert.deepEqual(commands, ["main-continuity"]);
    assert.equal(result, undefined);
    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0].to, "8705812936");
    assert.match(sentMessages[0].text, /continuity 风险|当前没有需要立即处理的 continuity 风险/);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("task-management control-plane preempts pending short-task followup in the same audience", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    registerResponse: buildRegisterDecision({
      classification_reason: "short-task",
      task_id: "task-short-preempt",
      task_status: "running",
      queue_position: 1,
      ahead_count: 0,
      running_count: 0,
      active_count: 1,
    }),
    followupResponse: {
      should_send: true,
      followup_message: "还在处理，我先同步一下进展。",
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    shortTaskFollowupTimeoutMs: 40,
  });

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我看一下这个短任务",
        body: "帮我看一下这个短任务",
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

    await plugin.beforeDispatch(
      {
        content: "/status",
        body: "/status",
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

    await new Promise((resolve) => setTimeout(resolve, 120));

    assert.equal(sentMessages.length, 2);
    assert.match(sentMessages[0].text, /^\[wd\]/);
    assert.match(sentMessages[1].text, /continuity 风险|当前没有需要立即处理的 continuity 风险/);
    assert.doesNotMatch(sentMessages[1].text, /还在处理/);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("higher-priority control-plane preempts already-enqueued low-priority control-plane in the same audience", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    registerResponse: buildRegisterDecision({
      classification_reason: "short-task",
      task_id: "task-lane-preempt",
      task_status: "running",
      queue_position: 1,
      ahead_count: 0,
      running_count: 0,
      active_count: 1,
    }),
    followupResponse: {
      should_send: true,
      followup_message: "还在处理，我先同步一下进展。",
      control_plane_message: {
        schema: "openclaw.task-system.control-plane.v1",
        kind: "short-task-followup",
        event_name: "short-task-followup",
        priority: "p2-progress-followup",
        task_id: "task-lane-preempt",
        text: "还在处理，我先同步一下进展。",
      },
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    shortTaskFollowupTimeoutMs: 10,
    outboundSendDelayMs: 80,
  });

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我看一下这个短任务",
        body: "帮我看一下这个短任务",
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

    await new Promise((resolve) => setTimeout(resolve, 20));

    await plugin.beforeDispatch(
      {
        content: "/status",
        body: "/status",
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

    await new Promise((resolve) => setTimeout(resolve, 260));

    assert.equal(sentMessages.length, 2);
    assert.match(sentMessages[0].text, /^\[wd\]/);
    assert.match(sentMessages[1].text, /continuity 风险|当前没有需要立即处理的 continuity 风险/);
    assert.doesNotMatch(sentMessages[1].text, /还在处理/);
    const debugEvents = await readDebugEvents(runtimeRoot);
    const preemptedPendingFollowup = debugEvents.find(
      (entry) =>
        entry.event === "continuity-summary:preempted-pending-followup" &&
        entry.payload?.taskId === "task-lane-preempt",
    );
    const droppedFollowup = debugEvents.find(
      (entry) =>
        entry.event === "short-task-followup:dropped" &&
        entry.payload?.reason === "preempted-by-higher-priority-control-plane",
    );
    const queuedContinuity = debugEvents.find((entry) => entry.event === "continuity-summary:lane-enqueued");
    const passedContinuity = debugEvents.find((entry) => entry.event === "continuity-summary:lane-pass");
    const sentContinuity = debugEvents.find((entry) => entry.event === "continuity-summary:sent");
    assert.equal(preemptedPendingFollowup?.payload?.reason, "higher-priority-task-management-control-plane");
    assert.equal(preemptedPendingFollowup?.payload?.schedulerDecision, "preempted-pending-followup");
    assert.equal(preemptedPendingFollowup?.payload?.blockedBy, "continuity-summary");
    assert.equal(typeof preemptedPendingFollowup?.payload?.blockedByEnqueueToken, "number");
    assert.equal(preemptedPendingFollowup?.payload?.blockedByPriority, "p1-task-management");
    if (droppedFollowup) {
      assert.equal(droppedFollowup.payload?.schedulerDecision, "dropped");
      assert.equal(droppedFollowup.payload?.dropCategory, "preempted");
      assert.equal(droppedFollowup.payload?.blockerScope, "audience-higher-priority");
      assert.equal(droppedFollowup.payload?.blockedBy, "continuity-summary");
      assert.equal(typeof droppedFollowup.payload?.blockedByEnqueueToken, "number");
      assert.equal(droppedFollowup.payload?.blockedByPriority, "p1-task-management");
    }
    assert.equal(queuedContinuity?.payload?.audienceKey, "telegram:default:8705812936");
    assert.equal(queuedContinuity?.payload?.schedulerDecision, "enqueued");
    assert.equal(typeof queuedContinuity?.payload?.enqueueToken, "number");
    assert.equal(passedContinuity?.payload?.schedulerDecision, "passed");
    assert.equal(typeof passedContinuity?.payload?.enqueueToken, "number");
    assert.equal(sentContinuity?.payload?.schedulerDecision, "sent");
    assert.equal(sentContinuity?.payload?.audienceKey, "telegram:default:8705812936");
    assert.equal(sentContinuity?.payload?.enqueueToken, queuedContinuity?.payload?.enqueueToken);
    assert.equal(sentContinuity?.payload?.audienceSequence, queuedContinuity?.payload?.audienceSequence);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("newer low-priority control-plane supersedes older low-priority control-plane in the same audience", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    registerResponses: [
      buildRegisterDecision({
        classification_reason: "short-task",
        task_id: "task-low-1",
        task_status: "running",
        queue_position: 1,
        ahead_count: 0,
        running_count: 0,
        active_count: 1,
      }),
      buildRegisterDecision({
        classification_reason: "short-task",
        task_id: "task-low-2",
        task_status: "running",
        queue_position: 1,
        ahead_count: 0,
        running_count: 0,
        active_count: 1,
      }),
    ],
    followupResponse: {
      should_send: true,
      followup_message: "还在处理，我先同步一下进展。",
      control_plane_message: {
        schema: "openclaw.task-system.control-plane.v1",
        kind: "short-task-followup",
        event_name: "short-task-followup",
        priority: "p2-progress-followup",
        text: "还在处理，我先同步一下进展。",
      },
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    shortTaskFollowupTimeoutMs: 10,
    outboundSendDelayMs: 80,
  });

  try {
    await plugin.beforeDispatch(
      {
        content: "短任务一",
        body: "短任务一",
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

    await plugin.beforeDispatch(
      {
        content: "短任务二",
        body: "短任务二",
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

    const deadline = Date.now() + 1600;
    while (Date.now() < deadline) {
      const progressMessages = sentMessages.filter((entry) => /还在处理，我先同步一下进展。/.test(entry.text));
      if (progressMessages.length > 0) {
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 25));
    }

    const progressMessages = sentMessages.filter((entry) => /还在处理，我先同步一下进展。/.test(entry.text));
    assert.equal(progressMessages.length, 1);
    assert.equal(progressMessages[0].text, "[wd] 还在处理，我先同步一下进展。");
    const debugEvents = await readDebugEvents(runtimeRoot);
    const supersededSameAudience = debugEvents.find(
      (entry) =>
        entry.event === "short-task-followup:dropped" &&
        entry.payload?.reason === "superseded-by-newer-control-plane-message-same-audience",
    );
    if (supersededSameAudience) {
      assert.equal(supersededSameAudience.payload?.schedulerDecision, "dropped");
      assert.equal(supersededSameAudience.payload?.dropCategory, "superseded");
      assert.equal(supersededSameAudience.payload?.blockerScope, "audience-newer-message");
      assert.equal(supersededSameAudience.payload?.blockedBy, "short-task-followup");
      assert.equal(typeof supersededSameAudience.payload?.blockedByEnqueueToken, "number");
      assert.equal(supersededSameAudience.payload?.blockedByPriority, "p2-progress-followup");
      assert.equal(supersededSameAudience.payload?.blockingTaskId, "task-low-2");
      assert.equal(typeof supersededSameAudience.payload?.enqueueToken, "number");
      assert.equal(typeof supersededSameAudience.payload?.latestSupersedableTokenByAudience, "number");
    }
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("tasks command sends session task summary through control-plane lane without entering register flow", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    const result = await plugin.beforeDispatch(
      {
        content: "/tasks",
        body: "/tasks",
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
    assert.deepEqual(commands, ["main-tasks-summary"]);
    assert.equal(result, undefined);
    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0].to, "8705812936");
    assert.match(sentMessages[0].text, /当前会话共有 2 条活动任务/);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("control-plane logs adapter-unavailable with scheduler decision when outbound adapter is missing", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    outboundAdapterMode: "unavailable",
  });

  try {
    await plugin.beforeDispatch(
      {
        content: "/status",
        body: "/status",
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

    const debugEvents = await readDebugEvents(runtimeRoot);
    const adapterUnavailable = debugEvents.find((entry) => entry.event === "continuity-summary:adapter-unavailable");
    assert.equal(sentMessages.length, 0);
    assert.equal(adapterUnavailable?.payload?.schedulerDecision, "adapter-unavailable");
    assert.equal(adapterUnavailable?.payload?.taskId, null);
    assert.equal(typeof adapterUnavailable?.payload?.enqueueToken, "number");
    assert.equal(adapterUnavailable?.payload?.audienceKey, "telegram:default:8705812936");
    assert.equal(adapterUnavailable?.payload?.audienceSequence, 1);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("control-plane logs delivery error with scheduler decision when outbound send fails", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    outboundAdapterMode: "error",
    outboundErrorMessage: "simulated-send-failure",
  });

  try {
    await plugin.beforeDispatch(
      {
        content: "/status",
        body: "/status",
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

    const debugEvents = await readDebugEvents(runtimeRoot);
    const deliveryError = debugEvents.find((entry) => entry.event === "continuity-summary:error");
    assert.equal(sentMessages.length, 0);
    assert.equal(deliveryError?.payload?.schedulerDecision, "error");
    assert.equal(deliveryError?.payload?.reason, "control-plane-send-failed");
    assert.equal(deliveryError?.payload?.error, "simulated-send-failure");
    assert.equal(deliveryError?.payload?.logLevel, "warn");
    assert.equal(deliveryError?.payload?.operatorVisible, true);
    assert.equal(deliveryError?.payload?.errorCategory, "control-plane-delivery-failure");
    assert.equal(typeof deliveryError?.payload?.enqueueToken, "number");
    assert.equal(deliveryError?.payload?.audienceKey, "telegram:default:8705812936");
    assert.equal(deliveryError?.payload?.audienceSequence, 1);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("plugin disabled emits structured load event", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  createApi(runtimeRoot, sentMessages, {
    enabled: false,
  });

  const disabled = await waitForDebugEvent(
    runtimeRoot,
    (entry) => entry.event === "plugin:load:disabled",
    1500,
  );
  assert.equal(disabled?.payload?.enabled, false);
  assert.equal(disabled?.payload?.schedulerDecision, "skipped");
  assert.equal(disabled?.payload?.reason, "plugin-disabled-by-config");
  assert.equal(disabled?.payload?.logLevel, "info");
  assert.equal(disabled?.payload?.operatorVisible, true);
});

test("short-task followup skip carries audience diagnostics before enqueue", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    registerResponse: buildRegisterDecision({
      classification_reason: "short-task",
      task_id: "task-short-skip",
      task_status: "running",
      queue_position: 1,
      ahead_count: 0,
      running_count: 0,
      active_count: 1,
    }),
    followupResponse: {
      should_send: false,
      reason: "still-within-threshold",
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    shortTaskFollowupTimeoutMs: 10,
  });

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我看一下这个短任务",
        body: "帮我看一下这个短任务",
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

    const skippedFollowup = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "short-task-followup:skipped",
      1500,
    );
    assert.equal(skippedFollowup?.payload?.schedulerDecision, "skipped");
    assert.equal(skippedFollowup?.payload?.reason, "still-within-threshold");
    assert.equal(skippedFollowup?.payload?.priority, "p2-progress-followup");
    assert.equal(skippedFollowup?.payload?.channel, "telegram");
    assert.equal(skippedFollowup?.payload?.chatId, "8705812936");
    assert.equal(skippedFollowup?.payload?.audienceKey, "telegram:default:8705812936");
    assert.equal(skippedFollowup?.payload?.taskId, "task-short-skip");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});
