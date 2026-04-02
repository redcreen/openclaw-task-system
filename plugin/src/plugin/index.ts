import { execFile } from "node:child_process";
import { appendFile, mkdtemp, mkdir, readdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { tmpdir } from "node:os";
import { promisify } from "node:util";
import { definePluginEntry, type OpenClawPluginApi } from "openclaw/plugin-sdk/core";

const execFileAsync = promisify(execFile);

type TaskSystemPluginConfig = {
  enabled?: boolean;
  pythonBin?: string;
  runtimeRoot?: string;
  configPath?: string;
  debugLogPath?: string;
  defaultAgentId?: string;
  registerOnBeforeDispatch?: boolean;
  sendImmediateAckOnRegister?: boolean;
  sendImmediateAckForShortTasks?: boolean;
  immediateAckTemplate?: string;
  shortTaskFollowupTimeoutMs?: number;
  shortTaskFollowupTemplate?: string;
  syncProgressOnMessageSending?: boolean;
  finalizeOnAgentEnd?: boolean;
  minProgressMessageLength?: number;
  ignoreProgressPatterns?: string[];
  enableHostFeishuDelivery?: boolean;
  hostDeliveryPollMs?: number;
  enableContinuationRunner?: boolean;
  continuationPollMs?: number;
};

function normalizeConfig(raw: unknown): Required<TaskSystemPluginConfig> {
  const value = raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
  return {
    enabled: value.enabled !== false,
    pythonBin: typeof value.pythonBin === "string" && value.pythonBin.trim() ? value.pythonBin.trim() : "python3",
    runtimeRoot:
      typeof value.runtimeRoot === "string" && value.runtimeRoot.trim()
        ? value.runtimeRoot.trim()
        : `${process.env.HOME ?? ""}/.openclaw/workspace/openclaw-task-system`,
    configPath: typeof value.configPath === "string" ? value.configPath.trim() : "",
    debugLogPath:
      typeof value.debugLogPath === "string" && value.debugLogPath.trim()
        ? value.debugLogPath.trim()
        : "",
    defaultAgentId:
      typeof value.defaultAgentId === "string" && value.defaultAgentId.trim()
        ? value.defaultAgentId.trim()
        : "main",
    registerOnBeforeDispatch: value.registerOnBeforeDispatch !== false,
    sendImmediateAckOnRegister: value.sendImmediateAckOnRegister !== false,
    sendImmediateAckForShortTasks: value.sendImmediateAckForShortTasks !== false,
    immediateAckTemplate:
      typeof value.immediateAckTemplate === "string" && value.immediateAckTemplate.trim()
        ? value.immediateAckTemplate.trim()
        : "已收到，正在开始处理；如果 30 秒内还没有新的阶段结果，我会先同步当前进展。",
    shortTaskFollowupTimeoutMs:
      typeof value.shortTaskFollowupTimeoutMs === "number" && Number.isFinite(value.shortTaskFollowupTimeoutMs)
        ? Math.max(1000, Math.trunc(value.shortTaskFollowupTimeoutMs))
        : 30000,
    shortTaskFollowupTemplate:
      typeof value.shortTaskFollowupTemplate === "string" && value.shortTaskFollowupTemplate.trim()
        ? value.shortTaskFollowupTemplate.trim()
        : "已收到你的消息，当前仍在处理中；稍后给你正式结果。",
    syncProgressOnMessageSending: value.syncProgressOnMessageSending !== false,
    finalizeOnAgentEnd: value.finalizeOnAgentEnd !== false,
    minProgressMessageLength:
      typeof value.minProgressMessageLength === "number" && Number.isFinite(value.minProgressMessageLength)
        ? Math.max(1, Math.trunc(value.minProgressMessageLength))
        : 20,
    ignoreProgressPatterns: Array.isArray(value.ignoreProgressPatterns)
      ? value.ignoreProgressPatterns.filter((entry): entry is string => typeof entry === "string" && entry.trim().length > 0)
      : ["^收到$", "^好的$", "^继续$", "^处理中$", "^稍等$", "^thinking\\.\\.\\.$", "^\\.\\.\\.$"],
    enableHostFeishuDelivery: value.enableHostFeishuDelivery !== false,
    hostDeliveryPollMs:
      typeof value.hostDeliveryPollMs === "number" && Number.isFinite(value.hostDeliveryPollMs)
        ? Math.max(1000, Math.trunc(value.hostDeliveryPollMs))
        : 3000,
    enableContinuationRunner: value.enableContinuationRunner !== false,
    continuationPollMs:
      typeof value.continuationPollMs === "number" && Number.isFinite(value.continuationPollMs)
        ? Math.max(1000, Math.trunc(value.continuationPollMs))
        : 3000,
  };
}

function buildHooksScriptPath(config: Required<TaskSystemPluginConfig>): string {
  return `${config.runtimeRoot}/scripts/runtime/openclaw_hooks.py`;
}

async function appendDebugLog(
  config: Required<TaskSystemPluginConfig>,
  event: string,
  payload: Record<string, unknown>,
): Promise<void> {
  if (!config.debugLogPath) {
    return;
  }
  try {
    await mkdir(join(config.debugLogPath, ".."), { recursive: true });
    const line = JSON.stringify({
      ts: new Date().toISOString(),
      event,
      payload,
    });
    await appendFile(config.debugLogPath, `${line}\n`, "utf-8");
  } catch {
    return;
  }
}

async function callHook(
  api: OpenClawPluginApi,
  config: Required<TaskSystemPluginConfig>,
  command: string,
  payload: Record<string, unknown>,
): Promise<Record<string, unknown> | null> {
  const script = buildHooksScriptPath(config);
  const tempDir = await mkdtemp(join(tmpdir(), "openclaw-task-system-"));
  const tempPayloadPath = join(tempDir, "payload.json");
  await writeFile(tempPayloadPath, JSON.stringify(payload, null, 2), "utf-8");

  try {
    await appendDebugLog(config, `hook:${command}:start`, payload);
    const args = [script, command, tempPayloadPath];
    if (config.configPath) {
      args.push(config.configPath);
    }
    const result = await execFileAsync(config.pythonBin, args, {
      cwd: config.runtimeRoot,
      env: process.env,
    });
    const parsed = JSON.parse(result.stdout || "{}") as Record<string, unknown>;
    await appendDebugLog(config, `hook:${command}:ok`, parsed);
    return parsed;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await appendDebugLog(config, `hook:${command}:error`, { message });
    api.logger.warn(`[task-system] hook ${command} failed: ${message}`);
    return null;
  } finally {
    await rm(tempDir, { recursive: true, force: true }).catch(() => {});
  }
}

function buildSessionKey(channelId: string, conversationId?: string): string {
  const suffix = conversationId?.trim() ? conversationId.trim() : "unknown";
  return `${channelId}:${suffix}`;
}

function formatContinuationDelayLabel(continuationDueAt: string): string | null {
  if (!continuationDueAt) {
    return null;
  }
  const dueMs = Date.parse(continuationDueAt);
  if (!Number.isFinite(dueMs)) {
    return null;
  }
  const diffMs = Math.max(0, dueMs - Date.now());
  const diffSeconds = Math.max(1, Math.ceil(diffMs / 1000));
  if (diffSeconds < 60) {
    return `预计约 ${diffSeconds} 秒后`;
  }
  const diffMinutes = Math.max(1, Math.ceil(diffSeconds / 60));
  return `预计约 ${diffMinutes} 分钟后`;
}

function normalizeText(value: unknown): string {
  if (typeof value !== "string") {
    if (value === null || value === undefined) {
      return "";
    }
    return String(value).replace(/\s+/g, " ").trim();
  }
  return value.replace(/\s+/g, " ").trim();
}

function isInternalRetryPrompt(prompt: string): boolean {
  const normalized = normalizeText(prompt).toLowerCase();
  return normalized === "continue where you left off. the previous model attempt failed or timed out.";
}

function shouldSyncProgress(content: string, config: Required<TaskSystemPluginConfig>): boolean {
  const normalized = normalizeText(content);
  if (normalized.length < config.minProgressMessageLength) {
    return false;
  }

  for (const pattern of config.ignoreProgressPatterns) {
    try {
      if (new RegExp(pattern, "i").test(normalized)) {
        return false;
      }
    } catch {
      continue;
    }
  }

  return true;
}

type SendInstructionPayload = {
  schema?: string;
  task_id?: string;
  agent_id?: string;
  session_key?: string;
  channel?: string;
  account_id?: string;
  chat_id?: string;
  message?: string;
};

function instructionDir(config: Required<TaskSystemPluginConfig>): string {
  return join(config.runtimeRoot, "data", "send-instructions");
}

function dispatchResultDir(config: Required<TaskSystemPluginConfig>): string {
  return join(config.runtimeRoot, "data", "dispatch-results");
}

function processedInstructionDir(config: Required<TaskSystemPluginConfig>): string {
  return join(config.runtimeRoot, "data", "processed-instructions");
}

function failedInstructionDir(config: Required<TaskSystemPluginConfig>): string {
  return join(config.runtimeRoot, "data", "failed-instructions");
}

async function ensureHostDeliveryDirs(config: Required<TaskSystemPluginConfig>): Promise<void> {
  await mkdir(dispatchResultDir(config), { recursive: true });
  await mkdir(processedInstructionDir(config), { recursive: true });
  await mkdir(failedInstructionDir(config), { recursive: true });
}

function shouldUseHostFeishuDelivery(payload: SendInstructionPayload): boolean {
  return String(payload.channel || "").trim().toLowerCase() === "feishu";
}

async function loadSendInstruction(path: string): Promise<SendInstructionPayload> {
  return JSON.parse(await readFile(path, "utf-8")) as SendInstructionPayload;
}

async function writeHostDispatchResult(
  config: Required<TaskSystemPluginConfig>,
  name: string,
  payload: SendInstructionPayload,
  result: Record<string, unknown>,
): Promise<void> {
  await ensureHostDeliveryDirs(config);
  await writeFile(
    join(dispatchResultDir(config), name),
    JSON.stringify(
      {
        schema: "openclaw.task-system.dispatch-result.v1",
        task_id: payload.task_id || null,
        agent_id: payload.agent_id || null,
        session_key: payload.session_key || null,
        channel: payload.channel || null,
        account_id: payload.account_id || null,
        chat_id: payload.chat_id || null,
        message: payload.message || null,
        ...result,
      },
      null,
      2,
    ) + "\n",
    "utf-8",
  );
}

async function archiveHostInstruction(
  config: Required<TaskSystemPluginConfig>,
  sourcePath: string,
  name: string,
  succeeded: boolean,
): Promise<string> {
  await ensureHostDeliveryDirs(config);
  const target = join(succeeded ? processedInstructionDir(config) : failedInstructionDir(config), name);
  await rename(sourcePath, target);
  return target;
}

async function processFeishuInstruction(
  api: OpenClawPluginApi,
  config: Required<TaskSystemPluginConfig>,
  path: string,
): Promise<void> {
  const name = basename(path);
  const payload = await loadSendInstruction(path);
  if (!shouldUseHostFeishuDelivery(payload)) {
    return;
  }

  const accountId = String(payload.account_id || "").trim();
  const chatId = String(payload.chat_id || "").trim();
  const message = String(payload.message || "").trim();
  if (!accountId || !chatId || !message) {
    await writeHostDispatchResult(config, name, payload, {
      action: "send",
      reason: !accountId ? "missing-account-id" : !chatId ? "missing-chat-id" : "empty-message",
      command: ["host-feishu-send"],
      executed: false,
      exit_code: null,
      stdout: null,
      stderr: null,
      via: "plugin-host",
    });
    await archiveHostInstruction(config, path, name, { succeeded: false });
    return;
  }

  const adapter = await api.runtime.channel.outbound.loadAdapter("feishu");
  if (!adapter?.sendText) {
    await writeHostDispatchResult(config, name, payload, {
      action: "send",
      reason: "feishu-adapter-unavailable",
      command: ["host-feishu-send"],
      executed: false,
      exit_code: null,
      stdout: null,
      stderr: null,
      via: "plugin-host",
    });
    await archiveHostInstruction(config, path, name, { succeeded: false });
    return;
  }

  try {
    const delivery = await adapter.sendText({
      cfg: api.config,
      to: chatId,
      text: message,
      accountId,
    });
    await writeHostDispatchResult(config, name, payload, {
      action: "send",
      reason: "supported-host-feishu",
      command: ["host-feishu-send"],
      executed: true,
      exit_code: 0,
      stdout: null,
      stderr: null,
      via: "plugin-host",
      result: delivery,
    });
    await archiveHostInstruction(config, path, name, { succeeded: true });
    await appendDebugLog(config, "host-feishu-delivery:sent", {
      taskId: payload.task_id || null,
      accountId,
      chatId,
    });
  } catch (error) {
    const messageText = error instanceof Error ? error.message : String(error);
    await writeHostDispatchResult(config, name, payload, {
      action: "send",
      reason: "host-feishu-send-failed",
      command: ["host-feishu-send"],
      executed: true,
      exit_code: 1,
      stdout: null,
      stderr: messageText,
      via: "plugin-host",
    });
    await archiveHostInstruction(config, path, name, { succeeded: false });
    await appendDebugLog(config, "host-feishu-delivery:error", {
      taskId: payload.task_id || null,
      error: messageText,
    });
  }
}

async function processHostDeliveryQueue(api: OpenClawPluginApi, config: Required<TaskSystemPluginConfig>): Promise<void> {
  if (!config.enableHostFeishuDelivery) {
    return;
  }
  const dir = instructionDir(config);
  await mkdir(dir, { recursive: true });
  const names = (await readdir(dir)).filter((entry) => entry.endsWith(".json")).sort();
  for (const name of names) {
    const path = join(dir, name);
    const payload = await loadSendInstruction(path).catch(() => null);
    if (!payload || !shouldUseHostFeishuDelivery(payload)) {
      continue;
    }
    await processFeishuInstruction(api, config, path);
  }
}

async function processDueContinuations(api: OpenClawPluginApi, config: Required<TaskSystemPluginConfig>): Promise<void> {
  if (!config.enableContinuationRunner) {
    return;
  }
  const claimed = await callHook(api, config, "claim-due-continuations", {});
  const tasks = Array.isArray(claimed?.tasks) ? claimed.tasks : [];
  for (const task of tasks) {
    const payload = task as Record<string, unknown>;
    const channel = normalizeText(String(payload.channel || ""));
    const chatId = normalizeText(String(payload.chat_id || ""));
    const taskId = normalizeText(String(payload.task_id || ""));
    const sessionKey = normalizeText(String(payload.session_key || ""));
    const replyText = normalizeText(String(payload.reply_text || ""));
    if (!channel || !chatId || !taskId || !replyText) {
      continue;
    }
    try {
      await sendStatusMessage(api, config, {
        channel,
        accountId: normalizeText(String(payload.account_id || "")),
        chatId,
        sessionKey,
        message: replyText,
        eventName: "continuation-delivery",
      });
      await callHook(api, config, "completed", {
        task_id: taskId,
        result_summary: `continuation reply sent: ${replyText}`.slice(0, 240),
      });
    } catch (error) {
      const messageText = error instanceof Error ? error.message : String(error);
      await callHook(api, config, "blocked", {
        task_id: taskId,
        reason: `continuation delivery failed: ${messageText}`.slice(0, 240),
      });
    }
  }
}

async function sendImmediateAck(
  api: OpenClawPluginApi,
  config: Required<TaskSystemPluginConfig>,
  payload: {
    channel: string;
    accountId?: string;
    chatId: string;
    taskId: string;
    sessionKey: string;
    message?: string;
  },
): Promise<void> {
  if (!config.sendImmediateAckOnRegister) {
    return;
  }
  const channel = String(payload.channel || "").trim().toLowerCase();
  if (!channel || channel === "agent") {
    return;
  }
  const chatId = String(payload.chatId || "").trim();
  const message = normalizeText(payload.message || config.immediateAckTemplate);
  if (!chatId || !message) {
    return;
  }

  try {
    const adapter = await api.runtime.channel.outbound.loadAdapter(channel);
    if (!adapter?.sendText) {
      await appendDebugLog(config, "immediate-ack:adapter-unavailable", {
        channel,
        taskId: payload.taskId,
        sessionKey: payload.sessionKey,
      });
      return;
    }

    await adapter.sendText({
      cfg: api.config,
      to: chatId,
      text: message,
      accountId: payload.accountId || "",
    });
    await appendDebugLog(config, "immediate-ack:sent", {
      channel,
      chatId,
      taskId: payload.taskId,
      sessionKey: payload.sessionKey,
      message,
    });
  } catch (error) {
    const messageText = error instanceof Error ? error.message : String(error);
    await appendDebugLog(config, "immediate-ack:error", {
      channel,
      chatId,
      taskId: payload.taskId,
      sessionKey: payload.sessionKey,
      error: messageText,
    });
    api.logger.warn(`[task-system] immediate ack failed for ${channel}:${chatId}: ${messageText}`);
  }
}

type PendingReceipt = {
  sessionKey: string;
  channel: string;
  accountId?: string;
  chatId: string;
  taskKind: "short" | "long";
  timer: ReturnType<typeof setTimeout> | null;
};

function toInteger(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return Math.trunc(value);
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return Math.trunc(parsed);
    }
  }
  return null;
}

