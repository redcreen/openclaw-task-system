import test from "node:test";
import assert from "node:assert/strict";

import {
  cleanupRuntime,
  createApi,
  createFakeRuntimeRoot,
  resetGlobalState,
  waitForDebugEvent,
  writeSendInstruction,
} from "./helpers/task-system-plugin-test-helpers.mjs";

// 这组测试覆盖 continuation runner 与 host delivery runner。

test("continuation delivery sent carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot({
    claimDueContinuationsResponse: {
      tasks: [
        {
          task_id: "task-cont-1",
          session_key: "agent:main:telegram:direct:8705812936",
          channel: "telegram",
          account_id: "default",
          chat_id: "8705812936",
          reply_text: "111",
          continuation_payload: {
            original_user_request: "1分钟后回复111",
          },
        },
      ],
    },
  });
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    enableContinuationRunner: true,
    continuationPollMs: 60_000,
  });

  try {
    await plugin.start();

    const delivered = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "continuation-delivery:sent",
      1500,
    );
    const wakeStart = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "continuation-wake:start",
      1500,
    );
    const wakeOk = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "continuation-wake:ok",
      1500,
    );
    assert.equal(wakeStart?.payload?.runner, "continuation-delivery");
    assert.equal(wakeStart?.payload?.lifecycleStage, "wake-start");
    assert.equal(wakeStart?.payload?.deliveryPath, "direct-channel-send");
    assert.equal(wakeStart?.payload?.reason, "continuation-wake-started");
    assert.equal(delivered?.payload?.schedulerDecision, "sent");
    assert.equal(delivered?.payload?.audienceKey, "telegram:default:8705812936");
    assert.equal(delivered?.payload?.taskId, "task-cont-1");
    assert.equal(delivered?.payload?.runner, "continuation-delivery");
    assert.equal(delivered?.payload?.lifecycleStage, "delivery-sent");
    assert.equal(delivered?.payload?.deliveryPath, "direct-channel-send");
    assert.equal(delivered?.payload?.reason, "continuation-delivery-sent");
    assert.equal(wakeOk?.payload?.runner, "continuation-delivery");
    assert.equal(wakeOk?.payload?.lifecycleStage, "wake-complete");
    assert.equal(wakeOk?.payload?.deliveryPath, "direct-channel-send");
    assert.equal(wakeOk?.payload?.reason, "continuation-wake-complete");
    assert.equal(typeof delivered?.payload?.enqueueToken, "number");
    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0]?.to, "8705812936");
    assert.equal(sentMessages[0]?.text, "111");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("host feishu delivery sent carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    enableHostFeishuDelivery: true,
    hostDeliveryPollMs: 60_000,
    enableContinuationRunner: false,
  });

  try {
    await writeSendInstruction(runtimeRoot, "instruction-1.json", {
      schema: "openclaw.task-system.send-instruction.v1",
      task_id: "task-host-1",
      agent_id: "main",
      session_key: "agent:main:feishu:direct:ou_xxx",
      channel: "feishu",
      account_id: "acct-1",
      chat_id: "chat-1",
      message: "host path message",
    });
    await plugin.start();

    const delivered = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "host-feishu-delivery:sent",
      1500,
    );
    assert.equal(delivered?.payload?.schedulerDecision, "sent");
    assert.equal(delivered?.payload?.audienceKey, "feishu:acct-1:chat-1");
    assert.equal(delivered?.payload?.taskId, "task-host-1");
    assert.equal(delivered?.payload?.runner, "host-feishu-delivery");
    assert.equal(delivered?.payload?.lifecycleStage, "delivery-sent");
    assert.equal(delivered?.payload?.deliveryPath, "plugin-host");
    assert.equal(delivered?.payload?.reason, "host-feishu-send-succeeded");
    assert.equal(typeof delivered?.payload?.enqueueToken, "number");
    assert.equal(delivered?.payload?.instructionName, "instruction-1.json");
    assert.equal(sentMessages.length, 1);
    assert.equal(sentMessages[0]?.to, "chat-1");
    assert.equal(sentMessages[0]?.accountId, "acct-1");
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("host feishu delivery error carries scheduler diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    enableHostFeishuDelivery: true,
    hostDeliveryPollMs: 60_000,
    enableContinuationRunner: false,
    outboundAdapterMode: "error",
    outboundErrorMessage: "host-send-failed",
  });

  try {
    await writeSendInstruction(runtimeRoot, "instruction-2.json", {
      schema: "openclaw.task-system.send-instruction.v1",
      task_id: "task-host-2",
      agent_id: "main",
      session_key: "agent:main:feishu:direct:ou_yyy",
      channel: "feishu",
      account_id: "acct-2",
      chat_id: "chat-2",
      message: "host path failed message",
    });
    await plugin.start();

    const failed = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "host-feishu-delivery:error",
      1500,
    );
    assert.equal(failed?.payload?.schedulerDecision, "error");
    assert.equal(failed?.payload?.audienceKey, "feishu:acct-2:chat-2");
    assert.equal(failed?.payload?.taskId, "task-host-2");
    assert.equal(failed?.payload?.runner, "host-feishu-delivery");
    assert.equal(failed?.payload?.lifecycleStage, "delivery-error");
    assert.equal(failed?.payload?.deliveryPath, "plugin-host");
    assert.equal(failed?.payload?.reason, "host-feishu-send-failed");
    assert.equal(typeof failed?.payload?.enqueueToken, "number");
    assert.equal(failed?.payload?.instructionName, "instruction-2.json");
    assert.equal(failed?.payload?.error, "host-send-failed");
    assert.equal(sentMessages.length, 0);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("host feishu delivery adapter-unavailable carries unified runner diagnostics", async () => {
  resetGlobalState();
  const { runtimeRoot } = await createFakeRuntimeRoot();
  const sentMessages = [];
  const plugin = createApi(runtimeRoot, sentMessages, {
    enableHostFeishuDelivery: true,
    hostDeliveryPollMs: 60_000,
    enableContinuationRunner: false,
    outboundAdapterMode: "unavailable",
  });

  try {
    await writeSendInstruction(runtimeRoot, "instruction-3.json", {
      schema: "openclaw.task-system.send-instruction.v1",
      task_id: "task-host-3",
      agent_id: "main",
      session_key: "agent:main:feishu:direct:ou_zzz",
      channel: "feishu",
      account_id: "acct-3",
      chat_id: "chat-3",
      message: "host path unavailable message",
    });
    await plugin.start();

    const unavailable = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "host-feishu-delivery:adapter-unavailable",
      1500,
    );
    assert.equal(unavailable?.payload?.schedulerDecision, "adapter-unavailable");
    assert.equal(unavailable?.payload?.runner, "host-feishu-delivery");
    assert.equal(unavailable?.payload?.lifecycleStage, "delivery-adapter-unavailable");
    assert.equal(unavailable?.payload?.deliveryPath, "plugin-host");
    assert.equal(unavailable?.payload?.reason, "host-feishu-adapter-unavailable");
    assert.equal(unavailable?.payload?.instructionName, "instruction-3.json");
    assert.equal(sentMessages.length, 0);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});

