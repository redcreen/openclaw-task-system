import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { appendFile, mkdir, readdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname, basename, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk";

const INTERNAL_STARTUP_RESUME_MARKER = "[[TASK-SYSTEM-STARTUP-RESUME]]";
const EARLY_ACK_STATE_KEY = "__openclawTaskSystemEarlyAckState";
const EARLY_ACK_TTL_MS = 5 * 60 * 1000;
const PRE_REGISTER_STATE_KEY = "__openclawTaskSystemPreRegisterState";

type TaskSystemPluginConfig = {
  enabled?: boolean;
  taskMessagePrefix?: string;
  openclawBin?: string;
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
  enableWatchdogRecoveryRunner?: boolean;
  watchdogRecoveryPollMs?: number;
};

const INSTALLED_PLUGIN_ROOT = dirname(dirname(dirname(fileURLToPath(import.meta.url))));

function resolveBundledPath(...parts: string[]): string {
  return join(INSTALLED_PLUGIN_ROOT, ...parts);
}

function normalizeConfig(raw: unknown): Required<TaskSystemPluginConfig> {
  const value = raw && typeof raw === "object" && !Array.isArray(raw) ? (raw as Record<string, unknown>) : {};
  const runtimeRoot =
    typeof value.runtimeRoot === "string" && value.runtimeRoot.trim()
      ? value.runtimeRoot.trim()
      : INSTALLED_PLUGIN_ROOT;
  return {
    enabled: value.enabled !== false,
    taskMessagePrefix:
      typeof value.taskMessagePrefix === "string"
        ? value.taskMessagePrefix
        : "[wd] ",
    openclawBin:
      typeof value.openclawBin === "string" && value.openclawBin.trim()
        ? value.openclawBin.trim()
        : process.env.OPENCLAW_BIN?.trim() || "openclaw",
    pythonBin: typeof value.pythonBin === "string" && value.pythonBin.trim() ? value.pythonBin.trim() : "python3",
    runtimeRoot,
    configPath:
      typeof value.configPath === "string" && value.configPath.trim()
        ? value.configPath.trim()
        : join(runtimeRoot, "config", "task_system.json"),
    debugLogPath:
      typeof value.debugLogPath === "string" && value.debugLogPath.trim()
        ? value.debugLogPath.trim()
        : join(runtimeRoot, "data", "plugin-debug.log"),
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
    enableWatchdogRecoveryRunner: value.enableWatchdogRecoveryRunner !== false,
    watchdogRecoveryPollMs:
      typeof value.watchdogRecoveryPollMs === "number" && Number.isFinite(value.watchdogRecoveryPollMs)
        ? Math.max(1000, Math.trunc(value.watchdogRecoveryPollMs))
        : 30000,
  };
}

function withTaskPrefix(config: Required<TaskSystemPluginConfig>, message: string): string {
  const normalized = normalizeText(message);
  if (!normalized) {
    return normalized;
  }
  const prefix = typeof config.taskMessagePrefix === "string" ? config.taskMessagePrefix : "";
  if (!prefix) {
    return normalized;
  }
  return `${prefix}${normalized}`;
}

function buildHooksScriptPath(config: Required<TaskSystemPluginConfig>): string {
  return `${config.runtimeRoot}/scripts/runtime/openclaw_hooks.py`;
}

type QueueScope = "direct" | "conversation" | "thread";

type QueueIdentity = {
  channel: string;
  accountId: string;
  conversationId: string;
  threadId?: string;
  senderId?: string;
  sessionKey?: string;
  scope: QueueScope;
  queueKey: string;
};

type EarlyAckMarker = {
  version?: number;
  queueKey?: string;
  sentAt: number;
  channel?: string;
  accountId?: string;
  conversationId?: string;
  threadId?: string;
  messageId?: string;
};

function getEarlyAckState(): Map<string, Array<number | EarlyAckMarker>> {
  const scope = globalThis as typeof globalThis & {
    [EARLY_ACK_STATE_KEY]?: Map<string, Array<number | EarlyAckMarker>>;
  };
  if (!(scope[EARLY_ACK_STATE_KEY] instanceof Map)) {
    scope[EARLY_ACK_STATE_KEY] = new Map<string, Array<number | EarlyAckMarker>>();
  }
  return scope[EARLY_ACK_STATE_KEY] as Map<string, Array<number | EarlyAckMarker>>;
}

function buildEarlyAckKey(channel: string, accountId: string, chatId: string): string {
  return `${normalizeText(channel).toLowerCase()}:${normalizeText(accountId)}:${normalizeText(chatId)}`;
}

function buildQueueIdentity(params: {
  channel: string;
  accountId?: string;
  conversationId?: string;
  threadId?: string;
  senderId?: string;
  sessionKey?: string;
  isGroup?: boolean;
}): QueueIdentity {
  const channel = normalizeText(params.channel).toLowerCase() || "unknown";
  const accountId = normalizeText(params.accountId);
  const conversationId = normalizeText(params.conversationId) || normalizeText(params.sessionKey) || "unknown";
  const threadId = normalizeText(params.threadId) || undefined;
  const senderId = normalizeText(params.senderId) || undefined;
  const sessionKey = normalizeText(params.sessionKey) || undefined;
  const scope: QueueScope = threadId ? "thread" : params.isGroup ? "conversation" : "direct";
  return {
    channel,
    accountId,
    conversationId,
    ...(threadId ? { threadId } : {}),
    ...(senderId ? { senderId } : {}),
    ...(sessionKey ? { sessionKey } : {}),
    scope,
    queueKey: buildEarlyAckKey(channel, accountId, threadId ? `${conversationId}:thread:${threadId}` : conversationId),
  };
}

function buildCandidateQueueKeys(channel: string, accountId: string, ids: string[]): string[] {
  const seen = new Set<string>();
  const keys: string[] = [];
  for (const id of ids) {
    const normalized = normalizeText(id);
    if (!normalized) {
      continue;
    }
    const key = buildEarlyAckKey(channel, accountId, normalized);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    keys.push(key);
  }
  return keys;
}

function buildFallbackQueueKeys(identity: QueueIdentity, ids: string[]): string[] {
  const keys = [identity.queueKey];
  return keys.concat(buildCandidateQueueKeys(identity.channel, identity.accountId, ids)).filter((entry, index, all) => {
    return entry && all.indexOf(entry) === index;
  });
}

function normalizeEarlyAckMarker(entry: number | EarlyAckMarker): EarlyAckMarker | null {
  if (typeof entry === "number" && Number.isFinite(entry)) {
    return {
      sentAt: entry,
    };
  }
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const sentAt = Number((entry as EarlyAckMarker).sentAt);
  if (!Number.isFinite(sentAt)) {
    return null;
  }
  return {
    ...entry,
    sentAt,
    queueKey: normalizeText(entry.queueKey),
  };
}

function consumeQueuedEarlyAck(identity: QueueIdentity, ids: string[]): boolean {
  const keys = buildFallbackQueueKeys(identity, ids);
  const state = getEarlyAckState();
  const now = Date.now();
  for (const key of keys) {
    const existing = Array.isArray(state.get(key)) ? state.get(key)! : [];
    const fresh = existing
      .map((entry) => normalizeEarlyAckMarker(entry))
      .filter((entry): entry is EarlyAckMarker => Boolean(entry) && now - entry.sentAt <= EARLY_ACK_TTL_MS);
    if (fresh.length === 0) {
      state.delete(key);
      continue;
    }
    fresh.shift();
    if (fresh.length > 0) {
      state.set(key, fresh);
    } else {
      state.delete(key);
    }
    return true;
  }
  return false;
}

type RawPreRegisterEntry = {
  version?: number;
  preRegisterSnapshot?: PreRegisterSnapshot | null;
  queueIdentity?: Partial<QueueIdentity> | null;
  queueKey?: string;
  content?: string;
  contentFingerprint?: string;
  senderId?: string;
  arrivalTs?: number;
  snapshotTs?: number;
  timestamp?: number;
  registerDecision?: Record<string, unknown>;
  registerResult?: Record<string, unknown>;
  ack?: {
    earlyAckEligible?: boolean;
    earlyAckSent?: boolean;
    earlyAckSentAt?: number;
  };
  earlyAckSent?: boolean;
};

type PreRegisterSnapshot = {
  version?: number;
  queueIdentity?: Partial<QueueIdentity> | null;
  queueKey?: string;
  content: string;
  contentFingerprint?: string;
  senderId: string;
  arrivalTs?: number;
  snapshotTs?: number;
  registerDecision?: Record<string, unknown>;
  ack?: {
    earlyAckEligible?: boolean;
    earlyAckSent?: boolean;
    earlyAckSentAt?: number;
  };
};

type ConsumedPreRegisterResult = {
  snapshot: PreRegisterSnapshot;
  registerResult: Record<string, unknown>;
  earlyAckSent: boolean;
};

type NormalizedPreRegisterState = ConsumedPreRegisterResult & {
  timestamp: number;
};

function extractPreRegisterSnapshot(entry: RawPreRegisterEntry): PreRegisterSnapshot | null {
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const snapshot =
    entry.preRegisterSnapshot && typeof entry.preRegisterSnapshot === "object"
      ? entry.preRegisterSnapshot
      : entry;
  if (!snapshot || typeof snapshot !== "object") {
    return null;
  }
  return snapshot;
}

function extractPreRegisterDecision(entry: RawPreRegisterEntry): Record<string, unknown> {
  const snapshot = extractPreRegisterSnapshot(entry);
  const snapshotDecision =
    snapshot?.registerDecision && typeof snapshot.registerDecision === "object" ? snapshot.registerDecision : null;
  if (snapshotDecision) {
    return snapshotDecision;
  }
  if (entry.registerDecision && typeof entry.registerDecision === "object") {
    return entry.registerDecision;
  }
  return entry.registerResult && typeof entry.registerResult === "object" ? entry.registerResult : {};
}

function extractPreRegisterQueueIdentity(entry: RawPreRegisterEntry): Partial<QueueIdentity> | null {
  const snapshot = extractPreRegisterSnapshot(entry);
  if (snapshot?.queueIdentity && typeof snapshot.queueIdentity === "object") {
    return snapshot.queueIdentity;
  }
  if (entry.queueIdentity && typeof entry.queueIdentity === "object") {
    return entry.queueIdentity;
  }
  return null;
}

function extractRawPreRegisterQueueKey(entry: RawPreRegisterEntry): string {
  const snapshot = extractPreRegisterSnapshot(entry);
  return normalizeText(snapshot?.queueKey || entry.queueKey);
}

function extractPreRegisterEarlyAckSent(entry: RawPreRegisterEntry): boolean {
  const snapshot = extractPreRegisterSnapshot(entry);
  return Boolean(snapshot?.ack?.earlyAckSent ?? entry.ack?.earlyAckSent ?? entry.earlyAckSent ?? false);
}

function extractRawPreRegisterAck(entry: RawPreRegisterEntry): PreRegisterSnapshot["ack"] | undefined {
  const snapshot = extractPreRegisterSnapshot(entry);
  if (snapshot?.ack && typeof snapshot.ack === "object") {
    return snapshot.ack;
  }
  return entry.ack;
}

function getRawPreRegisterState(): Map<string, RawPreRegisterEntry[]> {
  const scope = globalThis as typeof globalThis & {
    [PRE_REGISTER_STATE_KEY]?: Map<string, RawPreRegisterEntry[]>;
  };
  if (!(scope[PRE_REGISTER_STATE_KEY] instanceof Map)) {
    scope[PRE_REGISTER_STATE_KEY] = new Map<string, RawPreRegisterEntry[]>();
  }
  return scope[PRE_REGISTER_STATE_KEY] as Map<string, RawPreRegisterEntry[]>;
}

function fingerprintContent(content: string): string {
  return normalizeText(content).toLowerCase();
}

function normalizeRawPreRegisterState(entry: RawPreRegisterEntry): NormalizedPreRegisterState | null {
  if (!entry || typeof entry !== "object") {
    return null;
  }
  const snapshot = extractPreRegisterSnapshot(entry);
  if (!snapshot) {
    return null;
  }
  const content = normalizeText(snapshot.content);
  const senderId = normalizeText(snapshot.senderId);
  const timestamp = Number.isFinite(snapshot.snapshotTs)
    ? Number(snapshot.snapshotTs)
    : Number.isFinite(snapshot.arrivalTs)
      ? Number(snapshot.arrivalTs)
      : Number(entry.timestamp);
  if (!content || !senderId || !Number.isFinite(timestamp)) {
    return null;
  }
  const registerDecision = extractPreRegisterDecision(entry);
  return {
    timestamp,
    snapshot: {
      ...snapshot,
      content,
      senderId,
      queueKey: extractRawPreRegisterQueueKey(entry),
      contentFingerprint: fingerprintContent(snapshot.contentFingerprint || content),
      ack: extractRawPreRegisterAck(entry),
      registerDecision: registerDecision ?? {},
    },
    registerResult: registerDecision ?? {},
    earlyAckSent: extractPreRegisterEarlyAckSent(entry),
  };
}

function listFreshConsumedPreRegisters(entries: RawPreRegisterEntry[], now: number): NormalizedPreRegisterState[] {
  return entries
    .map((entry) => {
      const normalized = normalizeRawPreRegisterState(entry);
      if (!normalized || now - normalized.timestamp > EARLY_ACK_TTL_MS) {
        return null;
      }
      return normalized;
    })
    .filter((entry): entry is NormalizedPreRegisterState => Boolean(entry));
}

function toRawPreRegisterEntry(entry: NormalizedPreRegisterState | ConsumedPreRegisterResult, now: number): RawPreRegisterEntry {
  const timestamp =
    "timestamp" in entry && Number.isFinite(entry.timestamp)
      ? Number(entry.timestamp)
      : Number(entry.snapshot.snapshotTs ?? entry.snapshot.arrivalTs ?? now);
  return {
    version: entry.snapshot.version,
    preRegisterSnapshot: entry.snapshot,
    timestamp,
    registerDecision: entry.registerResult,
    registerResult: entry.registerResult,
    earlyAckSent: entry.earlyAckSent,
  };
}

function consumePreRegisteredSnapshot(
  identity: QueueIdentity,
  ids: string[],
  contents: string[],
  senderId: string,
): ConsumedPreRegisterResult | null {
  const state = getRawPreRegisterState();
  const now = Date.now();
  const normalizedSenderId = normalizeText(senderId);
  const keys = buildFallbackQueueKeys(identity, ids);
  const normalizedContents = contents
    .map((entry) => fingerprintContent(entry))
    .filter((entry, index, all) => entry && all.indexOf(entry) === index);

  for (const key of keys) {
    const existing = Array.isArray(state.get(key)) ? state.get(key)! : [];
    const fresh = listFreshConsumedPreRegisters(existing, now);
    let queueKeyMatchIndex = -1;
    let fallbackMatchIndex = -1;
    for (let index = 0; index < fresh.length; index += 1) {
      const candidate = fresh[index];
      const entryQueueKey = normalizeText(candidate.snapshot.queueKey);
      const entryFingerprint = fingerprintContent(candidate.snapshot.contentFingerprint || candidate.snapshot.content);
      if (entryQueueKey && entryQueueKey === identity.queueKey && normalizedContents.includes(entryFingerprint)) {
        queueKeyMatchIndex = index;
        break;
      }
      if (
        fallbackMatchIndex < 0 &&
        normalizedContents.includes(entryFingerprint) &&
        normalizeText(candidate.snapshot.senderId) === normalizedSenderId
      ) {
        fallbackMatchIndex = index;
      }
    }
    const matchIndex = queueKeyMatchIndex >= 0 ? queueKeyMatchIndex : fallbackMatchIndex;
    if (matchIndex < 0) {
      if (fresh.length > 0) {
        state.set(key, fresh.map((entry) => toRawPreRegisterEntry(entry, now)));
      } else {
        state.delete(key);
      }
      continue;
    }
    const [match] = fresh.splice(matchIndex, 1);
    if (fresh.length > 0) {
      state.set(key, fresh.map((entry) => toRawPreRegisterEntry(entry, now)));
    } else {
      state.delete(key);
    }
    return match ?? null;
  }
  return null;
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

function enqueueDebugLog(
  config: Required<TaskSystemPluginConfig>,
  event: string,
  payload: Record<string, unknown>,
): void {
  void appendDebugLog(config, event, payload);
}

type TextCapableAdapter = {
  sendText?: (args: {
    cfg: unknown;
    to: string;
    text: string;
    accountId?: string;
  }) => Promise<unknown>;
};

const outboundAdapterCache = new WeakMap<OpenClawPluginApi, Map<string, Promise<TextCapableAdapter | null>>>();

async function loadOutboundAdapter(
  api: OpenClawPluginApi,
  channel: string,
): Promise<TextCapableAdapter | null> {
  const normalizedChannel = normalizeText(channel).toLowerCase();
  if (!normalizedChannel) {
    return null;
  }
  let cache = outboundAdapterCache.get(api);
  if (!cache) {
    cache = new Map<string, Promise<TextCapableAdapter | null>>();
    outboundAdapterCache.set(api, cache);
  }
  const cached = cache.get(normalizedChannel);
  if (cached) {
    return cached;
  }
  const pending = api.runtime.channel.outbound
    .loadAdapter(normalizedChannel)
    .then((adapter) => (adapter as TextCapableAdapter | null) ?? null)
    .catch(() => {
      cache?.delete(normalizedChannel);
      return null;
    });
  cache.set(normalizedChannel, pending);
  return pending;
}

async function warmOutboundAdapters(
  api: OpenClawPluginApi,
  channels: string[],
): Promise<void> {
  await Promise.allSettled(
    channels.map(async (channel) => {
      const normalized = normalizeText(channel).toLowerCase();
      if (!normalized) {
        return;
      }
      await loadOutboundAdapter(api, normalized);
    }),
  );
}

async function callHook(
  api: OpenClawPluginApi,
  config: Required<TaskSystemPluginConfig>,
  command: string,
  payload: Record<string, unknown>,
): Promise<Record<string, unknown> | null> {
  const script = buildHooksScriptPath(config);
  try {
    enqueueDebugLog(config, `hook:${command}:start`, payload);
    const args = [script, command, "-"];
    if (config.configPath) {
      args.push(config.configPath);
    }
    const result = await new Promise<{ stdout: string; stderr: string }>((resolve, reject) => {
      const child = spawn(config.pythonBin, args, {
        cwd: config.runtimeRoot,
        env: process.env,
        stdio: ["pipe", "pipe", "pipe"],
      });
      let stdout = "";
      let stderr = "";
      child.stdout.on("data", (chunk) => {
        stdout += String(chunk);
      });
      child.stderr.on("data", (chunk) => {
        stderr += String(chunk);
      });
      child.on("error", reject);
      child.on("close", (code) => {
        if (code === 0) {
          resolve({ stdout, stderr });
          return;
        }
        reject(new Error(stderr.trim() || `hook exited with code ${code}`));
      });
      child.stdin.write(JSON.stringify(payload));
      child.stdin.end();
    });
    const parsed = JSON.parse(result.stdout || "{}") as Record<string, unknown>;
    enqueueDebugLog(config, `hook:${command}:ok`, parsed);
    return parsed;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    enqueueDebugLog(config, `hook:${command}:error`, {
      message,
      command,
      schedulerDecision: "error",
      reason: "hook-call-failed",
      logLevel: "warn",
      operatorVisible: true,
      errorCategory: "hook-call-failure",
    });
    api.logger.warn(`[task-system] hook ${command} failed: ${message}`);
    return null;
  }
}

async function callGatewayCli(
  api: OpenClawPluginApi,
  config: Required<TaskSystemPluginConfig>,
  method: string,
  params: Record<string, unknown>,
  timeoutMs = 10000,
): Promise<Record<string, unknown> | null> {
  try {
    enqueueDebugLog(config, `gateway:${method}:start`, params);
    const args = [
      "gateway",
      "call",
      method,
      "--json",
      "--params",
      JSON.stringify(params),
      "--timeout",
      String(timeoutMs),
    ];
    const result = await new Promise<{ stdout: string; stderr: string }>((resolve, reject) => {
      const child = spawn(config.openclawBin, args, {
        cwd: config.runtimeRoot,
        env: process.env,
        stdio: ["ignore", "pipe", "pipe"],
      });
      let stdout = "";
      let stderr = "";
      child.stdout.on("data", (chunk) => {
        stdout += String(chunk);
      });
      child.stderr.on("data", (chunk) => {
        stderr += String(chunk);
      });
      child.on("error", reject);
      child.on("close", (code) => {
        if (code === 0) {
          resolve({ stdout, stderr });
          return;
        }
        reject(new Error(stderr.trim() || `gateway call exited with code ${code}`));
      });
    });
    const parsed = JSON.parse(result.stdout || "{}") as Record<string, unknown>;
    enqueueDebugLog(config, `gateway:${method}:ok`, parsed);
    return parsed;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    enqueueDebugLog(config, `gateway:${method}:error`, {
      message,
      method,
      schedulerDecision: "error",
      reason: "gateway-call-failed",
      logLevel: "warn",
      operatorVisible: true,
      errorCategory: "gateway-call-failure",
    });
    api.logger.warn(`[task-system] gateway ${method} failed: ${message}`);
    return null;
  }
}

function buildSessionKey(channelId: string, conversationId?: string): string {
  const suffix = conversationId?.trim() ? conversationId.trim() : "unknown";
  return `${channelId}:${suffix}`;
}

function normalizeSessionKey(sessionKey: string): string {
  return normalizeText(sessionKey);
}

function inferAgentIdFromSessionKey(sessionKey: string): string | null {
  const normalized = normalizeText(sessionKey);
  if (!normalized) {
    return null;
  }
  const match = /^agent:([^:]+):/i.exec(normalized);
  if (!match?.[1]) {
    return null;
  }
  return normalizeText(match[1]) || null;
}

function resolveAgentId(
  configuredAgentId: string | undefined,
  sessionKey: string,
  defaultAgentId: string,
): string {
  const explicitAgentId = normalizeText(configuredAgentId);
  if (explicitAgentId) {
    return explicitAgentId;
  }
  const inferredAgentId = inferAgentIdFromSessionKey(sessionKey);
  if (inferredAgentId) {
    return inferredAgentId;
  }
  return defaultAgentId;
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

function formatEstimatedWaitLabel(estimatedWaitSeconds: number | null): string | null {
  if (!Number.isFinite(estimatedWaitSeconds ?? NaN) || estimatedWaitSeconds === null) {
    return null;
  }
  const seconds = Math.max(1, Math.trunc(estimatedWaitSeconds));
  if (seconds < 60) {
    return `预计约 ${seconds} 秒后`;
  }
  const minutes = Math.max(1, Math.ceil(seconds / 60));
  return `预计约 ${minutes} 分钟后`;
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

function canSendDirectStatusMessage(channel: string, chatId: string): boolean {
  const normalizedChannel = normalizeText(channel).toLowerCase();
  const normalizedChatId = normalizeDirectStatusRecipient(channel, chatId);
  if (!normalizedChannel || !normalizedChatId) {
    return false;
  }
  if (normalizedChannel !== "telegram") {
    return true;
  }
  return /^-?\d+$/.test(normalizedChatId);
}

function normalizeDirectStatusRecipient(channel: string, chatId: string): string {
  const normalizedChannel = normalizeText(channel).toLowerCase();
  const normalizedChatId = normalizeText(chatId);
  if (!normalizedChatId) {
    return "";
  }
  if (normalizedChannel !== "telegram") {
    return normalizedChatId;
  }
  const slashMatch = /^slash:(-?\d+)$/i.exec(normalizedChatId);
  if (slashMatch?.[1]) {
    return slashMatch[1];
  }
  return normalizedChatId;
}

function isInternalRetryPrompt(prompt: string): boolean {
  const normalized = normalizeText(prompt).toLowerCase();
  return normalized === "continue where you left off. the previous model attempt failed or timed out.";
}

function isInternalStartupResumePrompt(prompt: string): boolean {
  return normalizeText(prompt).startsWith(INTERNAL_STARTUP_RESUME_MARKER);
}

function isContinuationWakePrompt(prompt: string): boolean {
  const normalized = normalizeText(prompt);
  if (!normalized) {
    return false;
  }
  return (
    normalized.includes("这是一个已经到达计划时间的延迟任务，请你现在继续执行") &&
    normalized.includes("你现在必须直接回复以下最终内容")
  );
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
  const audienceKey = buildControlPlaneAudienceKey("feishu", accountId, chatId);
  const enqueueToken = Date.now();
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
    await appendDebugLog(config, "host-feishu-delivery:skipped-invalid-payload", {
      taskId: payload.task_id || null,
      accountId,
      chatId,
      audienceKey,
      enqueueToken,
      runner: "host-feishu-delivery",
      lifecycleStage: "delivery-skipped",
      deliveryPath: "plugin-host",
      schedulerDecision: "skipped",
      reason: !accountId ? "missing-account-id" : !chatId ? "missing-chat-id" : "empty-message",
      instructionName: name,
    });
    return;
  }

  const adapter = await loadOutboundAdapter(api, "feishu");
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
    await appendDebugLog(config, "host-feishu-delivery:adapter-unavailable", {
      taskId: payload.task_id || null,
      accountId,
      chatId,
      audienceKey,
      enqueueToken,
      runner: "host-feishu-delivery",
      lifecycleStage: "delivery-adapter-unavailable",
      deliveryPath: "plugin-host",
      schedulerDecision: "adapter-unavailable",
      reason: "host-feishu-adapter-unavailable",
      instructionName: name,
    });
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
      audienceKey,
      enqueueToken,
      runner: "host-feishu-delivery",
      lifecycleStage: "delivery-sent",
      deliveryPath: "plugin-host",
      schedulerDecision: "sent",
      reason: "host-feishu-send-succeeded",
      instructionName: name,
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
      accountId,
      chatId,
      audienceKey,
      enqueueToken,
      runner: "host-feishu-delivery",
      lifecycleStage: "delivery-error",
      deliveryPath: "plugin-host",
      schedulerDecision: "error",
      reason: "host-feishu-send-failed",
      instructionName: name,
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
    const accountId = normalizeText(String(payload.account_id || ""));
    const replyText = normalizeText(String(payload.reply_text || ""));
    const originalUserRequest = normalizeText(
      String(
        (payload.continuation_payload &&
          typeof payload.continuation_payload === "object" &&
          (payload.continuation_payload as Record<string, unknown>).original_user_request) ||
          "",
      ),
    );
    if (!channel || !chatId || !taskId || !replyText) {
      continue;
    }
    const audienceKey = buildControlPlaneAudienceKey(channel, accountId, chatId);
    const enqueueToken = Date.now();
    try {
      const wakeStart = await callHook(api, config, "continuation-wake", {
        task_id: taskId,
        state: "attempting",
        message: "已到达计划时间，准备直接发送延迟回复",
      });
      await appendDebugLog(config, "continuation-wake:start", {
        taskId,
        sessionKey,
        attemptCount: wakeStart?.attempt_count ?? null,
        channel,
        chatId,
        accountId,
        audienceKey,
        enqueueToken,
        runner: "continuation-delivery",
        lifecycleStage: "wake-start",
        deliveryPath: "direct-channel-send",
        schedulerDecision: "wake-start",
        reason: "continuation-wake-started",
        originalUserRequest: originalUserRequest || null,
      });
      const adapter = await loadOutboundAdapter(api, channel);
      if (!adapter?.sendText) {
        await appendDebugLog(config, "continuation-delivery:adapter-unavailable", {
          taskId,
          sessionKey,
          channel,
          chatId,
          accountId,
          audienceKey,
          enqueueToken,
          runner: "continuation-delivery",
          lifecycleStage: "delivery-adapter-unavailable",
          deliveryPath: "direct-channel-send",
          schedulerDecision: "adapter-unavailable",
          reason: "continuation-delivery-adapter-unavailable",
        });
        await callHook(api, config, "continuation-wake", {
          task_id: taskId,
          state: "failed",
          message: `延迟回复发送失败：channel ${channel} adapter 不可用`.slice(0, 240),
        });
        await callHook(api, config, "blocked", {
          task_id: taskId,
          reason: `continuation delivery adapter unavailable: ${channel}`.slice(0, 240),
        });
        continue;
      }
      await adapter.sendText({
        cfg: api.config,
        to: chatId,
        text: replyText,
        accountId,
      });
      await appendDebugLog(config, "continuation-delivery:sent", {
        taskId,
        sessionKey,
        channel,
        chatId,
        message: replyText,
        accountId,
        audienceKey,
        enqueueToken,
        runner: "continuation-delivery",
        lifecycleStage: "delivery-sent",
        deliveryPath: "direct-channel-send",
        schedulerDecision: "sent",
        reason: "continuation-delivery-sent",
      });
      await callHook(api, config, "continuation-wake", {
        task_id: taskId,
        state: "dispatched",
        message: "已直接发送到点回复",
      });
      await callHook(api, config, "completed", {
        task_id: taskId,
        result_summary: `continuation reply delivered: ${replyText}`.slice(0, 240),
      });
      await appendDebugLog(config, "continuation-wake:ok", {
        taskId,
        sessionKey,
        channel,
        chatId,
        accountId,
        audienceKey,
        enqueueToken,
        runner: "continuation-delivery",
        lifecycleStage: "wake-complete",
        deliveryPath: "direct-channel-send",
        schedulerDecision: "wake-ok",
        reason: "continuation-wake-complete",
        deliveredReplyText: replyText,
      });
    } catch (error) {
      const messageText = error instanceof Error ? error.message : String(error);
      await callHook(api, config, "continuation-wake", {
        task_id: taskId,
        state: "failed",
        message: `唤醒 agent 失败：${messageText}`.slice(0, 240),
      });
      await callHook(api, config, "blocked", {
        task_id: taskId,
        reason: `continuation wake failed: ${messageText}`.slice(0, 240),
      });
      await appendDebugLog(config, "continuation-wake:error", {
        taskId,
        sessionKey,
        channel,
        chatId,
        accountId,
        audienceKey,
        enqueueToken,
        runner: "continuation-delivery",
        lifecycleStage: "wake-error",
        deliveryPath: "direct-channel-send",
        schedulerDecision: "error",
        reason: "continuation-wake-failed",
        error: messageText,
      });
    }
  }
}

async function processWatchdogRecovery(
  api: OpenClawPluginApi,
  config: Required<TaskSystemPluginConfig>,
  options: { startupRecovery?: boolean } = {},
): Promise<void> {
  const { startupRecovery = false } = options;
  if (!config.enableWatchdogRecoveryRunner) {
    return;
  }
  const result = await callHook(api, config, "watchdog-auto-recover", { startup_recovery: startupRecovery });
  if (!startupRecovery || !result) {
    return;
  }
  const promoted = Array.isArray(result.startup_promoted) ? result.startup_promoted : [];
  for (const item of promoted) {
    const sessionKey = normalizeText((item as Record<string, unknown>).session_key);
    if (!sessionKey) {
      continue;
    }
    const channel = normalizeText((item as Record<string, unknown>).channel).toLowerCase();
    const accountId = normalizeText((item as Record<string, unknown>).account_id);
    const chatId = normalizeText((item as Record<string, unknown>).chat_id);
    const taskLabel = normalizeText((item as Record<string, unknown>).task_label);
    const resumeMessage = [
      INTERNAL_STARTUP_RESUME_MARKER,
      "系统恢复：OpenClaw 重启后检测到当前会话里有未完成的主任务需要继续推进。",
      taskLabel ? `任务目标：${taskLabel}` : "",
      "请基于当前会话上下文和现有 workspace 继续执行，并在完成后把最终结果回复到当前频道。",
    ]
      .filter(Boolean)
      .join("\n");
    const useExplicitDelivery = !!channel && !!chatId;
    const method = useExplicitDelivery ? "chat.send" : "sessions.steer";
    const audienceKey = useExplicitDelivery
      ? buildControlPlaneAudienceKey(channel, accountId, chatId)
      : `session:${sessionKey}`;
    const params = useExplicitDelivery
      ? {
          sessionKey,
          message: resumeMessage,
          timeoutMs: 10000,
          idempotencyKey: `startup-resume:${randomUUID()}`,
          deliver: true,
          originatingChannel: channel,
          originatingTo: chatId,
          ...(accountId ? { originatingAccountId: accountId } : {}),
        }
      : {
          key: sessionKey,
          message: resumeMessage,
          timeoutMs: 10000,
        };
    await appendDebugLog(config, "watchdog-auto-recover:startup-dispatch", {
      sessionKey,
      taskLabel,
      method,
      channel,
      chatId,
      accountId,
      audienceKey,
      startupRecovery: true,
      schedulerDecision: "sent",
      reason: "startup-watchdog-recovery-dispatch",
    });
    await callGatewayCli(api, config, method, params);
  }
}

type PendingReceipt = {
  taskId: string;
  sessionKey: string;
  channel: string;
  accountId?: string;
  chatId: string;
  taskKind: "short" | "long";
  timer: ReturnType<typeof setTimeout> | null;
};

type ActiveTaskBinding = {
  taskId: string;
};

type ControlPlanePriority = "p0-receive-ack" | "p1-task-management" | "p2-progress-followup" | "p3-advisory";

type ControlPlaneMessage = {
  eventName: string;
  priority: ControlPlanePriority;
  channel: string;
  accountId?: string;
  chatId: string;
  sessionKey: string;
  message: string;
  taskId?: string;
};

type ControlPlaneTerminalState = {
  eventName: string;
  ts: number;
  enqueueToken: number;
  priority: ControlPlanePriority;
  taskId: string | null;
  terminalPhase: "committed";
};

type ControlPlanePendingTerminalState = {
  eventName: string;
  enqueueToken: number;
  priority: ControlPlanePriority;
  taskId: string | null;
  terminalPhase: "pending";
};

type ControlPlaneBlockerMeta = {
  enqueueToken: number;
  eventName: string;
  priority: ControlPlanePriority;
  taskId: string | null;
};

function isSupersedableControlPlanePriority(priority: ControlPlanePriority): boolean {
  return priority === "p2-progress-followup" || priority === "p3-advisory";
}

function normalizeControlPlanePriority(value: unknown): ControlPlanePriority {
  const normalized = normalizeText(value).toLowerCase();
  if (
    normalized === "p0-receive-ack" ||
    normalized === "p1-task-management" ||
    normalized === "p2-progress-followup" ||
    normalized === "p3-advisory"
  ) {
    return normalized;
  }
  return "p3-advisory";
}

function extractHookControlPlaneMessage(payload: Record<string, unknown> | null | undefined): Partial<ControlPlaneMessage> | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const raw = payload.control_plane_message;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return null;
  }
  const record = raw as Record<string, unknown>;
  const message = normalizeText(record.text);
  if (!message) {
    return null;
  }
  return {
    eventName: normalizeText(record.event_name) || "short-task-followup",
    priority: normalizeControlPlanePriority(record.priority),
    taskId: normalizeText(record.task_id) || undefined,
    message,
  };
}

