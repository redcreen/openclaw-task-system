# Plugin Installation Guide

## 1. 目标

本文件说明如何在不修改 OpenClaw 主程序的前提下，把 `openclaw-task-system` 以插件方式接入。

这里关注的是：

- 如何安装
- 如何配置
- 如何做安装后验证

这里不负责解释完整 roadmap 或架构设计；那两部分分别看：

- `docs/ROADMAP.md`
- `docs/ARCHITECTURE.md`

## 2. 前提

以下路径应存在：

- `workspace/openclaw-task-system/plugin/`
- `workspace/openclaw-task-system/scripts/runtime/openclaw_hooks.py`
- `workspace/openclaw-task-system/config/task_system.json`
  示例参考：`workspace/openclaw-task-system/config/task_system.example.json`

## 3. 安装前自检

先运行：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py
```

如果需要机器可读输出：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py --json
```

安装前还可以运行本地联调 smoke：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py
```

如果需要机器可读输出：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py --json
```

## 4. 链接安装插件

推荐使用 link 方式安装：

```bash
openclaw plugins install --link /Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin
```

## 5. OpenClaw 配置示例

示例文件：

- `config/openclaw_plugin.example.json`

核心配置块示例：

```json
{
  "plugins": {
    "entries": {
      "openclaw-task-system": {
        "enabled": true,
        "config": {
          "enabled": true,
          "pythonBin": "python3",
          "runtimeRoot": "/Users/redcreen/.openclaw/workspace/openclaw-task-system",
          "configPath": "/Users/redcreen/.openclaw/workspace/openclaw-task-system/config/task_system.json",
          "defaultAgentId": "main",
          "registerOnBeforeDispatch": true,
          "sendImmediateAckOnRegister": true,
          "sendImmediateAckForShortTasks": true,
          "immediateAckTemplate": "已收到，正在开始处理；如果 30 秒内还没有新的阶段结果，我会先同步当前进展。",
          "shortTaskFollowupTimeoutMs": 30000,
          "shortTaskFollowupTemplate": "已收到你的消息，当前仍在处理中；稍后给你正式结果。",
          "syncProgressOnMessageSending": true,
          "finalizeOnAgentEnd": true,
          "enableHostFeishuDelivery": true,
          "hostDeliveryPollMs": 3000,
          "minProgressMessageLength": 20
        }
      }
    }
  }
}
```

## 6. 当前插件行为

当前插件已经不只是“第一阶段接入器”，而是 task-system 的主要 OpenClaw 扩展入口。

它当前负责的能力包括：

- 在 `before_dispatch` 期间接入 task register / pre-register / immediate ack 逻辑
- 对短任务与长任务走统一的 control-plane 发送入口
- 在 `message_sending` / `llm_output` 期间回写可见进展
- 在 `agent_end` 期间做任务终态收口
- 处理 short follow-up、continuation、host delivery、watchdog / continuity 等 runtime 结果
- 维护最小 control-plane lane / scheduler，逐步把控制面消息从普通 reply 中分离

需要明确的是：

- “所有 channel 都已做到 receive-time `[wd]`”还没有完成
- 当前更准确的状态是：plugin 已经把 dispatch 之后的控制面链路收得更稳、更统一，并在为后续 receive-time producer 做准备

其中 `message_sending` 只会把“足够像阶段进展”的外发消息记成进展，避免把过短或占位性的回复误判成真实推进。

## 7. 推荐验证顺序

建议按这个顺序验证：

1. 运行 `plugin_doctor.py`
2. 运行 `plugin_smoke.py`
3. 运行 `main_acceptance.py`
4. 安装并启用插件
5. 在 OpenClaw 中发起一个长任务
6. 检查任务是否完成注册、进展回写、最终收口
7. 对静默任务运行 `watchdog_cycle.py`，确认能产出发送指令
8. 如果目标是 Feishu，在 OpenClaw 保持运行状态下等待插件 bridge 轮询，直接在 Feishu app 中观察是否收到提醒

## 8. 当前边界

当前仍然成立的边界是：

- 不改 OpenClaw core
- 不改宿主代码
- 不改其它插件代码
- 只通过现有扩展点和本项目自身 plugin/runtime 工作

当前仍未完成的，不应在安装文档里误写成“已经具备”的能力包括：

- 所有 channel 的 receive-time `[wd]`
- 所有 channel 的统一 receive-side producer
- 完整的多 channel control-plane 闭环

这些属于 roadmap 与 architecture 持续推进内容，不属于本文件的安装结论。