function buildImmediateReceiptMessage(
  config: Required<TaskSystemPluginConfig>,
  registerResult: Record<string, unknown> | null,
): string {
  const fallback = normalizeText(config.immediateAckTemplate);
  if (!registerResult) {
    return fallback;
  }
  const taskStatus = normalizeText(registerResult.task_status);
  const queuePosition = toInteger(registerResult.queue_position);
  const aheadCount = Math.max(toInteger(registerResult.ahead_count) ?? 0, 0);
  const runningCount = Math.max(toInteger(registerResult.running_count) ?? 0, 0);
  const activeCount = Math.max(toInteger(registerResult.active_count) ?? 0, 0);
  const continuationDueAt = normalizeText(String(registerResult.continuation_due_at || ""));

  if (taskStatus === "paused" && continuationDueAt) {
    const delayLabel = formatContinuationDelayLabel(continuationDueAt);
    if (delayLabel) {
      return `已收到，已安排后续继续执行；${delayLabel}，到点后我会主动回复。`;
    }
    return "已收到，已安排后续继续执行；到点后我会主动回复。";
  }

  if (taskStatus === "queued") {
    const position = queuePosition ?? aheadCount + 1;
    return `已收到，当前有 ${runningCount} 条任务正在处理；你的请求已进入队列，前面还有 ${aheadCount} 个号，你现在排第 ${position} 位。`;
  }
  if (taskStatus === "running" && activeCount > 1) {
    return `已收到，现在轮到你的请求开始处理了；当前队列里共有 ${activeCount} 条活动任务，我会继续同步真实进展。`;
  }
  if (taskStatus === "running") {
    return "已收到，正在开始处理；如果 30 秒内还没有新的阶段结果，我会先同步当前进展。";
  }
  return fallback;
}

