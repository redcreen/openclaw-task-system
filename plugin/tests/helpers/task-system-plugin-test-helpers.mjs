import os from "node:os";
import path from "node:path";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";

import taskSystemPlugin from "../../src/plugin/index.ts";

export const EARLY_ACK_STATE_KEY = "__openclawTaskSystemEarlyAckState";
export const PRE_REGISTER_STATE_KEY = "__openclawTaskSystemPreRegisterState";

export function buildStateKey(channel, accountId, chatId) {
  return `${String(channel || "").trim().toLowerCase()}:${String(accountId || "").trim()}:${String(chatId || "").trim()}`;
}

export function buildQueueIdentity({ channel = "feishu", accountId = "acct-1", conversationId = "chat-1", senderId = "user-1" } = {}) {
  return {
    channel,
    accountId,
    conversationId,
    senderId,
    sessionKey: `agent:main:${channel}:${accountId}:${senderId}`,
    scope: "direct",
    queueKey: buildStateKey(channel, accountId, conversationId),
  };
}

export function buildRegisterDecision(overrides = {}) {
  return {
    should_register_task: true,
    classification_reason: "long-task",
    task_id: "task-pre",
    task_status: "queued",
    queue_position: 2,
    ahead_count: 1,
    running_count: 1,
    active_count: 2,
    estimated_wait_seconds: 45,
    ...overrides,
  };
}

export function buildCanonicalSnapshotEntry({
  channel = "feishu",
  accountId = "acct-1",
  conversationId = "chat-1",
  senderId = "user-1",
  content = "在么",
  registerDecision = buildRegisterDecision(),
  earlyAckSent = false,
  messageId = "",
  threadId = "",
} = {}) {
  const ts = Date.now();
  const queueIdentity = buildQueueIdentity({ channel, accountId, conversationId, senderId });
  return {
    version: 2,
    timestamp: ts,
    preRegisterSnapshot: {
      version: 1,
      queueKey: queueIdentity.queueKey,
      queueIdentity,
      content,
      contentFingerprint: content,
      senderId,
      messageId,
      threadId,
      arrivalTs: ts,
      snapshotTs: ts,
      registerDecision,
      ack: {
        earlyAckEligible: true,
        earlyAckSent,
        earlyAckSentAt: ts,
      },
    },
    registerResult: registerDecision,
    earlyAckSent,
  };
}

export function buildEarlyAckMarker({
  channel = "feishu",
  accountId = "acct-1",
  conversationId = "chat-1",
  messageId = "msg-1",
  sentAt = Date.now(),
} = {}) {
  return {
    version: 1,
    queueKey: buildStateKey(channel, accountId, conversationId),
    sentAt,
    channel,
    accountId,
    conversationId,
    messageId,
  };
}