test("startup watchdog recovery carries lifecycle scheduler diagnostics", async () => {
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
    gatewayCallResponses: {
      "chat.send": {
        ok: true,
        delivered: true,
      },
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

    const kickoff = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "watchdog-auto-recover:startup-kickoff" && entry.payload?.attempt === "initial",
      1500,
    );
    assert.equal(kickoff?.payload?.startupRecovery, true);
    assert.equal(kickoff?.payload?.schedulerDecision, "entered");
    assert.equal(kickoff?.payload?.reason, "startup-watchdog-recovery");

    const dispatch = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "watchdog-auto-recover:startup-dispatch",
      1500,
    );
    assert.equal(dispatch?.payload?.startupRecovery, true);
    assert.equal(dispatch?.payload?.schedulerDecision, "sent");
    assert.equal(dispatch?.payload?.reason, "startup-watchdog-recovery-dispatch");
    assert.equal(dispatch?.payload?.audienceKey, "feishu:acct-resume:chat-resume");
    assert.equal(dispatch?.payload?.sessionKey, "agent:main:feishu:direct:ou_resume");

    const gatewayOk = await waitForDebugEvent(
      runtimeRoot,
      (entry) => entry.event === "gateway:chat.send:ok",
      1500,
    );
    assert.equal(gatewayOk?.payload?.ok, true);
    assert.equal(gatewayOk?.payload?.delivered, true);
  } finally {
    await cleanupRuntime(plugin, runtimeRoot);
  }
});