async function sendStatusMessage(
  api: OpenClawPluginApi,
  config: Required<TaskSystemPluginConfig>,
  payload: {
    channel: string;
    accountId?: string;
    chatId: string;
    sessionKey: string;
    message: string;
    eventName: string;
  },
): Promise<void> {
  const channel = String(payload.channel || "").trim().toLowerCase();
  if (!channel || channel === "agent") {
    return;
  }
  const chatId = String(payload.chatId || "").trim();
  const message = normalizeText(payload.message);
  if (!chatId || !message) {
    return;
  }
  try {
    const adapter = await api.runtime.channel.outbound.loadAdapter(channel);
    if (!adapter?.sendText) {
      await appendDebugLog(config, `${payload.eventName}:adapter-unavailable`, {
        channel,
        chatId,
        sessionKey: payload.sessionKey,
      });
      return;
    }
    await adapter.sendText({
      cfg: api.config,
      to: chatId,
      text: message,
      accountId: payload.accountId || "",
    });
    await appendDebugLog(config, `${payload.eventName}:sent`, {
      channel,
      chatId,
      sessionKey: payload.sessionKey,
      message,
    });
  } catch (error) {
    const messageText = error instanceof Error ? error.message : String(error);
    await appendDebugLog(config, `${payload.eventName}:error`, {
      channel,
      chatId,
      sessionKey: payload.sessionKey,
      error: messageText,
    });
    api.logger.warn(`[task-system] ${payload.eventName} failed for ${channel}:${chatId}: ${messageText}`);
  }
}