function buildHookBackedControlPlaneMessage(
  hookPayload: Record<string, unknown> | null | undefined,
  fallback: Omit<ControlPlaneMessage, "eventName" | "priority" | "taskId" | "message"> & {
    eventName: string;
    priority: ControlPlanePriority;
    message: string;
    taskId?: string;
  },
): ControlPlaneMessage {
  const extracted = extractHookControlPlaneMessage(hookPayload);
  return {
    ...fallback,
    eventName: extracted?.eventName || fallback.eventName,
    priority: extracted?.priority || fallback.priority,
    taskId: extracted?.taskId || fallback.taskId,
    message: extracted?.message || fallback.message,
  };
}

function isTerminalControlPlanePriority(priority: ControlPlanePriority): boolean {
  return priority === "p1-task-management";
}

function shouldDropForTerminalControlPlaneState(
  priority: ControlPlanePriority,
  terminalState: ControlPlaneTerminalState | undefined,
): boolean {
  if (!terminalState) {
    return false;
  }
  return !isTerminalControlPlanePriority(priority);
}

function buildControlPlaneAudienceKey(channel: string, accountId: string | undefined, chatId: string): string {
  return `${normalizeText(channel).toLowerCase()}:${normalizeText(accountId)}:${normalizeText(chatId)}`;
}

