# Plugin Installation Guide

## 1. 目标

本文件说明如何在不修改 OpenClaw 主程序的前提下，把任务系统以插件方式接入。

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

## 6. 第一阶段插件行为

当前插件第一阶段会做这些事：

- 在 `before_dispatch` 期间注册长任务候选
- 对所有消息立刻回一条“已收到，开始处理”的轻提示
- 对短任务，如果超时还没返回，再补一条“仍在处理中”
- 对长任务，如果后续 30 秒内没有阶段进展，再由 watchdog 补提示
- 在 `message_sending` 期间为当前活动任务回写进展
- 在 `agent_end` 期间自动完成或失败收口
- 在插件内部轮询 `send-instructions/`，把 `feishu` 通知直接投递回宿主会话

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

当前阶段还不要求：

- 自动标记完成
- 自动标记失败
- 全量多 agent 生命周期接入

这些会在下一阶段继续补充。