function extractTextFromUnknown(value: unknown): string[] {
  if (typeof value === "string") {
    const normalized = normalizeText(value);
    return normalized ? [normalized] : [];
  }
  if (Array.isArray(value)) {
    return value.flatMap((entry) => extractTextFromUnknown(entry));
  }
  if (!value || typeof value !== "object") {
    return [];
  }

  const record = value as Record<string, unknown>;
  const direct = [
    ...extractTextFromUnknown(record.text),
    ...extractTextFromUnknown(record.content),
    ...extractTextFromUnknown(record.message),
  ];
  if (direct.length > 0) {
    return direct;
  }
  return Object.values(record).flatMap((entry) => extractTextFromUnknown(entry));
}

function summarizeAgentEnd(event: { messages: unknown[]; success: boolean; durationMs?: number }): string {
  const assistantMessages = event.messages.filter((entry) => {
    if (!entry || typeof entry !== "object") {
      return false;
    }
    const role = (entry as Record<string, unknown>).role;
    return typeof role === "string" && role.toLowerCase() === "assistant";
  });
  const latestAssistant = assistantMessages.at(-1);
  const texts = latestAssistant ? extractTextFromUnknown(latestAssistant).filter(Boolean) : [];
  const summary = texts.find((entry) => entry.length >= 20) || texts[0];
  if (summary) {
    return summary.slice(0, 240);
  }
  return event.success
    ? `agent run completed in ${event.durationMs ?? 0}ms`
    : `agent run failed after ${event.durationMs ?? 0}ms`;
}