export async function createFakeRuntimeRoot(options = {}) {
  const runtimeRoot = await mkdtemp(path.join(os.tmpdir(), "openclaw-task-system-plugin-"));
  const runtimeDir = path.join(runtimeRoot, "scripts", "runtime");
  const callsPath = path.join(runtimeRoot, "hook-calls.jsonl");
  const gatewayCallsPath = path.join(runtimeRoot, "gateway-calls.jsonl");
  const registerResponse = options.registerResponse ?? {
    should_register_task: true,
    classification_reason: "long-task",
    task_id: "task-123",
    task_status: "queued",
    queue_position: 2,
    ahead_count: 1,
    running_count: 1,
    active_count: 2,
    estimated_wait_seconds: 45,
  };
  const registerResponses = Array.isArray(options.registerResponses) ? options.registerResponses : null;
  const followupResponse = options.followupResponse ?? { should_send: false };
  const finalizeActiveResponse = options.finalizeActiveResponse ?? { updated: true };
  const mainContinuityResponse = options.mainContinuityResponse ?? {
    runbook_status: "ok",
    primary_action_kind: "none",
    control_plane_message: {
      schema: "openclaw.task-system.control-plane.v1",
      kind: "continuity-summary",
      event_name: "continuity-summary",
      priority: "p1-task-management",
      text: "当前没有需要立即处理的 continuity 风险。",
      session_key: "agent:main:telegram:direct:8705812936",
      metadata: {
        auto_resume_ready: false,
        auto_resume_safe_to_apply: false,
        primary_action_kind: "none",
        primary_action_command: null,
        top_risk_session_key: null,
      },
    },
  };
  const mainTasksSummaryResponse = options.mainTasksSummaryResponse ?? {
    task_count: 2,
    control_plane_message: {
      schema: "openclaw.task-system.control-plane.v1",
      kind: "main-tasks-summary",
      event_name: "main-tasks-summary",
      priority: "p1-task-management",
      text: "当前会话共有 2 条活动任务：处理中：正在处理的任务；排队中，第 2 位：排队中的任务",
      session_key: "agent:main:telegram:direct:8705812936",
      metadata: {
        task_count: 2,
        focus_session_key: "agent:main:telegram:direct:8705812936",
      },
    },
  };
  const taskmonitorControlResponse = options.taskmonitorControlResponse ?? {
    ok: true,
    enabled: false,
    message: "已关闭当前会话的 taskmonitor；后续消息将不再进入 task system 监控。",
    control_plane_message: {
      schema: "openclaw.task-system.control-plane.v1",
      kind: "taskmonitor-updated",
      event_name: "taskmonitor-disabled",
      priority: "p1-task-management",
      text: "已关闭当前会话的 taskmonitor；后续消息将不再进入 task system 监控。",
      session_key: "agent:main:telegram:direct:8705812936",
      metadata: {
        enabled: false,
        action: "off",
      },
    },
  };
  const claimDueContinuationsResponse = options.claimDueContinuationsResponse ?? { tasks: [] };
  const fulfillDueContinuationResponse = options.fulfillDueContinuationResponse ?? { updated: false };
  const watchdogAutoRecoverResponse = options.watchdogAutoRecoverResponse ?? {};
  const createFollowupPlanResponse = options.createFollowupPlanResponse ?? {
    ok: true,
    plan_id: "plan-123",
    source_task_id: "task-123",
    due_at: "2026-04-06T12:00:00+08:00",
    kind: "delayed-reply",
  };
  const attachPromiseGuardResponse = options.attachPromiseGuardResponse ?? {
    ok: true,
    status: "armed",
    source_task_id: "task-123",
  };
  const scheduleFollowupFromPlanResponse = options.scheduleFollowupFromPlanResponse ?? {
    ok: true,
    followup_task_id: "task-followup-123",
    task_status: "paused",
  };
  const finalizePlannedFollowupResponse = options.finalizePlannedFollowupResponse ?? {
    ok: true,
    status: "linked",
    followup_task_id: "task-followup-123",
  };
  const resolveActiveResponse = options.resolveActiveResponse ?? {
    found: true,
    task_id: "task-123",
    status: "running",
  };
  const gatewayCallResponses = options.gatewayCallResponses ?? {};
  const gatewayCallFailures = options.gatewayCallFailures ?? {};
  const hookFailureCommands = Array.isArray(options.hookFailureCommands) ? options.hookFailureCommands : [];
  const followupDelayMs = Number.isFinite(options.followupDelayMs) ? Number(options.followupDelayMs) : 0;
  const serializedRegisterResponse = JSON.stringify(JSON.stringify(registerResponse));
  const serializedRegisterResponses = JSON.stringify(JSON.stringify(registerResponses));
  const serializedFollowupResponse = JSON.stringify(JSON.stringify(followupResponse));
  const serializedFinalizeActiveResponse = JSON.stringify(JSON.stringify(finalizeActiveResponse));
  const serializedMainContinuityResponse = JSON.stringify(JSON.stringify(mainContinuityResponse));
  const serializedMainTasksSummaryResponse = JSON.stringify(JSON.stringify(mainTasksSummaryResponse));
  const serializedTaskmonitorControlResponse = JSON.stringify(JSON.stringify(taskmonitorControlResponse));
  const serializedClaimDueContinuationsResponse = JSON.stringify(JSON.stringify(claimDueContinuationsResponse));
  const serializedFulfillDueContinuationResponse = JSON.stringify(JSON.stringify(fulfillDueContinuationResponse));
  const serializedWatchdogAutoRecoverResponse = JSON.stringify(JSON.stringify(watchdogAutoRecoverResponse));
  const serializedCreateFollowupPlanResponse = JSON.stringify(JSON.stringify(createFollowupPlanResponse));
  const serializedAttachPromiseGuardResponse = JSON.stringify(JSON.stringify(attachPromiseGuardResponse));
  const serializedScheduleFollowupFromPlanResponse = JSON.stringify(JSON.stringify(scheduleFollowupFromPlanResponse));
  const serializedFinalizePlannedFollowupResponse = JSON.stringify(JSON.stringify(finalizePlannedFollowupResponse));
  const serializedResolveActiveResponse = JSON.stringify(JSON.stringify(resolveActiveResponse));
  const serializedGatewayCallResponses = JSON.stringify(JSON.stringify(gatewayCallResponses));
  const serializedGatewayCallFailures = JSON.stringify(JSON.stringify(gatewayCallFailures));
  const serializedHookFailureCommands = JSON.stringify(JSON.stringify(hookFailureCommands));

  await mkdir(runtimeDir, { recursive: true });
  await writeFile(
    path.join(runtimeDir, "openclaw_hooks.py"),
    `#!/usr/bin/env python3
import json
import sys
from pathlib import Path

payload = json.load(sys.stdin)
command = sys.argv[1]
runtime_root = Path(__file__).resolve().parents[2]
calls_path = runtime_root / "hook-calls.jsonl"
failure_commands = set(json.loads(${serializedHookFailureCommands}))
with calls_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"command": command, "payload": payload}, ensure_ascii=False) + "\\n")

if command in failure_commands:
    sys.stderr.write(f"simulated {command} failure")
    sys.exit(1)

if command == "taskmonitor-status":
    print(json.dumps({"enabled": True}, ensure_ascii=False))
elif command == "taskmonitor-control":
    print(json.dumps(json.loads(${serializedTaskmonitorControlResponse}), ensure_ascii=False))
elif command == "main-continuity":
    print(json.dumps(json.loads(${serializedMainContinuityResponse}), ensure_ascii=False))
elif command == "main-tasks-summary":
    print(json.dumps(json.loads(${serializedMainTasksSummaryResponse}), ensure_ascii=False))
elif command == "claim-due-continuations":
    print(json.dumps(json.loads(${serializedClaimDueContinuationsResponse}), ensure_ascii=False))
elif command == "fulfill-due-continuation":
    print(json.dumps(json.loads(${serializedFulfillDueContinuationResponse}), ensure_ascii=False))
elif command == "watchdog-auto-recover":
    print(json.dumps(json.loads(${serializedWatchdogAutoRecoverResponse}), ensure_ascii=False))
elif command == "create-followup-plan":
    print(json.dumps(json.loads(${serializedCreateFollowupPlanResponse}), ensure_ascii=False))
elif command == "attach-promise-guard":
    print(json.dumps(json.loads(${serializedAttachPromiseGuardResponse}), ensure_ascii=False))
elif command == "schedule-followup-from-plan":
    print(json.dumps(json.loads(${serializedScheduleFollowupFromPlanResponse}), ensure_ascii=False))
elif command == "finalize-planned-followup":
    print(json.dumps(json.loads(${serializedFinalizePlannedFollowupResponse}), ensure_ascii=False))
elif command == "resolve-active":
    print(json.dumps(json.loads(${serializedResolveActiveResponse}), ensure_ascii=False))
elif command == "register":
    responses = json.loads(${serializedRegisterResponses})
    if isinstance(responses, list) and responses:
        raw = calls_path.read_text(encoding="utf-8") if calls_path.exists() else ""
        register_count = sum(
            1
            for line in raw.splitlines()
            if line.strip() and json.loads(line).get("command") == "register"
        )
        response = responses[min(max(register_count - 1, 0), len(responses) - 1)]
        print(json.dumps(response, ensure_ascii=False))
    else:
        print(json.dumps(json.loads(${serializedRegisterResponse}), ensure_ascii=False))
elif command == "finalize-active":
    print(json.dumps(json.loads(${serializedFinalizeActiveResponse}), ensure_ascii=False))
elif command == "should-send-short-followup":
    if ${JSON.stringify(followupDelayMs)} > 0:
        import time
        time.sleep(${JSON.stringify(followupDelayMs)} / 1000.0)
    print(json.dumps(json.loads(${serializedFollowupResponse}), ensure_ascii=False))
else:
    print("{}")
`,
    "utf8",
  );
  const binDir = path.join(runtimeRoot, "bin");
  await mkdir(binDir, { recursive: true });
  await writeFile(
    path.join(binDir, "openclaw"),
    `#!/usr/bin/env python3
import json
import sys
from pathlib import Path

runtime_root = Path(__file__).resolve().parents[1]
calls_path = runtime_root / "gateway-calls.jsonl"
responses = json.loads(${serializedGatewayCallResponses})
failures = json.loads(${serializedGatewayCallFailures})
argv = sys.argv[1:]
with calls_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({"argv": argv}, ensure_ascii=False) + "\\n")
method = argv[2] if len(argv) >= 3 else ""
if method in failures:
    sys.stderr.write(str(failures.get(method) or f"simulated {method} failure"))
    sys.exit(1)
response = responses.get(method, {})
print(json.dumps(response, ensure_ascii=False))
`,
    { encoding: "utf8", mode: 0o755 },
  );
  return { runtimeRoot, callsPath, gatewayCallsPath, openclawBin: path.join(binDir, "openclaw") };
}