function isPreemptingControlPlanePriority(priority: ControlPlanePriority): boolean {
  return priority === "p0-receive-ack" || priority === "p1-task-management";
}

type TaskMonitorCommand = {
  action: "on" | "off" | "status";
};

type ContinuitySummaryCommand = {
  compact: boolean;
};

type TasksSummaryCommand = {
  scope: "session";
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

function parseTaskMonitorCommand(content: string): TaskMonitorCommand | null {
  const normalized = normalizeText(content).toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized === "/taskmonitor" || normalized === "taskmonitor" || normalized === "/taskmonitor status") {
    return { action: "status" };
  }
  if (normalized === "/taskmonitor on" || normalized === "taskmonitor on") {
    return { action: "on" };
  }
  if (normalized === "/taskmonitor off" || normalized === "taskmonitor off") {
    return { action: "off" };
  }
  return null;
}

function parseContinuitySummaryCommand(content: string): ContinuitySummaryCommand | null {
  const normalized = normalizeText(content).toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized === "/status" || normalized === "status") {
    return { compact: false };
  }
  if (normalized === "/compact" || normalized === "compact") {
    return { compact: true };
  }
  return null;
}

function parseTasksSummaryCommand(content: string): TasksSummaryCommand | null {
  const normalized = normalizeText(content).toLowerCase();
  if (!normalized) {
    return null;
  }
  if (normalized === "/tasks" || normalized === "tasks") {
    return { scope: "session" };
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
  const resolvedDecision = resolveRegisterDecision(registerResult);
  const taskStatus = normalizeText(resolvedDecision.task_status);
  const queuePosition = toInteger(resolvedDecision.queue_position);
  const aheadCount = Math.max(toInteger(resolvedDecision.ahead_count) ?? 0, 0);
  const runningCount = Math.max(toInteger(resolvedDecision.running_count) ?? 0, 0);
  const activeCount = Math.max(toInteger(resolvedDecision.active_count) ?? 0, 0);
  const estimatedWaitSeconds = toInteger(resolvedDecision.estimated_wait_seconds);
  const continuationDueAt = normalizeText(String(resolvedDecision.continuation_due_at || ""));
  const estimatedWaitLabel = formatEstimatedWaitLabel(estimatedWaitSeconds);

  if (taskStatus === "paused" && continuationDueAt) {
    const delayLabel = formatContinuationDelayLabel(continuationDueAt);
    if (delayLabel) {
      return `已收到，已安排后续继续执行；${delayLabel}，到点后我会主动回复。`;
    }
    return "已收到，已安排后续继续执行；到点后我会主动回复。";
  }

  if (taskStatus === "queued" || taskStatus === "received") {
    const position = queuePosition ?? aheadCount + 1;
    if (runningCount <= 0 && aheadCount > 0) {
      if (estimatedWaitLabel) {
        return `已收到，你的请求已进入队列；前面还有 ${aheadCount} 个号，你现在排第 ${position} 位，${estimatedWaitLabel}轮到处理。`;
      }
      return `已收到，你的请求已进入队列；前面还有 ${aheadCount} 个号，你现在排第 ${position} 位。`;
    }
    if (runningCount <= 0) {
      if (estimatedWaitLabel) {
        return `已收到，你的请求已进入队列；你现在排第 ${position} 位，${estimatedWaitLabel}轮到处理。`;
      }
      return `已收到，你的请求已进入队列；你现在排第 ${position} 位。`;
    }
    if (estimatedWaitLabel) {
      return `已收到，当前有 ${runningCount} 条任务正在处理；你的请求已进入队列，前面还有 ${aheadCount} 个号，你现在排第 ${position} 位，${estimatedWaitLabel}轮到处理。`;
    }
    return `已收到，当前有 ${runningCount} 条任务正在处理；你的请求已进入队列，前面还有 ${aheadCount} 个号，你现在排第 ${position} 位。`;
  }
  if (taskStatus === "running" && activeCount > 1) {
    if (estimatedWaitLabel) {
      return `已收到，现在轮到你的请求开始处理了；当前队列里共有 ${activeCount} 条活动任务，${estimatedWaitLabel}内预计会有初步结果，我会继续同步真实进展。`;
    }
    return `已收到，现在轮到你的请求开始处理了；当前队列里共有 ${activeCount} 条活动任务，我会继续同步真实进展。`;
  }
  if (taskStatus === "running") {
    return "已收到，正在开始处理；如果 30 秒内还没有新的阶段结果，我会先同步当前进展。";
  }
  return fallback;
}

function resolveRegisterDecision(registerResult: Record<string, unknown> | null | undefined): Record<string, unknown> {
  if (!registerResult || typeof registerResult !== "object") {
    return {};
  }
  const nested = registerResult.register_decision;
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    return nested as Record<string, unknown>;
  }
  return registerResult;
}