const taskSystemPlugin = definePluginEntry({
  id: "openclaw-task-system",
  name: "OpenClaw Task System",
  description: "Plugin-first task lifecycle management for long-running OpenClaw work",
  configSchema: {
    parse(value: unknown) {
      return normalizeConfig(value);
    },
  },
  register(api: OpenClawPluginApi) {
    const config = normalizeConfig(api.pluginConfig);
    let hostDeliveryTimer: ReturnType<typeof setInterval> | null = null;
    let continuationTimer: ReturnType<typeof setInterval> | null = null;
    const pendingReceipts = new Map<string, PendingReceipt>();
    if (!config.enabled) {
      api.logger.info("[task-system] plugin loaded in disabled mode");
      return;
    }

    api.on("before_dispatch", async (event, ctx) => {
      if (!config.registerOnBeforeDispatch || !event.content?.trim()) {
        return;
      }
      const sessionKey = event.sessionKey || ctx.sessionKey || buildSessionKey(ctx.channelId ?? event.channel ?? "unknown", ctx.conversationId);
      const agentId = ctx.agentId || config.defaultAgentId;
      await appendDebugLog(config, "before_dispatch", {
        agentId,
        sessionKey,
        channel: event.channel ?? ctx.channelId ?? "unknown",
        content: normalizeText(event.content).slice(0, 240),
      });
      const registerResult = await callHook(api, config, "register", {
        agent_id: agentId,
        session_key: sessionKey,
        channel: event.channel ?? ctx.channelId ?? "unknown",
        account_id: ctx.accountId ?? "",
        chat_id: ctx.conversationId ?? sessionKey,
        user_id: event.senderId ?? ctx.senderId ?? "",
        user_request: event.body || event.content,
      });
      await appendDebugLog(config, "immediate-ack:decision", {
        sessionKey,
        channel: event.channel ?? ctx.channelId ?? "unknown",
        shouldRegisterTask: registerResult?.should_register_task ?? null,
        classificationReason: registerResult?.classification_reason ?? null,
        taskId: registerResult?.task_id ?? null,
      });
      const classificationReason = String(registerResult?.classification_reason || "").trim();
      const isLongTask = Boolean(registerResult?.should_register_task);
      const isExistingActive = classificationReason === "existing-active-task";
      const shouldSendImmediateAck =
        config.sendImmediateAckOnRegister &&
        ((isLongTask && !isExistingActive) || (!isLongTask && config.sendImmediateAckForShortTasks));
      const immediateAckMessage = buildImmediateReceiptMessage(config, registerResult);

      const existingReceipt = pendingReceipts.get(sessionKey);
      if (existingReceipt?.timer) {
        clearTimeout(existingReceipt.timer);
      }
      pendingReceipts.delete(sessionKey);

      if (shouldSendImmediateAck) {
        if (isLongTask && typeof registerResult?.task_id === "string" && registerResult.task_id.trim()) {
          await sendImmediateAck(api, config, {
            channel: event.channel ?? ctx.channelId ?? "unknown",
            accountId: ctx.accountId ?? "",
            chatId: ctx.conversationId ?? sessionKey,
            taskId: registerResult.task_id,
            sessionKey,
            message: immediateAckMessage,
          });
        } else {
          await sendStatusMessage(api, config, {
            channel: event.channel ?? ctx.channelId ?? "unknown",
            accountId: ctx.accountId ?? "",
            chatId: ctx.conversationId ?? sessionKey,
            sessionKey,
            message: immediateAckMessage,
            eventName: "immediate-ack",
          });
        }
      }

      if (!isLongTask && config.shortTaskFollowupTimeoutMs > 0) {
        const timer = setTimeout(() => {
          const pending = pendingReceipts.get(sessionKey);
          if (!pending) {
            return;
          }
          void sendStatusMessage(api, config, {
            channel: pending.channel,
            accountId: pending.accountId,
            chatId: pending.chatId,
            sessionKey: pending.sessionKey,
            message: config.shortTaskFollowupTemplate,
            eventName: "short-task-followup",
          });
        }, config.shortTaskFollowupTimeoutMs);

        pendingReceipts.set(sessionKey, {
          sessionKey,
          channel: event.channel ?? ctx.channelId ?? "unknown",
          accountId: ctx.accountId ?? "",
          chatId: ctx.conversationId ?? sessionKey,
          taskKind: "short",
          timer,
        });
      }
    });

    api.on("before_agent_start", async (event, ctx) => {
      if (!config.registerOnBeforeDispatch || !event.prompt?.trim()) {
        return;
      }
      if (isInternalRetryPrompt(event.prompt)) {
        await appendDebugLog(config, "before_agent_start:internal-retry", {
          agentId: ctx.agentId || config.defaultAgentId,
          sessionKey: ctx.sessionKey || "",
        });
        return;
      }
      if (ctx.trigger && ctx.trigger !== "user") {
        await appendDebugLog(config, "before_agent_start:ignored", {
          trigger: ctx.trigger,
          agentId: ctx.agentId || config.defaultAgentId,
          sessionKey: ctx.sessionKey || "",
        });
        return;
      }
      const sessionKey = ctx.sessionKey?.trim();
      if (!sessionKey) {
        await appendDebugLog(config, "before_agent_start:missing-session", {
          agentId: ctx.agentId || config.defaultAgentId,
          prompt: normalizeText(event.prompt).slice(0, 240),
        });
        return;
      }
      const agentId = ctx.agentId || config.defaultAgentId;
      await appendDebugLog(config, "before_agent_start", {
        agentId,
        sessionKey,
        trigger: ctx.trigger || "unknown",
        prompt: normalizeText(event.prompt).slice(0, 240),
      });
      await callHook(api, config, "register", {
        agent_id: agentId,
        session_key: sessionKey,
        channel: ctx.channelId || "agent",
        account_id: ctx.accountId ?? "",
        chat_id: ctx.sessionId || sessionKey,
        user_id: "",
        user_request: event.prompt,
      });
    });

    api.on("before_prompt_build", async (event, ctx) => {
      if (!config.registerOnBeforeDispatch || !event.prompt?.trim()) {
        return;
      }
      const sessionKey = ctx.sessionKey?.trim();
      if (!sessionKey) {
        await appendDebugLog(config, "before_prompt_build:missing-session", {
          agentId: ctx.agentId || config.defaultAgentId,
          prompt: normalizeText(event.prompt).slice(0, 240),
        });
        return;
      }
      const agentId = ctx.agentId || config.defaultAgentId;
      await appendDebugLog(config, "before_prompt_build", {
        agentId,
        sessionKey,
        trigger: ctx.trigger || "unknown",
        prompt: normalizeText(event.prompt).slice(0, 240),
      });
      await callHook(api, config, "register", {
        agent_id: agentId,
        session_key: sessionKey,
        channel: ctx.channelId || "agent",
        account_id: ctx.accountId ?? "",
        chat_id: ctx.sessionId || sessionKey,
        user_id: "",
        user_request: event.prompt,
      });
    });

    api.on("before_model_resolve", async (event, ctx) => {
      if (!event.prompt?.trim()) {
        return;
      }
      await appendDebugLog(config, "before_model_resolve", {
        agentId: ctx.agentId || config.defaultAgentId,
        sessionKey: ctx.sessionKey || "",
        trigger: ctx.trigger || "unknown",
        prompt: normalizeText(event.prompt).slice(0, 240),
      });
    });

    api.on("message_sending", async (event, ctx) => {
      if (!config.syncProgressOnMessageSending || !event.content?.trim()) {
        return;
      }
      if (ctx.sessionKey?.trim()) {
        const continuationFulfilled = await callHook(api, config, "fulfill-due-continuation", {
          agent_id: ctx.agentId || config.defaultAgentId,
          session_key: ctx.sessionKey,
          content: event.content,
        });
        if (continuationFulfilled?.updated) {
          await appendDebugLog(config, "message_sending:continuation-fulfilled", {
            agentId: ctx.agentId || config.defaultAgentId,
            sessionKey: ctx.sessionKey,
            matchedReplyText: continuationFulfilled.matched_reply_text ?? null,
          });
          return;
        }
      }
      if (!shouldSyncProgress(event.content, config)) {
        await appendDebugLog(config, "message_sending:ignored", {
          sessionKey: ctx.sessionKey || buildSessionKey(ctx.channelId, ctx.conversationId),
          content: normalizeText(event.content).slice(0, 240),
        });
        return;
      }
      const sessionKey = buildSessionKey(ctx.channelId, ctx.conversationId);
      const agentId = ctx.agentId || config.defaultAgentId;
      await appendDebugLog(config, "message_sending", {
        agentId,
        sessionKey,
        content: normalizeText(event.content).slice(0, 240),
      });
      await callHook(api, config, "progress-active", {
        agent_id: agentId,
        session_key: sessionKey,
        progress_note: normalizeText(event.content).slice(0, 240),
      });
    });

    api.on("llm_output", async (event, ctx) => {
      if (!config.syncProgressOnMessageSending) {
        return;
      }
      const sessionKey = ctx.sessionKey?.trim();
      if (!sessionKey) {
        return;
      }
      const text = normalizeText((event.assistantTexts || []).join("\n"));
      if (!text) {
        return;
      }
      const continuationFulfilled = await callHook(api, config, "fulfill-due-continuation", {
        agent_id: ctx.agentId || config.defaultAgentId,
        session_key: sessionKey,
        content: text,
      });
      if (continuationFulfilled?.updated) {
        await appendDebugLog(config, "llm_output:continuation-fulfilled", {
          agentId: ctx.agentId || config.defaultAgentId,
          sessionKey,
          matchedReplyText: continuationFulfilled.matched_reply_text ?? null,
          content: text.slice(0, 240),
        });
        return;
      }
      if (!shouldSyncProgress(text, config)) {
        await appendDebugLog(config, "llm_output:ignored", {
          agentId: ctx.agentId || config.defaultAgentId,
          sessionKey,
          content: text.slice(0, 240),
        });
        return;
      }
      const agentId = ctx.agentId || config.defaultAgentId;
      await appendDebugLog(config, "llm_output", {
        agentId,
        sessionKey,
        content: text.slice(0, 240),
      });
      await callHook(api, config, "progress-active", {
        agent_id: agentId,
        session_key: sessionKey,
        progress_note: text.slice(0, 240),
      });
    });

    api.on("agent_end", async (event, ctx) => {
      if (!config.finalizeOnAgentEnd || !ctx.sessionKey?.trim()) {
        return;
      }
      const pendingReceipt = pendingReceipts.get(ctx.sessionKey);
      if (pendingReceipt?.timer) {
        clearTimeout(pendingReceipt.timer);
      }
      pendingReceipts.delete(ctx.sessionKey);
      await appendDebugLog(config, "agent_end", {
        agentId: ctx.agentId || config.defaultAgentId,
        sessionKey: ctx.sessionKey,
        success: event.success,
        error: event.error ?? null,
      });
      await callHook(api, config, "finalize-active", {
        agent_id: ctx.agentId || config.defaultAgentId,
        session_key: ctx.sessionKey,
        success: event.success,
        result_summary: event.success ? summarizeAgentEnd(event) : undefined,
        error: event.error,
      });
    });

    api.registerService({
      id: "openclaw-task-system-host-delivery",
      async start() {
        if (!config.enableHostFeishuDelivery) {
          if (config.enableContinuationRunner) {
            continuationTimer = setInterval(() => {
              void processDueContinuations(api, config);
            }, config.continuationPollMs);
            await processDueContinuations(api, config);
          }
          return;
        }
        hostDeliveryTimer = setInterval(() => {
          void processHostDeliveryQueue(api, config);
        }, config.hostDeliveryPollMs);
        await processHostDeliveryQueue(api, config);
        if (config.enableContinuationRunner) {
          continuationTimer = setInterval(() => {
            void processDueContinuations(api, config);
          }, config.continuationPollMs);
          await processDueContinuations(api, config);
        }
      },
      async stop() {
        if (hostDeliveryTimer) {
          clearInterval(hostDeliveryTimer);
          hostDeliveryTimer = null;
        }
        if (continuationTimer) {
          clearInterval(continuationTimer);
          continuationTimer = null;
        }
        for (const pending of pendingReceipts.values()) {
          if (pending.timer) {
            clearTimeout(pending.timer);
          }
        }
        pendingReceipts.clear();
      },
    });

    api.logger.info(`[task-system] plugin loaded (root=${config.runtimeRoot})`);
  },
});

export default taskSystemPlugin;