export function createApi(runtimeRoot, sentMessages, pluginConfigOverrides = {}) {
  const handlers = new Map();
  const services = [];
  const registeredTools = new Map();
  const outboundSendDelayMs = Number.isFinite(pluginConfigOverrides.outboundSendDelayMs)
    ? Number(pluginConfigOverrides.outboundSendDelayMs)
    : 0;
  const outboundAdapterMode = typeof pluginConfigOverrides.outboundAdapterMode === "string"
    ? pluginConfigOverrides.outboundAdapterMode
    : "ok";
  const outboundErrorMessage = typeof pluginConfigOverrides.outboundErrorMessage === "string"
    ? pluginConfigOverrides.outboundErrorMessage
    : "simulated-outbound-error";
  const api = {
    pluginConfig: {
      runtimeRoot,
      pythonBin: "python3",
      debugLogPath: path.join(runtimeRoot, "plugin-debug.jsonl"),
      enableHostFeishuDelivery: false,
      enableContinuationRunner: false,
      enableWatchdogRecoveryRunner: false,
      sendImmediateAckForShortTasks: true,
      ...pluginConfigOverrides,
    },
    config: {},
    logger: {
      info() {},
      warn() {},
    },
    runtime: {
      channel: {
        outbound: {
          async loadAdapter() {
            if (outboundAdapterMode === "unavailable") {
              return null;
            }
            return {
              async sendText(payload) {
                if (outboundAdapterMode === "error") {
                  throw new Error(outboundErrorMessage);
                }
                if (outboundSendDelayMs > 0) {
                  await new Promise((resolve) => setTimeout(resolve, outboundSendDelayMs));
                }
                sentMessages.push(payload);
              },
            };
          },
        },
      },
    },
    on(eventName, handler) {
      handlers.set(eventName, handler);
    },
    registerTool(tool) {
      registeredTools.set(tool.name, tool);
    },
    registerService(service) {
      services.push(service);
    },
  };
  taskSystemPlugin.register(api);
  return {
    api,
    beforeDispatch: handlers.get("before_dispatch"),
    beforeAgentStart: handlers.get("before_agent_start"),
    beforePromptBuild: handlers.get("before_prompt_build"),
    beforeModelResolve: handlers.get("before_model_resolve"),
    messageSending: handlers.get("message_sending"),
    llmOutput: handlers.get("llm_output"),
    agentEnd: handlers.get("agent_end"),
    registeredTools,
    start: async () => {
      for (const service of services) {
        if (typeof service.start === "function") {
          await service.start();
        }
      }
    },
    stop: async () => {
      for (const service of services) {
        if (typeof service.stop === "function") {
          await service.stop();
        }
      }
    },
  };
}