async function deliverControlPlaneMessage(
  api: OpenClawPluginApi,
  config: Required<TaskSystemPluginConfig>,
  payload: ControlPlaneMessage,
  schedulerContext?: {
    audienceKey?: string | null;
    enqueueToken?: number | null;
    audienceSequence?: number | null;
  },
): Promise<void> {
  const channel = String(payload.channel || "").trim().toLowerCase();
  if (!channel || channel === "agent") {
    return;
  }
  const chatId = normalizeDirectStatusRecipient(channel, String(payload.chatId || ""));
  const message = withTaskPrefix(config, payload.message);
  if (!chatId || !message) {
    return;
  }
  if (!canSendDirectStatusMessage(channel, chatId)) {
    await appendDebugLog(config, `${payload.eventName}:skipped`, {
      channel,
      chatId,
      taskId: payload.taskId ?? null,
      sessionKey: payload.sessionKey,
      schedulerDecision: "skipped",
      reason: "unsupported-direct-recipient",
      audienceKey: schedulerContext?.audienceKey ?? null,
      enqueueToken: schedulerContext?.enqueueToken ?? null,
      audienceSequence: schedulerContext?.audienceSequence ?? null,
    });
    return;
  }
  try {
    const loadStartedAt = Date.now();
    const adapter = await loadOutboundAdapter(api, channel);
    const adapterLoadMs = Date.now() - loadStartedAt;
    if (!adapter?.sendText) {
      await appendDebugLog(config, `${payload.eventName}:adapter-unavailable`, {
        channel,
        chatId,
        taskId: payload.taskId ?? null,
        sessionKey: payload.sessionKey,
        schedulerDecision: "adapter-unavailable",
        adapterLoadMs,
        audienceKey: schedulerContext?.audienceKey ?? null,
        enqueueToken: schedulerContext?.enqueueToken ?? null,
        audienceSequence: schedulerContext?.audienceSequence ?? null,
      });
      return;
    }
    const sendStartedAt = Date.now();
    await adapter.sendText({
      cfg: api.config,
      to: chatId,
      text: message,
      accountId: payload.accountId || "",
    });
    const sendMs = Date.now() - sendStartedAt;
    await appendDebugLog(config, `${payload.eventName}:sent`, {
      channel,
      chatId,
      taskId: payload.taskId ?? null,
      sessionKey: payload.sessionKey,
      schedulerDecision: "sent",
      message,
      adapterLoadMs,
      sendMs,
      priority: payload.priority,
      audienceKey: schedulerContext?.audienceKey ?? buildControlPlaneAudienceKey(channel, payload.accountId, chatId),
      enqueueToken: schedulerContext?.enqueueToken ?? null,
      audienceSequence: schedulerContext?.audienceSequence ?? null,
    });
  } catch (error) {
    const messageText = error instanceof Error ? error.message : String(error);
    await appendDebugLog(config, `${payload.eventName}:error`, {
      channel,
      chatId,
      taskId: payload.taskId ?? null,
      sessionKey: payload.sessionKey,
      schedulerDecision: "error",
      reason: "control-plane-send-failed",
      error: messageText,
      priority: payload.priority,
      logLevel: "warn",
      operatorVisible: true,
      errorCategory: "control-plane-delivery-failure",
      audienceKey: schedulerContext?.audienceKey ?? null,
      enqueueToken: schedulerContext?.enqueueToken ?? null,
      audienceSequence: schedulerContext?.audienceSequence ?? null,
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

function hasVisibleAssistantOutput(event: { messages: unknown[] }): boolean {
  const assistantMessages = event.messages.filter((entry) => {
    if (!entry || typeof entry !== "object") {
      return false;
    }
    const role = (entry as Record<string, unknown>).role;
    return typeof role === "string" && role.toLowerCase() === "assistant";
  });
  for (const message of assistantMessages) {
    if (extractTextFromUnknown(message).some((entry) => entry.length > 0)) {
      return true;
    }
  }
  return false;
}

const taskSystemPlugin = {
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
    let watchdogRecoveryTimer: ReturnType<typeof setInterval> | null = null;
    let startupWatchdogRecoveryRetryTimer: ReturnType<typeof setTimeout> | null = null;
    const pendingReceipts = new Map<string, PendingReceipt>();
    const activeTaskBindings = new Map<string, ActiveTaskBinding>();
    const taskMonitorEnabledBySession = new Map<string, boolean>();
    const recentActivationBySession = new Map<string, { signature: string; ts: number }>();
    const controlPlaneSequenceByAudience = new Map<string, number>();
    const controlPlaneLaneByAudience = new Map<string, Promise<void>>();
    const controlPlaneLatestPreemptingTokenByAudience = new Map<string, number>();
    const controlPlaneLatestPreemptingMetaByAudience = new Map<string, ControlPlaneBlockerMeta>();
    const controlPlaneLatestSupersedableTokenByAudience = new Map<string, number>();
    const controlPlaneLatestSupersedableMetaByAudience = new Map<string, ControlPlaneBlockerMeta>();
    const controlPlaneTerminalByTask = new Map<string, ControlPlaneTerminalState>();
    const controlPlanePendingTerminalByTask = new Map<string, ControlPlanePendingTerminalState>();
    const controlPlaneLatestSupersedableTokenByTask = new Map<string, number>();
    const controlPlaneLatestSupersedableMetaByTask = new Map<string, ControlPlaneBlockerMeta>();
    let controlPlaneEnqueueToken = 0;
    if (!config.enabled) {
      enqueueDebugLog(config, "plugin:load:disabled", {
        enabled: false,
        runtimeRoot: config.runtimeRoot,
        schedulerDecision: "skipped",
        reason: "plugin-disabled-by-config",
        logLevel: "info",
        operatorVisible: true,
      });
      api.logger.info("[task-system] plugin loaded in disabled mode");
      return;
    }

    async function appendControlPlaneDropLog(
      payload: ControlPlaneMessage,
      options: {
        reason: string;
        dropCategory: "terminal" | "preempted" | "superseded";
        blockerScope: string;
        audienceKey?: string;
        enqueueToken?: number;
        blockingTaskId?: string | null;
        blockedBy?: string | null;
        blockedByEnqueueToken?: number | null;
        blockedByPriority?: ControlPlanePriority | null;
        blockedByTerminalPhase?: "pending" | "committed" | null;
        terminalPhase?: "pending" | "committed";
        latestPreemptingTokenByAudience?: number | null;
        latestSupersedableTokenByAudience?: number | null;
        latestSupersedableTokenByTask?: number | null;
        pendingTerminalEventByTask?: string | null;
      },
    ): Promise<void> {
      await appendDebugLog(config, `${payload.eventName}:dropped`, {
        channel: payload.channel,
        chatId: payload.chatId,
        taskId: normalizeText(payload.taskId) || null,
        sessionKey: payload.sessionKey,
        schedulerDecision: "dropped",
        reason: options.reason,
        dropCategory: options.dropCategory,
        blockerScope: options.blockerScope,
        blockingTaskId: normalizeText(options.blockingTaskId) || null,
        blockedBy: options.blockedBy ?? null,
        blockedByEnqueueToken: options.blockedByEnqueueToken ?? null,
        blockedByPriority: options.blockedByPriority ?? null,
        blockedByTerminalPhase: options.blockedByTerminalPhase ?? null,
        terminalPhase: options.terminalPhase ?? null,
        priority: payload.priority,
        audienceKey: options.audienceKey ?? null,
        enqueueToken: options.enqueueToken ?? null,
        latestPreemptingTokenByAudience: options.latestPreemptingTokenByAudience ?? null,
        latestSupersedableTokenByAudience: options.latestSupersedableTokenByAudience ?? null,
        latestSupersedableTokenByTask: options.latestSupersedableTokenByTask ?? null,
        pendingTerminalEventByTask: options.pendingTerminalEventByTask ?? null,
      });
    }

    async function appendControlPlaneLaneLog(
      payload: ControlPlaneMessage,
      eventSuffix: "preempted-pending-followup" | "lane-enqueued" | "lane-pass",
      options: {
        schedulerDecision: "preempted-pending-followup" | "enqueued" | "passed";
        audienceKey?: string;
        enqueueToken?: number;
        audienceSequence?: number;
        latestPreemptingTokenByAudience?: number | null;
        latestSupersedableTokenByAudience?: number | null;
        latestSupersedableTokenByTask?: number | null;
        pendingTerminalEventByTask?: string | null;
        blockingTaskId?: string | null;
        blockedBy?: string | null;
        blockedByEnqueueToken?: number | null;
        blockedByPriority?: ControlPlanePriority | null;
        reason?: string | null;
      },
    ): Promise<void> {
      await appendDebugLog(config, `${payload.eventName}:${eventSuffix}`, {
        channel: payload.channel,
        chatId: payload.chatId,
        taskId: normalizeText(payload.taskId) || null,
        sessionKey: payload.sessionKey,
        priority: payload.priority,
        schedulerDecision: options.schedulerDecision,
        audienceKey: options.audienceKey ?? null,
        enqueueToken: options.enqueueToken ?? null,
        audienceSequence: options.audienceSequence ?? null,
        latestPreemptingTokenByAudience: options.latestPreemptingTokenByAudience ?? null,
        latestSupersedableTokenByAudience: options.latestSupersedableTokenByAudience ?? null,
        latestSupersedableTokenByTask: options.latestSupersedableTokenByTask ?? null,
        pendingTerminalEventByTask: options.pendingTerminalEventByTask ?? null,
        blockingTaskId: normalizeText(options.blockingTaskId) || null,
        blockedBy: options.blockedBy ?? null,
        blockedByEnqueueToken: options.blockedByEnqueueToken ?? null,
        blockedByPriority: options.blockedByPriority ?? null,
        reason: options.reason ?? null,
      });
    }

    async function appendControlPlaneSkipLog(
      eventName: string,
      options: {
        channel?: string | null;
        accountId?: string | null;
        chatId?: string | null;
        taskId?: string | null;
        sessionKey?: string | null;
        priority?: ControlPlanePriority | null;
        audienceKey?: string | null;
        schedulerDecision: "skipped";
        reason?: string | null;
      },
    ): Promise<void> {
      await appendDebugLog(config, `${eventName}:skipped`, {
        channel: normalizeText(options.channel) || null,
        chatId: normalizeText(options.chatId) || null,
        taskId: normalizeText(options.taskId) || null,
        sessionKey: normalizeSessionKey(options.sessionKey || ""),
        priority: options.priority ?? null,
        audienceKey:
          options.audienceKey ??
          (options.channel && options.chatId
            ? buildControlPlaneAudienceKey(options.channel, options.accountId || "", options.chatId)
            : null),
        schedulerDecision: options.schedulerDecision,
        reason: options.reason ?? null,
      });
    }

    async function sendControlPlaneMessage(payload: ControlPlaneMessage): Promise<void> {
      const normalizedTaskId = normalizeText(payload.taskId);
      const terminalState = normalizedTaskId ? controlPlaneTerminalByTask.get(normalizedTaskId) : undefined;
      if (shouldDropForTerminalControlPlaneState(payload.priority, terminalState)) {
        await appendControlPlaneDropLog(payload, {
          reason: "terminal-control-plane-state",
          dropCategory: "terminal",
          blockerScope: "task-terminal-committed",
          blockingTaskId: normalizedTaskId,
          blockedBy: terminalState?.eventName ?? null,
          blockedByEnqueueToken: terminalState?.enqueueToken ?? null,
          blockedByPriority: "p1-task-management",
          blockedByTerminalPhase: "committed",
          pendingTerminalEventByTask:
            normalizedTaskId ? controlPlanePendingTerminalByTask.get(normalizedTaskId)?.eventName ?? null : null,
        });
        return;
      }
      const audienceKey = buildControlPlaneAudienceKey(payload.channel, payload.accountId, payload.chatId);
      const nextSequence = (controlPlaneSequenceByAudience.get(audienceKey) ?? 0) + 1;
      controlPlaneSequenceByAudience.set(audienceKey, nextSequence);
      const enqueueToken = ++controlPlaneEnqueueToken;
      if (isPreemptingControlPlanePriority(payload.priority)) {
        controlPlaneLatestPreemptingTokenByAudience.set(audienceKey, enqueueToken);
        controlPlaneLatestPreemptingMetaByAudience.set(audienceKey, {
          enqueueToken,
          eventName: payload.eventName,
          priority: payload.priority,
          taskId: normalizedTaskId || null,
        });
        for (const [pendingTaskId, receipt] of pendingReceipts.entries()) {
          const pendingAudienceKey = buildControlPlaneAudienceKey(receipt.channel, receipt.accountId, receipt.chatId);
          if (pendingAudienceKey !== audienceKey) {
            continue;
          }
          if (receipt.timer) {
            clearTimeout(receipt.timer);
          }
          pendingReceipts.delete(pendingTaskId);
          await appendControlPlaneLaneLog(
            {
              ...payload,
              taskId: pendingTaskId,
              sessionKey: receipt.sessionKey,
            },
            "preempted-pending-followup",
            {
              schedulerDecision: "preempted-pending-followup",
              audienceKey,
              enqueueToken,
              blockingTaskId: normalizedTaskId || null,
              blockedBy: payload.eventName,
              blockedByEnqueueToken: enqueueToken,
              blockedByPriority: payload.priority,
              latestPreemptingTokenByAudience: controlPlaneLatestPreemptingTokenByAudience.get(audienceKey) ?? null,
              reason: "higher-priority-task-management-control-plane",
            },
          );
        }
      }
      if (normalizedTaskId && isSupersedableControlPlanePriority(payload.priority)) {
        controlPlaneLatestSupersedableTokenByTask.set(normalizedTaskId, enqueueToken);
        controlPlaneLatestSupersedableMetaByTask.set(normalizedTaskId, {
          enqueueToken,
          eventName: payload.eventName,
          priority: payload.priority,
          taskId: normalizedTaskId,
        });
      }
      if (isSupersedableControlPlanePriority(payload.priority)) {
        controlPlaneLatestSupersedableTokenByAudience.set(audienceKey, enqueueToken);
        controlPlaneLatestSupersedableMetaByAudience.set(audienceKey, {
          enqueueToken,
          eventName: payload.eventName,
          priority: payload.priority,
          taskId: normalizedTaskId || null,
        });
      }
      if (normalizedTaskId && isTerminalControlPlanePriority(payload.priority)) {
        controlPlanePendingTerminalByTask.set(normalizedTaskId, {
          eventName: payload.eventName,
          enqueueToken,
          priority: payload.priority,
          taskId: normalizedTaskId,
          terminalPhase: "pending",
        });
        await appendDebugLog(config, `${payload.eventName}:terminal-pending-armed`, {
          channel: payload.channel,
          chatId: payload.chatId,
          taskId: normalizedTaskId,
          sessionKey: payload.sessionKey,
          terminalPhase: "pending",
          priority: payload.priority,
          audienceKey,
          enqueueToken,
          pendingTerminalEventByTask: controlPlanePendingTerminalByTask.get(normalizedTaskId)?.eventName ?? null,
        });
      }
      await appendControlPlaneLaneLog(payload, "lane-enqueued", {
        schedulerDecision: "enqueued",
        audienceKey,
        enqueueToken,
        audienceSequence: nextSequence,
        latestPreemptingTokenByAudience: controlPlaneLatestPreemptingTokenByAudience.get(audienceKey) ?? null,
        latestSupersedableTokenByAudience: controlPlaneLatestSupersedableTokenByAudience.get(audienceKey) ?? null,
        latestSupersedableTokenByTask:
          normalizedTaskId ? controlPlaneLatestSupersedableTokenByTask.get(normalizedTaskId) ?? null : null,
        pendingTerminalEventByTask:
          normalizedTaskId ? controlPlanePendingTerminalByTask.get(normalizedTaskId)?.eventName ?? null : null,
      });
      const priorLane = controlPlaneLaneByAudience.get(audienceKey) ?? Promise.resolve();
      const nextLane = priorLane
        .catch(() => {})
        .then(async () => {
          const latestTerminalState = normalizedTaskId ? controlPlaneTerminalByTask.get(normalizedTaskId) : undefined;
          if (shouldDropForTerminalControlPlaneState(payload.priority, latestTerminalState)) {
            await appendControlPlaneDropLog(payload, {
              reason: "terminal-control-plane-state",
              dropCategory: "terminal",
              blockerScope: "task-terminal-committed",
              blockingTaskId: normalizedTaskId,
              terminalPhase: "committed",
              blockedBy: latestTerminalState?.eventName ?? null,
              blockedByEnqueueToken: latestTerminalState?.enqueueToken ?? null,
              blockedByPriority: "p1-task-management",
              blockedByTerminalPhase: "committed",
              audienceKey,
              enqueueToken,
              pendingTerminalEventByTask:
                normalizedTaskId ? controlPlanePendingTerminalByTask.get(normalizedTaskId)?.eventName ?? null : null,
            });
            return;
          }
          const pendingTerminalState = normalizedTaskId ? controlPlanePendingTerminalByTask.get(normalizedTaskId) : undefined;
          if (
            isSupersedableControlPlanePriority(payload.priority) &&
            (controlPlaneLatestPreemptingTokenByAudience.get(audienceKey) ?? -1) > enqueueToken
          ) {
            const blockingPreemptingMeta = controlPlaneLatestPreemptingMetaByAudience.get(audienceKey);
            await appendControlPlaneDropLog(payload, {
              reason: "preempted-by-higher-priority-control-plane",
              dropCategory: "preempted",
              blockerScope: "audience-higher-priority",
              blockingTaskId: blockingPreemptingMeta?.taskId ?? null,
              blockedBy: blockingPreemptingMeta?.eventName ?? null,
              blockedByEnqueueToken: blockingPreemptingMeta?.enqueueToken ?? null,
              blockedByPriority: blockingPreemptingMeta?.priority ?? null,
              audienceKey,
              enqueueToken,
              latestPreemptingTokenByAudience: controlPlaneLatestPreemptingTokenByAudience.get(audienceKey) ?? null,
            });
            return;
          }
          if (
            isSupersedableControlPlanePriority(payload.priority) &&
            (controlPlaneLatestSupersedableTokenByAudience.get(audienceKey) ?? -1) !== enqueueToken
          ) {
            const blockingSupersedableAudienceMeta = controlPlaneLatestSupersedableMetaByAudience.get(audienceKey);
            await appendControlPlaneDropLog(payload, {
              reason: "superseded-by-newer-control-plane-message-same-audience",
              dropCategory: "superseded",
              blockerScope: "audience-newer-message",
              blockingTaskId: blockingSupersedableAudienceMeta?.taskId ?? null,
              blockedBy: blockingSupersedableAudienceMeta?.eventName ?? null,
              blockedByEnqueueToken: blockingSupersedableAudienceMeta?.enqueueToken ?? null,
              blockedByPriority: blockingSupersedableAudienceMeta?.priority ?? null,
              audienceKey,
              enqueueToken,
              latestPreemptingTokenByAudience: controlPlaneLatestPreemptingTokenByAudience.get(audienceKey) ?? null,
              latestSupersedableTokenByAudience: controlPlaneLatestSupersedableTokenByAudience.get(audienceKey) ?? null,
            });
            return;
          }
          if (
            normalizedTaskId &&
            isSupersedableControlPlanePriority(payload.priority) &&
            pendingTerminalState
          ) {
            await appendControlPlaneDropLog(payload, {
              reason: "terminal-control-plane-pending",
              dropCategory: "terminal",
              blockerScope: "task-terminal-pending",
              blockingTaskId: normalizedTaskId,
              terminalPhase: "pending",
              blockedBy: pendingTerminalState.eventName,
              blockedByEnqueueToken: pendingTerminalState.enqueueToken,
              blockedByPriority: "p1-task-management",
              blockedByTerminalPhase: "pending",
              audienceKey,
              enqueueToken,
            });
            return;
          }
          if (
            normalizedTaskId &&
            isSupersedableControlPlanePriority(payload.priority) &&
            controlPlaneLatestSupersedableTokenByTask.get(normalizedTaskId) !== enqueueToken
          ) {
            const blockingSupersedableTaskMeta = controlPlaneLatestSupersedableMetaByTask.get(normalizedTaskId);
            await appendControlPlaneDropLog(payload, {
              reason: "superseded-by-newer-control-plane-message",
              dropCategory: "superseded",
              blockerScope: "task-newer-message",
              blockingTaskId: blockingSupersedableTaskMeta?.taskId ?? null,
              blockedBy: blockingSupersedableTaskMeta?.eventName ?? null,
              blockedByEnqueueToken: blockingSupersedableTaskMeta?.enqueueToken ?? null,
              blockedByPriority: blockingSupersedableTaskMeta?.priority ?? null,
              audienceKey,
              enqueueToken,
              latestSupersedableTokenByTask: controlPlaneLatestSupersedableTokenByTask.get(normalizedTaskId) ?? null,
            });
            return;
          }
          await appendControlPlaneLaneLog(payload, "lane-pass", {
            schedulerDecision: "passed",
            audienceKey,
            enqueueToken,
            audienceSequence: nextSequence,
            latestPreemptingTokenByAudience: controlPlaneLatestPreemptingTokenByAudience.get(audienceKey) ?? null,
            latestSupersedableTokenByAudience: controlPlaneLatestSupersedableTokenByAudience.get(audienceKey) ?? null,
            latestSupersedableTokenByTask:
              normalizedTaskId ? controlPlaneLatestSupersedableTokenByTask.get(normalizedTaskId) ?? null : null,
          });
          await deliverControlPlaneMessage(api, config, payload, {
            audienceKey,
            enqueueToken,
            audienceSequence: nextSequence,
          });
          if (normalizedTaskId && isTerminalControlPlanePriority(payload.priority)) {
            controlPlaneTerminalByTask.set(normalizedTaskId, {
              eventName: payload.eventName,
              ts: Date.now(),
              enqueueToken,
              priority: payload.priority,
              taskId: normalizedTaskId,
              terminalPhase: "committed",
            });
            await appendDebugLog(config, `${payload.eventName}:terminal-state-committed`, {
              channel: payload.channel,
              chatId: payload.chatId,
              taskId: normalizedTaskId,
              sessionKey: payload.sessionKey,
              terminalPhase: "committed",
              priority: payload.priority,
              audienceKey,
              enqueueToken,
              blockedBy: payload.eventName,
            });
            controlPlanePendingTerminalByTask.delete(normalizedTaskId);
          }
        });
      controlPlaneLaneByAudience.set(audienceKey, nextLane);
      try {
        await nextLane;
      } finally {
        if (controlPlaneLaneByAudience.get(audienceKey) === nextLane) {
          controlPlaneLaneByAudience.delete(audienceKey);
        }
      }
    }

    async function isTaskMonitorEnabled(sessionKey: string): Promise<boolean> {
      const normalizedSessionKey = normalizeSessionKey(sessionKey);
      const cached = taskMonitorEnabledBySession.get(normalizedSessionKey);
      if (typeof cached === "boolean") {
        return cached;
      }
      const result = await callHook(api, config, "taskmonitor-status", {
        session_key: normalizedSessionKey,
      });
      const enabled = result?.enabled !== false;
      taskMonitorEnabledBySession.set(normalizedSessionKey, enabled);
      return enabled;
    }

    async function isTaskMonitorEnabledForSession(sessionKey: string): Promise<boolean> {
      const normalizedSessionKey = normalizeSessionKey(sessionKey);
      const cached = taskMonitorEnabledBySession.get(normalizedSessionKey);
      if (typeof cached === "boolean") {
        return cached;
      }
      if (activeTaskBindings.has(normalizedSessionKey)) {
        return true;
      }
      return isTaskMonitorEnabled(normalizedSessionKey);
    }

    function isTaskMonitorEnabledForFollowupStage(sessionKey: string): boolean {
      const normalizedSessionKey = normalizeSessionKey(sessionKey);
      const cached = taskMonitorEnabledBySession.get(normalizedSessionKey);
      if (cached === false) {
        return false;
      }
      return true;
    }

    function clearSessionTaskArtifacts(sessionKey: string): void {
      const normalizedSessionKey = normalizeSessionKey(sessionKey);
      const activeTaskBinding = activeTaskBindings.get(normalizedSessionKey);
      if (activeTaskBinding?.taskId) {
        controlPlaneTerminalByTask.delete(activeTaskBinding.taskId);
        controlPlanePendingTerminalByTask.delete(activeTaskBinding.taskId);
        controlPlaneLatestSupersedableTokenByTask.delete(activeTaskBinding.taskId);
      }
      activeTaskBindings.delete(normalizedSessionKey);
      recentActivationBySession.delete(normalizedSessionKey);
      for (const [taskId, receipt] of pendingReceipts.entries()) {
        if (receipt.sessionKey !== normalizedSessionKey) {
          continue;
        }
        if (receipt.timer) {
          clearTimeout(receipt.timer);
        }
        pendingReceipts.delete(taskId);
      }
    }

    api.on("before_dispatch", async (event, ctx) => {
      if (!config.registerOnBeforeDispatch || !event.content?.trim()) {
        return;
      }
      if (isInternalStartupResumePrompt(event.content)) {
        enqueueDebugLog(config, "before_dispatch:startup-resume", {
          sessionKey: normalizeSessionKey(
            event.sessionKey || ctx.sessionKey || buildSessionKey(ctx.channelId ?? event.channel ?? "unknown", ctx.conversationId),
          ),
          channel: event.channel ?? ctx.channelId ?? "unknown",
        });
        return;
      }
      const sessionKey = normalizeSessionKey(
        event.sessionKey || ctx.sessionKey || buildSessionKey(ctx.channelId ?? event.channel ?? "unknown", ctx.conversationId),
      );
      const agentId = resolveAgentId(ctx.agentId, sessionKey, config.defaultAgentId);
      enqueueDebugLog(config, "before_dispatch", {
        agentId,
        sessionKey,
        channel: event.channel ?? ctx.channelId ?? "unknown",
        content: normalizeText(event.content).slice(0, 240),
      });
      const taskMonitorCommand = parseTaskMonitorCommand(event.content);
      const continuitySummaryCommand = parseContinuitySummaryCommand(event.content);
      const tasksSummaryCommand = parseTasksSummaryCommand(event.content);
      const channelName = event.channel ?? ctx.channelId ?? "unknown";
      const accountId = ctx.accountId ?? "";
      const chatId = ctx.conversationId ?? sessionKey;
      if (taskMonitorCommand) {
        const taskMonitorResult = await callHook(api, config, "taskmonitor-control", {
          session_key: sessionKey,
          action: taskMonitorCommand.action,
        });
        const enabled = taskMonitorResult?.enabled !== false;
        taskMonitorEnabledBySession.set(sessionKey, enabled);
        if (!enabled) {
          clearSessionTaskArtifacts(sessionKey);
        }
        const managementMessage = buildHookBackedControlPlaneMessage(taskMonitorResult, {
          channel: channelName,
          accountId,
          chatId,
          sessionKey,
          message:
            normalizeText(String(taskMonitorResult?.message || "")) ||
            "taskmonitor 状态已更新。",
          eventName: "taskmonitor-control",
          priority: "p1-task-management",
        });
        await sendControlPlaneMessage(managementMessage);
        return {
          handled: true,
        };
      }
      if (continuitySummaryCommand) {
        const continuityResult = await callHook(api, config, "main-continuity", {
          session_key: sessionKey,
          compact: continuitySummaryCommand.compact,
        });
        const continuityMessage = buildHookBackedControlPlaneMessage(continuityResult, {
          channel: channelName,
          accountId,
          chatId,
          sessionKey,
          message:
            normalizeText(String(continuityResult?.control_plane_message?.text || "")) ||
            "已收到状态查询请求，正在整理当前 task-system 状态。",
          eventName: "continuity-summary",
          priority: "p1-task-management",
        });
        await sendControlPlaneMessage(continuityMessage);
        enqueueDebugLog(config, "before_dispatch:continuity-summary-sent", {
          sessionKey,
          channel: channelName,
          compact: continuitySummaryCommand.compact,
          primaryActionKind: continuityResult?.primary_action_kind ?? null,
        });
        return;
      }
      if (tasksSummaryCommand) {
        const tasksSummaryResult = await callHook(api, config, "main-tasks-summary", {
          session_key: sessionKey,
          scope: tasksSummaryCommand.scope,
        });
        const tasksMessage = buildHookBackedControlPlaneMessage(tasksSummaryResult, {
          channel: channelName,
          accountId,
          chatId,
          sessionKey,
          message:
            normalizeText(String(tasksSummaryResult?.control_plane_message?.text || "")) ||
            "已收到任务查询请求，正在整理当前会话任务状态。",
          eventName: "main-tasks-summary",
          priority: "p1-task-management",
        });
        await sendControlPlaneMessage(tasksMessage);
        enqueueDebugLog(config, "before_dispatch:tasks-summary-sent", {
          sessionKey,
          channel: channelName,
          taskCount: tasksSummaryResult?.task_count ?? null,
          scope: tasksSummaryCommand.scope,
        });
        return;
      }
      if (!(await isTaskMonitorEnabled(sessionKey))) {
        enqueueDebugLog(config, "before_dispatch:taskmonitor-disabled", {
          agentId,
          sessionKey,
          schedulerDecision: "skipped",
          reason: "taskmonitor-disabled",
        });
        return;
      }
      const senderId = event.senderId ?? ctx.senderId ?? "";
      const queueIdentity = buildQueueIdentity({
        channel: channelName,
        accountId,
        conversationId: chatId,
        senderId,
        sessionKey,
        isGroup: Boolean(event.isGroup),
      });
      const queueIds = [chatId, senderId];
      const preRegistered = consumePreRegisteredSnapshot(
        queueIdentity,
        queueIds,
        [event.content, event.body].filter((entry): entry is string => typeof entry === "string"),
        senderId,
      );
      const registerResult =
        preRegistered?.registerResult ??
        (await callHook(api, config, "register", {
          agent_id: agentId,
          session_key: sessionKey,
          channel: channelName,
          account_id: accountId,
          chat_id: chatId,
          user_id: senderId,
          user_request: event.body || event.content,
          observe_only: true,
        }));
      const registerDecision = resolveRegisterDecision(registerResult);
      enqueueDebugLog(config, "immediate-ack:decision", {
        sessionKey,
        channel: channelName,
        queueKey: queueIdentity.queueKey,
        shouldRegisterTask: registerDecision.should_register_task ?? null,
        classificationReason: registerDecision.classification_reason ?? null,
        taskId: registerDecision.task_id ?? null,
        preRegistered: Boolean(preRegistered),
        producerMode: preRegistered ? "receive-side-producer" : "dispatch-side-priority-only",
        producerConsumerAligned: Boolean(preRegistered),
      });
      if (typeof registerDecision.task_id === "string" && registerDecision.task_id.trim()) {
        activeTaskBindings.set(sessionKey, {
          taskId: registerDecision.task_id.trim(),
        });
      }
      const classificationReason = String(registerDecision.classification_reason || "").trim();
      const isExistingActive = classificationReason === "existing-active-task";
      const isLongTask = classificationReason === "long-task" || classificationReason === "scheduled-continuation";
      const shouldSendShortTaskAck = isLongTask || config.sendImmediateAckForShortTasks;
      const shouldSendImmediateAck =
        config.sendImmediateAckOnRegister &&
        Boolean(registerDecision.should_register_task) &&
        shouldSendShortTaskAck &&
        !isExistingActive;
      const immediateAckMessage = buildImmediateReceiptMessage(config, registerResult);
      const receiptTaskId =
        typeof registerDecision.task_id === "string" && registerDecision.task_id.trim()
          ? registerDecision.task_id.trim()
          : "";
      const queuedEarlyAckConsumed =
        shouldSendImmediateAck &&
        (Boolean(preRegistered?.earlyAckSent) || consumeQueuedEarlyAck(queueIdentity, queueIds));

      if (
        config.sendImmediateAckOnRegister &&
        Boolean(registerDecision.should_register_task) &&
        shouldSendShortTaskAck &&
        isExistingActive
      ) {
        await appendControlPlaneSkipLog("immediate-ack", {
          channel: channelName,
          accountId,
          chatId,
          taskId: registerDecision.task_id ?? null,
          sessionKey,
          priority: "p0-receive-ack",
          schedulerDecision: "skipped",
          reason: "existing-active-task",
        });
      }

      if (queuedEarlyAckConsumed) {
        await appendControlPlaneSkipLog("immediate-ack", {
          channel: channelName,
          accountId,
          chatId,
          taskId: registerDecision.task_id ?? null,
          sessionKey,
          priority: "p0-receive-ack",
          schedulerDecision: "skipped",
          reason: "queued-early-ack-already-sent",
        });
      }

      if (shouldSendImmediateAck && !queuedEarlyAckConsumed) {
        if (isLongTask && typeof registerDecision.task_id === "string" && registerDecision.task_id.trim()) {
          await sendControlPlaneMessage({
            eventName: "immediate-ack",
            priority: "p0-receive-ack",
            channel: channelName,
            accountId,
            chatId,
            taskId: registerDecision.task_id,
            sessionKey,
            message: immediateAckMessage,
          });
        } else {
          await sendControlPlaneMessage({
            channel: channelName,
            accountId,
            chatId,
            sessionKey,
            message: immediateAckMessage,
            eventName: "immediate-ack",
            priority: "p0-receive-ack",
            taskId: receiptTaskId || undefined,
          });
          if (!receiptTaskId) {
            return;
          }
          const existingReceipt = pendingReceipts.get(receiptTaskId);
          if (existingReceipt?.timer) {
            clearTimeout(existingReceipt.timer);
          }
          const timer = setTimeout(() => {
            const current = pendingReceipts.get(receiptTaskId);
            if (!current) {
              return;
            }
            pendingReceipts.delete(receiptTaskId);
            void (async () => {
              const followupCheck = await callHook(api, config, "should-send-short-followup", {
                task_id: current.taskId,
              });
              if (!followupCheck?.should_send) {
                await appendControlPlaneSkipLog("short-task-followup", {
                  channel: current.channel,
                  accountId: current.accountId,
                  chatId: current.chatId,
                  taskId: current.taskId,
                  sessionKey: current.sessionKey,
                  priority: "p2-progress-followup",
                  schedulerDecision: "skipped",
                  reason: followupCheck?.reason ?? "unknown",
                });
                return;
              }
              const hookControlPlaneMessage = extractHookControlPlaneMessage(followupCheck);
              await sendControlPlaneMessage({
                channel: current.channel,
                accountId: current.accountId ?? "",
                chatId: current.chatId,
                sessionKey: current.sessionKey,
                message:
                  hookControlPlaneMessage?.message ||
                  normalizeText(String(followupCheck?.followup_message || "")) ||
                  config.shortTaskFollowupTemplate,
                eventName: hookControlPlaneMessage?.eventName || "short-task-followup",
                priority: hookControlPlaneMessage?.priority || "p2-progress-followup",
                taskId: hookControlPlaneMessage?.taskId || current.taskId,
              });
            })();
          }, config.shortTaskFollowupTimeoutMs);
          pendingReceipts.set(receiptTaskId, {
            taskId: receiptTaskId,
            sessionKey,
            channel: event.channel ?? ctx.channelId ?? "unknown",
            accountId: ctx.accountId ?? "",
            chatId: ctx.conversationId ?? sessionKey,
            taskKind: "short",
            timer,
          });
        }
      }

      if (classificationReason === "continuation-task") {
        enqueueDebugLog(config, "before_dispatch:continuation-handled", {
          agentId,
          sessionKey,
          taskId: registerDecision.task_id ?? null,
        });
        return {
          handled: true,
        };
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
          schedulerDecision: "skipped",
          reason: "internal-retry-prompt",
        });
        return;
      }
      if (isContinuationWakePrompt(event.prompt)) {
        await appendDebugLog(config, "before_agent_start:continuation-wake", {
          agentId: ctx.agentId || config.defaultAgentId,
          sessionKey: ctx.sessionKey || "",
          schedulerDecision: "skipped",
          reason: "continuation-wake-prompt",
        });
        return;
      }
      if (ctx.trigger && ctx.trigger !== "user") {
        await appendDebugLog(config, "before_agent_start:ignored", {
          trigger: ctx.trigger,
          agentId: ctx.agentId || config.defaultAgentId,
          sessionKey: ctx.sessionKey || "",
          schedulerDecision: "skipped",
          reason: "unsupported-trigger",
        });
        return;
      }
      const sessionKey = ctx.sessionKey?.trim();
      if (!sessionKey) {
        await appendDebugLog(config, "before_agent_start:missing-session", {
          agentId: ctx.agentId || config.defaultAgentId,
          prompt: normalizeText(event.prompt).slice(0, 240),
          schedulerDecision: "skipped",
          reason: "missing-session",
        });
        return;
      }
      const agentId = resolveAgentId(ctx.agentId, sessionKey, config.defaultAgentId);
      const normalizedSessionKey = normalizeSessionKey(sessionKey);
      if (!isTaskMonitorEnabledForFollowupStage(normalizedSessionKey)) {
        await appendDebugLog(config, "before_agent_start:taskmonitor-disabled", {
          agentId,
          sessionKey: normalizedSessionKey,
          schedulerDecision: "skipped",
          reason: "taskmonitor-disabled",
        });
        return;
      }
      await appendDebugLog(config, "before_agent_start", {
        agentId,
        sessionKey: normalizedSessionKey,
        trigger: ctx.trigger || "unknown",
        prompt: normalizeText(event.prompt).slice(0, 240),
        schedulerDecision: "entered",
        reason: "before-agent-start",
      });
      const activeTaskBinding = activeTaskBindings.get(normalizedSessionKey);
      const activationSignature = JSON.stringify({
        taskId: activeTaskBinding?.taskId ?? "",
        trigger: ctx.trigger || "unknown",
        prompt: normalizeText(event.prompt).slice(0, 240),
      });
      const recentActivation = recentActivationBySession.get(normalizedSessionKey);
      if (
        recentActivation &&
        recentActivation.signature === activationSignature &&
        Date.now() - recentActivation.ts < 3000
      ) {
        await appendDebugLog(config, "before_agent_start:duplicate-activation-skipped", {
          agentId,
          sessionKey: normalizedSessionKey,
          taskId: activeTaskBinding?.taskId ?? null,
          schedulerDecision: "skipped",
          reason: "duplicate-activation",
          trigger: ctx.trigger || "unknown",
        });
        return;
      }
      recentActivationBySession.set(normalizedSessionKey, {
        signature: activationSignature,
        ts: Date.now(),
      });
      await callHook(api, config, "activate-latest", {
        agent_id: agentId,
        session_key: normalizedSessionKey,
        task_id: activeTaskBinding?.taskId,
      });
    });

    api.on("before_prompt_build", async (event, ctx) => {
      if (!config.registerOnBeforeDispatch || !event.prompt?.trim()) {
        return;
      }
      if (isContinuationWakePrompt(event.prompt)) {
        await appendDebugLog(config, "before_prompt_build:continuation-wake", {
          agentId: ctx.agentId || config.defaultAgentId,
          sessionKey: ctx.sessionKey || "",
          schedulerDecision: "skipped",
          reason: "continuation-wake-prompt",
        });
        return;
      }
      const sessionKey = ctx.sessionKey?.trim();
      if (!sessionKey) {
        await appendDebugLog(config, "before_prompt_build:missing-session", {
          agentId: ctx.agentId || config.defaultAgentId,
          prompt: normalizeText(event.prompt).slice(0, 240),
          schedulerDecision: "skipped",
          reason: "missing-session",
        });
        return;
      }
      const agentId = ctx.agentId || config.defaultAgentId;
      await appendDebugLog(config, "before_prompt_build", {
        agentId,
        sessionKey,
        trigger: ctx.trigger || "unknown",
        prompt: normalizeText(event.prompt).slice(0, 240),
        schedulerDecision: "entered",
        reason: "before-prompt-build",
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
        schedulerDecision: "entered",
        reason: "before-model-resolve",
      });
    });

    api.on("message_sending", async (event, ctx) => {
      if (!config.syncProgressOnMessageSending || !event.content?.trim()) {
        return;
      }
      if (ctx.sessionKey?.trim()) {
        if (!(await isTaskMonitorEnabled(ctx.sessionKey))) {
          await appendDebugLog(config, "message_sending:taskmonitor-disabled", {
            agentId: ctx.agentId || config.defaultAgentId,
            sessionKey: ctx.sessionKey || "",
            schedulerDecision: "skipped",
            reason: "taskmonitor-disabled",
          });
          return;
        }
        const resolvedAgentId = resolveAgentId(ctx.agentId, ctx.sessionKey, config.defaultAgentId);
        const normalizedSessionKey = normalizeSessionKey(ctx.sessionKey);
        const continuationFulfilled = await callHook(api, config, "fulfill-due-continuation", {
          agent_id: resolvedAgentId,
          session_key: normalizedSessionKey,
          content: event.content,
        });
        if (continuationFulfilled?.updated) {
          await appendDebugLog(config, "message_sending:continuation-fulfilled", {
            agentId: resolvedAgentId,
            sessionKey: normalizedSessionKey,
            matchedReplyText: continuationFulfilled.matched_reply_text ?? null,
            schedulerDecision: "skipped",
            reason: "continuation-fulfilled",
          });
          return;
        }
      }
      if (!shouldSyncProgress(event.content, config)) {
        await appendDebugLog(config, "message_sending:ignored", {
          sessionKey: ctx.sessionKey || buildSessionKey(ctx.channelId, ctx.conversationId),
          content: normalizeText(event.content).slice(0, 240),
          schedulerDecision: "skipped",
          reason: "progress-sync-filtered",
        });
        return;
      }
      const sessionKey = normalizeSessionKey(buildSessionKey(ctx.channelId, ctx.conversationId));
      const agentId = resolveAgentId(ctx.agentId, sessionKey, config.defaultAgentId);
      await appendDebugLog(config, "message_sending", {
        agentId,
        sessionKey,
        content: normalizeText(event.content).slice(0, 240),
        schedulerDecision: "entered",
        reason: "progress-sync",
      });
      const activeTaskBinding = activeTaskBindings.get(sessionKey);
      await callHook(api, config, "progress-active", {
        agent_id: agentId,
        session_key: sessionKey,
        task_id: activeTaskBinding?.taskId,
        progress_note: normalizeText(event.content).slice(0, 240),
      });
    });

    api.on("llm_output", async (event, ctx) => {
      if (!config.syncProgressOnMessageSending) {
        return;
      }
      const sessionKey = normalizeSessionKey(ctx.sessionKey?.trim() || "");
      if (!sessionKey) {
        return;
      }
      if (!(await isTaskMonitorEnabledForSession(sessionKey))) {
        await appendDebugLog(config, "llm_output:taskmonitor-disabled", {
          agentId: ctx.agentId || config.defaultAgentId,
          sessionKey,
          schedulerDecision: "skipped",
          reason: "taskmonitor-disabled",
        });
        return;
      }
      const text = normalizeText((event.assistantTexts || []).join("\n"));
      if (!text) {
        return;
      }
      const agentId = resolveAgentId(ctx.agentId, sessionKey, config.defaultAgentId);
      const continuationFulfilled = await callHook(api, config, "fulfill-due-continuation", {
        agent_id: agentId,
        session_key: sessionKey,
        content: text,
      });
      if (continuationFulfilled?.updated) {
        await appendDebugLog(config, "llm_output:continuation-fulfilled", {
          agentId,
          sessionKey,
          matchedReplyText: continuationFulfilled.matched_reply_text ?? null,
          content: text.slice(0, 240),
          schedulerDecision: "skipped",
          reason: "continuation-fulfilled",
        });
        return;
      }
      if (!shouldSyncProgress(text, config)) {
        await appendDebugLog(config, "llm_output:ignored", {
          agentId,
          sessionKey,
          content: text.slice(0, 240),
          schedulerDecision: "skipped",
          reason: "progress-sync-filtered",
        });
        return;
      }
      await appendDebugLog(config, "llm_output", {
        agentId,
        sessionKey,
        content: text.slice(0, 240),
        schedulerDecision: "entered",
        reason: "progress-sync",
      });
      const activeTaskBinding = activeTaskBindings.get(sessionKey);
      await callHook(api, config, "progress-active", {
        agent_id: agentId,
        session_key: sessionKey,
        task_id: activeTaskBinding?.taskId,
        progress_note: text.slice(0, 240),
      });
    });

    api.on("agent_end", async (event, ctx) => {
      const normalizedSessionKey = normalizeSessionKey(ctx.sessionKey?.trim() || "");
      if (!config.finalizeOnAgentEnd || !normalizedSessionKey) {
        return;
      }
      if (!(await isTaskMonitorEnabledForSession(normalizedSessionKey))) {
        await appendDebugLog(config, "agent_end:taskmonitor-disabled", {
          agentId: resolveAgentId(ctx.agentId, normalizedSessionKey, config.defaultAgentId),
          sessionKey: normalizedSessionKey,
          success: event.success,
          schedulerDecision: "skipped",
          reason: "taskmonitor-disabled",
        });
        clearSessionTaskArtifacts(normalizedSessionKey);
        return;
      }
      const activeTaskBinding = activeTaskBindings.get(normalizedSessionKey);
      if (activeTaskBinding?.taskId) {
        controlPlaneTerminalByTask.set(activeTaskBinding.taskId, {
          eventName: event.success ? "agent-settled" : "agent-failed",
          ts: Date.now(),
        });
        await appendDebugLog(config, "agent_end:terminal-state-armed", {
          agentId: resolveAgentId(ctx.agentId, normalizedSessionKey, config.defaultAgentId),
          sessionKey: normalizedSessionKey,
          taskId: activeTaskBinding.taskId,
          terminalPhase: "armed",
          terminalEventName: event.success ? "agent-settled" : "agent-failed",
          success: event.success,
        });
      }
      const pendingReceipt = activeTaskBinding ? pendingReceipts.get(activeTaskBinding.taskId) : undefined;
      if (pendingReceipt?.timer) {
        clearTimeout(pendingReceipt.timer);
        await appendDebugLog(config, "agent_end:pending-followup-cleared", {
          agentId: resolveAgentId(ctx.agentId, normalizedSessionKey, config.defaultAgentId),
          sessionKey: normalizedSessionKey,
          taskId: activeTaskBinding?.taskId ?? null,
          terminalPhase: "armed",
          reason: "terminal-agent-end",
        });
      }
      if (activeTaskBinding) {
        pendingReceipts.delete(activeTaskBinding.taskId);
      }
      for (const [taskId, receipt] of pendingReceipts.entries()) {
        if (receipt.sessionKey !== normalizedSessionKey) {
          continue;
        }
        if (receipt.timer) {
          clearTimeout(receipt.timer);
          await appendDebugLog(config, "agent_end:pending-followup-cleared", {
            agentId: resolveAgentId(ctx.agentId, normalizedSessionKey, config.defaultAgentId),
            sessionKey: normalizedSessionKey,
            taskId,
            terminalPhase: "armed",
            reason: "terminal-agent-end-session-sweep",
          });
        }
        pendingReceipts.delete(taskId);
      }
      await appendDebugLog(config, "agent_end", {
        agentId: resolveAgentId(ctx.agentId, normalizedSessionKey, config.defaultAgentId),
        sessionKey: normalizedSessionKey,
        success: event.success,
        error: event.error ?? null,
        schedulerDecision: "entered",
        reason: "agent-end",
      });
      const finalizeResult = await callHook(api, config, "finalize-active", {
        agent_id: resolveAgentId(ctx.agentId, normalizedSessionKey, config.defaultAgentId),
        session_key: normalizedSessionKey,
        task_id: activeTaskBinding?.taskId,
        success: event.success,
        has_visible_output: event.success ? hasVisibleAssistantOutput(event) : false,
        result_summary: event.success ? summarizeAgentEnd(event) : undefined,
        error: event.error,
      });
      const shouldDeliverFinalizeControlPlane =
        Boolean(finalizeResult?.control_plane_message) &&
        Boolean(activeTaskBinding?.taskId) &&
        (!event.success || !hasVisibleAssistantOutput(event));
      if (shouldDeliverFinalizeControlPlane) {
        await sendControlPlaneMessage(
          buildHookBackedControlPlaneMessage(finalizeResult, {
            channel: ctx.channelId ?? "unknown",
            accountId: ctx.accountId ?? "",
            chatId: ctx.conversationId ?? normalizedSessionKey,
            sessionKey: normalizedSessionKey,
            taskId: activeTaskBinding?.taskId,
            eventName: event.success ? "task-completed" : "task-failed",
            priority: "p1-task-management",
            message: event.success ? "当前任务已完成。" : "当前任务已失败。",
          }),
        );
      }
      if (activeTaskBinding) {
        await appendDebugLog(config, "agent_end:terminal-state-cleared", {
          agentId: resolveAgentId(ctx.agentId, normalizedSessionKey, config.defaultAgentId),
          sessionKey: normalizedSessionKey,
          taskId: activeTaskBinding.taskId,
          terminalPhase: "cleared",
          reason: "finalize-active-complete",
        });
        controlPlaneTerminalByTask.delete(activeTaskBinding.taskId);
        activeTaskBindings.delete(normalizedSessionKey);
      }
      recentActivationBySession.delete(normalizedSessionKey);
    });

    api.registerService({
      id: "openclaw-task-system-host-delivery",
      async start() {
        await warmOutboundAdapters(api, ["telegram", "feishu"]);
        if (config.enableWatchdogRecoveryRunner) {
          watchdogRecoveryTimer = setInterval(() => {
            void processWatchdogRecovery(api, config);
          }, config.watchdogRecoveryPollMs);
          await appendDebugLog(config, "watchdog-auto-recover:startup-kickoff", {
            startupRecovery: true,
            attempt: "initial",
            schedulerDecision: "entered",
            reason: "startup-watchdog-recovery",
          });
          await processWatchdogRecovery(api, config, { startupRecovery: true });
          startupWatchdogRecoveryRetryTimer = setTimeout(() => {
            void appendDebugLog(config, "watchdog-auto-recover:startup-kickoff", {
              startupRecovery: true,
              attempt: "delayed-retry",
              schedulerDecision: "entered",
              reason: "startup-watchdog-recovery",
            });
            void processWatchdogRecovery(api, config, { startupRecovery: true });
          }, 10000);
        }
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
        if (watchdogRecoveryTimer) {
          clearInterval(watchdogRecoveryTimer);
          watchdogRecoveryTimer = null;
        }
        if (startupWatchdogRecoveryRetryTimer) {
          clearTimeout(startupWatchdogRecoveryRetryTimer);
          startupWatchdogRecoveryRetryTimer = null;
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
        activeTaskBindings.clear();
        controlPlaneSequenceByAudience.clear();
        controlPlaneLaneByAudience.clear();
        controlPlaneLatestPreemptingTokenByAudience.clear();
        controlPlaneLatestSupersedableTokenByAudience.clear();
        controlPlaneTerminalByTask.clear();
        controlPlanePendingTerminalByTask.clear();
        controlPlaneLatestSupersedableTokenByTask.clear();
        taskMonitorEnabledBySession.clear();
        recentActivationBySession.clear();
      },
    });

    enqueueDebugLog(config, "plugin:load:enabled", {
      enabled: true,
      runtimeRoot: config.runtimeRoot,
      schedulerDecision: "entered",
      reason: "plugin-register-complete",
      logLevel: "info",
      operatorVisible: true,
    });
    api.logger.info(`[task-system] plugin loaded (root=${config.runtimeRoot})`);
  },
};

export default taskSystemPlugin;
