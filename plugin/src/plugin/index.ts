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
  syncProgressOnMessageSending?: boolean;
  finalizeOnAgentEnd?: boolean;
  minProgressMessageLength?: number;
  ignoreProgressPatterns?: string[];
  enableHostFeishuDelivery?: boolean;
  hostDeliveryPollMs?: number;
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

function normalizeText(value: string): string {
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
      await callHook(api, config, "register", {
        agent_id: agentId,
        session_key: sessionKey,
        channel: event.channel ?? ctx.channelId ?? "unknown",
        account_id: ctx.accountId ?? "",
        chat_id: ctx.conversationId ?? sessionKey,
        user_id: event.senderId ?? ctx.senderId ?? "",
        user_request: event.body || event.content,
      });
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
          return;
        }
        hostDeliveryTimer = setInterval(() => {
          void processHostDeliveryQueue(api, config);
        }, config.hostDeliveryPollMs);
        await processHostDeliveryQueue(api, config);
      },
      async stop() {
        if (hostDeliveryTimer) {
          clearInterval(hostDeliveryTimer);
          hostDeliveryTimer = null;
        }
      },
    });

    api.logger.info(`[task-system] plugin loaded (root=${config.runtimeRoot})`);
  },
});

export default taskSystemPlugin;