export async function readDebugEvents(runtimeRoot) {
  try {
    const raw = await readFile(path.join(runtimeRoot, "plugin-debug.jsonl"), "utf8");
    return raw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line));
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return [];
    }
    throw error;
  }
}

export async function waitForDebugEvent(runtimeRoot, predicate, timeoutMs = 1500) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const events = await readDebugEvents(runtimeRoot);
    const match = events.find(predicate);
    if (match) {
      return match;
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  return null;
}

export async function readHookCommands(callsPath) {
  try {
    const raw = await readFile(callsPath, "utf8");
    return raw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line).command);
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return [];
    }
    throw error;
  }
}

export async function readHookCalls(callsPath) {
  try {
    const raw = await readFile(callsPath, "utf8");
    return raw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => JSON.parse(line));
  } catch (error) {
    if (error && typeof error === "object" && "code" in error && error.code === "ENOENT") {
      return [];
    }
    throw error;
  }
}

export function resetGlobalState() {
  globalThis[EARLY_ACK_STATE_KEY] = new Map();
  globalThis[PRE_REGISTER_STATE_KEY] = new Map();
}

export async function writeSendInstruction(runtimeRoot, name, payload) {
  const dir = path.join(runtimeRoot, "data", "send-instructions");
  await mkdir(dir, { recursive: true });
  await writeFile(path.join(dir, name), JSON.stringify(payload, null, 2) + "\n", "utf8");
}

export async function cleanupRuntime(plugin, runtimeRoot) {
  await plugin.stop();
  await rm(runtimeRoot, { recursive: true, force: true });
  resetGlobalState();
}
