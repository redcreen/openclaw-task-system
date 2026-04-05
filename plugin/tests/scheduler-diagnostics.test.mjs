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

// 这组测试覆盖 lifecycle / scheduler 诊断日志，确保 entered / skipped / ignored 口径统一。

test("duplicate before_agent_start skip carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot, callsPath } = await createFakeRuntimeRoot({
    registerResponse: buildRegisterDecision({
      classification_reason: "long-task",
      task_id: "task-dup-activation",
      task_status: "queued",
    }),
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我继续处理",
        body: "帮我继续处理",
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

    await plugin.beforeAgentStart(
      { prompt: "继续当前任务" },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        trigger: "user",
        agentId: "main",
      },
    );

    await plugin.beforeAgentStart(
      { prompt: "继续当前任务" },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        trigger: "user",
        agentId: "main",
      },
    );

    const commands = await readHookCommands(callsPath);
    assert.deepEqual(commands, ["taskmonitor-status", "register", "activate-latest"]);

    const debugEvents = await readDebugEvents(runtimeRoot);
    const duplicateSkipped = debugEvents.find((entry) => entry.event === "before_agent_start:duplicate-activation-skipped");
    assert.equal(duplicateSkipped?.payload?.schedulerDecision, "skipped");
    assert.equal(duplicateSkipped?.payload?.reason, "duplicate-activation");
    assert.equal(duplicateSkipped?.payload?.taskId, "task-dup-activation");
    assert.equal(duplicateSkipped?.payload?.trigger, "user");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_agent_start taskmonitor-disabled carries scheduler diagnostics", async () => {
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

    await plugin.beforeAgentStart(
      { prompt: "继续当前任务" },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        trigger: "user",
        agentId: "main",
      },
    );

    const debugEvents = await readDebugEvents(runtimeRoot);
    const disabled = debugEvents.find((entry) => entry.event === "before_agent_start:taskmonitor-disabled");
    assert.equal(disabled?.payload?.schedulerDecision, "skipped");
    assert.equal(disabled?.payload?.reason, "taskmonitor-disabled");
    assert.equal(disabled?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_agent_start ignored trigger carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeAgentStart(
      { prompt: "继续当前任务" },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        trigger: "system",
        agentId: "main",
      },
    );

    const debugEvents = await readDebugEvents(runtimeRoot);
    const ignored = debugEvents.find((entry) => entry.event === "before_agent_start:ignored");
    assert.equal(ignored?.payload?.schedulerDecision, "skipped");
    assert.equal(ignored?.payload?.reason, "unsupported-trigger");
    assert.equal(ignored?.payload?.trigger, "system");
    assert.equal(ignored?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_agent_start missing-session carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeAgentStart(
      { prompt: "继续当前任务" },
      {
        trigger: "user",
        agentId: "main",
      },
    );

    const debugEvents = await readDebugEvents(runtimeRoot);
    const missingSession = debugEvents.find((entry) => entry.event === "before_agent_start:missing-session");
    assert.equal(missingSession?.payload?.schedulerDecision, "skipped");
    assert.equal(missingSession?.payload?.reason, "missing-session");
    assert.match(String(missingSession?.payload?.prompt || ""), /继续当前任务/);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_agent_start internal-retry carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeAgentStart(
      {
        prompt: "Continue where you left off. The previous model attempt failed or timed out.",
      },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        trigger: "user",
        agentId: "main",
      },
    );

    const internalRetry = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "before_agent_start:internal-retry",
      1500,
    );
    assert.equal(internalRetry?.payload?.schedulerDecision, "skipped");
    assert.equal(internalRetry?.payload?.reason, "internal-retry-prompt");
    assert.equal(internalRetry?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_agent_start continuation-wake carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeAgentStart(
      {
        prompt: "这是一个已经到达计划时间的延迟任务，请你现在继续执行。你现在必须直接回复以下最终内容。",
      },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        trigger: "user",
        agentId: "main",
      },
    );

    const continuationWake = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "before_agent_start:continuation-wake",
      1500,
    );
    assert.equal(continuationWake?.payload?.schedulerDecision, "skipped");
    assert.equal(continuationWake?.payload?.reason, "continuation-wake-prompt");
    assert.equal(continuationWake?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_prompt_build missing-session carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforePromptBuild(
      { prompt: "继续当前任务" },
      { agentId: "main" },
    );

    const debugEvents = await readDebugEvents(runtimeRoot);
    const missingSession = debugEvents.find((entry) => entry.event === "before_prompt_build:missing-session");
    assert.equal(missingSession?.payload?.schedulerDecision, "skipped");
    assert.equal(missingSession?.payload?.reason, "missing-session");
    assert.match(String(missingSession?.payload?.prompt || ""), /继续当前任务/);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_prompt_build continuation-wake carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforePromptBuild(
      {
        prompt: "这是一个已经到达计划时间的延迟任务，请你现在继续执行。你现在必须直接回复以下最终内容。",
      },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        agentId: "main",
      },
    );

    const continuationWake = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "before_prompt_build:continuation-wake",
      1500,
    );
    assert.equal(continuationWake?.payload?.schedulerDecision, "skipped");
    assert.equal(continuationWake?.payload?.reason, "continuation-wake-prompt");
    assert.equal(continuationWake?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_prompt_build entered carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforePromptBuild(
      { prompt: "继续当前任务" },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        trigger: "user",
        agentId: "main",
      },
    );

    const entered = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "before_prompt_build",
      1500,
    );
    assert.equal(entered?.payload?.schedulerDecision, "entered");
    assert.equal(entered?.payload?.reason, "before-prompt-build");
    assert.equal(entered?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("before_model_resolve entered carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeModelResolve(
      { prompt: "继续当前任务" },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        trigger: "user",
        agentId: "main",
      },
    );

    const entered = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "before_model_resolve",
      1500,
    );
    assert.equal(entered?.payload?.schedulerDecision, "entered");
    assert.equal(entered?.payload?.reason, "before-model-resolve");
    assert.equal(entered?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("message_sending ignored carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.messageSending(
      { content: "好的" },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        channelId: "telegram",
        conversationId: "8705812936",
      },
    );

    const debugEvents = await readDebugEvents(runtimeRoot);
    const ignored = debugEvents.find((entry) => entry.event === "message_sending:ignored");
    assert.equal(ignored?.payload?.schedulerDecision, "skipped");
    assert.equal(ignored?.payload?.reason, "progress-sync-filtered");
    assert.equal(ignored?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("message_sending entered carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.messageSending(
      { content: "这是一个足够长的进度同步内容，用来触发正常 progress sync。" },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        channelId: "telegram",
        conversationId: "8705812936",
        agentId: "main",
      },
    );

    const entered = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "message_sending",
      1500,
    );
    assert.equal(entered?.payload?.schedulerDecision, "entered");
    assert.equal(entered?.payload?.reason, "progress-sync");
    assert.equal(entered?.payload?.sessionKey, "telegram:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("llm_output taskmonitor-disabled carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
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

    await plugin.llmOutput(
      { assistantTexts: ["我来继续处理这个问题"] },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        agentId: "main",
      },
    );

    const debugEvents = await readDebugEvents(runtimeRoot);
    const disabled = debugEvents.find((entry) => entry.event === "llm_output:taskmonitor-disabled");
    assert.equal(disabled?.payload?.schedulerDecision, "skipped");
    assert.equal(disabled?.payload?.reason, "taskmonitor-disabled");
    assert.equal(disabled?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("llm_output ignored carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.llmOutput(
      { assistantTexts: ["好的"] },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        agentId: "main",
      },
    );

    const debugEvents = await readDebugEvents(runtimeRoot);
    const ignored = debugEvents.find((entry) => entry.event === "llm_output:ignored");
    assert.equal(ignored?.payload?.schedulerDecision, "skipped");
    assert.equal(ignored?.payload?.reason, "progress-sync-filtered");
    assert.equal(ignored?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("llm_output entered carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.llmOutput(
      { assistantTexts: ["这是一个足够长的进度同步内容，用来触发正常 progress sync。"] },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        agentId: "main",
      },
    );

    const entered = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "llm_output",
      1500,
    );
    assert.equal(entered?.payload?.schedulerDecision, "entered");
    assert.equal(entered?.payload?.reason, "progress-sync");
    assert.equal(entered?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("hook failure carries operator-visible scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    hookFailureCommands: ["taskmonitor-status"],
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
      {
        content: "帮我继续处理",
        body: "帮我继续处理",
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

    const failed = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "hook:taskmonitor-status:error",
      1500,
    );
    assert.equal(failed?.payload?.schedulerDecision, "error");
    assert.equal(failed?.payload?.reason, "hook-call-failed");
    assert.equal(failed?.payload?.command, "taskmonitor-status");
    assert.equal(failed?.payload?.logLevel, "warn");
    assert.equal(failed?.payload?.operatorVisible, true);
    assert.equal(failed?.payload?.errorCategory, "hook-call-failure");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("gateway failure carries operator-visible scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot, openclawBin } = await createFakeRuntimeRoot({
    watchdogAutoRecoverResponse: {
      startup_promoted: [
        {
          session_key: "agent:main:feishu:direct:ou_resume",
          channel: "feishu",
          account_id: "acct-resume",
          chat_id: "chat-resume",
          task_label: "继续处理遗留任务",
        },
      ],
    },
    gatewayCallFailures: {
      "chat.send": "simulated chat.send failure",
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    enableWatchdogRecoveryRunner: true,
    watchdogRecoveryPollMs: 60_000,
    enableHostFeishuDelivery: false,
    enableContinuationRunner: false,
    openclawBin,
  });

  try {
    await plugin.start();

    const failed = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "gateway:chat.send:error",
      1500,
    );
    assert.equal(failed?.payload?.schedulerDecision, "error");
    assert.equal(failed?.payload?.reason, "gateway-call-failed");
    assert.equal(failed?.payload?.method, "chat.send");
    assert.equal(failed?.payload?.logLevel, "warn");
    assert.equal(failed?.payload?.operatorVisible, true);
    assert.equal(failed?.payload?.errorCategory, "gateway-call-failure");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("plugin load emits structured enabled lifecycle event", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    const loaded = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "plugin:load:enabled",
      1500,
    );
    assert.equal(loaded?.payload?.enabled, true);
    assert.equal(loaded?.payload?.schedulerDecision, "entered");
    assert.equal(loaded?.payload?.reason, "plugin-register-complete");
    assert.equal(loaded?.payload?.logLevel, "info");
    assert.equal(loaded?.payload?.operatorVisible, true);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("message_sending continuation-fulfilled carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    fulfillDueContinuationResponse: {
      updated: true,
      matched_reply_text: "111",
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.messageSending(
      { content: "111" },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        agentId: "main",
      },
    );

    const fulfilled = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "message_sending:continuation-fulfilled",
      1500,
    );
    assert.equal(fulfilled?.payload?.schedulerDecision, "skipped");
    assert.equal(fulfilled?.payload?.reason, "continuation-fulfilled");
    assert.equal(fulfilled?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
    assert.equal(fulfilled?.payload?.matchedReplyText, "111");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("llm_output continuation-fulfilled carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    fulfillDueContinuationResponse: {
      updated: true,
      matched_reply_text: "111",
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.llmOutput(
      { assistantTexts: ["111"] },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        agentId: "main",
      },
    );

    const fulfilled = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "llm_output:continuation-fulfilled",
      1500,
    );
    assert.equal(fulfilled?.payload?.schedulerDecision, "skipped");
    assert.equal(fulfilled?.payload?.reason, "continuation-fulfilled");
    assert.equal(fulfilled?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
    assert.equal(fulfilled?.payload?.matchedReplyText, "111");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("agent_end taskmonitor-disabled carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.beforeDispatch(
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

    const debugEvents = await readDebugEvents(runtimeRoot);
    const disabled = debugEvents.find((entry) => entry.event === "agent_end:taskmonitor-disabled");
    assert.equal(disabled?.payload?.schedulerDecision, "skipped");
    assert.equal(disabled?.payload?.reason, "taskmonitor-disabled");
    assert.equal(disabled?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
    assert.equal(disabled?.payload?.success, true);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("agent_end entered carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages);

  try {
    await plugin.agentEnd(
      {
        success: true,
        messages: [{ role: "assistant", content: "最终结果" }],
      },
      {
        sessionKey: "agent:main:telegram:direct:8705812936",
        agentId: "main",
        channelId: "telegram",
        conversationId: "8705812936",
      },
    );

    const entered = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "agent_end",
      1500,
    );
    assert.equal(entered?.payload?.schedulerDecision, "entered");
    assert.equal(entered?.payload?.reason, "agent-end");
    assert.equal(entered?.payload?.sessionKey, "agent:main:telegram:direct:8705812936");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});
