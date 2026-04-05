# Plugin Installation Guide

本文件只负责：

- 安装前检查
- 插件链接安装
- OpenClaw 插件配置
- 安装后的最小验证

项目背景、能力边界、路线图统一看：

- [README.md](/Users/redcreen/Project/openclaw-task-system/README.md)
- [ROADMAP.md](/Users/redcreen/Project/openclaw-task-system/docs/ROADMAP.md)

## 1. 前提

以下内容应存在：

- [plugin/](/Users/redcreen/Project/openclaw-task-system/plugin)
- [scripts/runtime/openclaw_hooks.py](/Users/redcreen/Project/openclaw-task-system/scripts/runtime/openclaw_hooks.py)
- [config/task_system.json](/Users/redcreen/Project/openclaw-task-system/config/task_system.json)

如果还没有正式配置，可以从样例开始：

- [config/task_system.example.json](/Users/redcreen/Project/openclaw-task-system/config/task_system.example.json)
- [config/openclaw_plugin.example.json](/Users/redcreen/Project/openclaw-task-system/config/openclaw_plugin.example.json)

## 2. 安装前检查

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py
python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py
```

机器可读输出：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py --json
python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py --json
```

## 3. 正式安装插件

推荐直接用正式安装方式：

```bash
openclaw plugins install /Users/redcreen/Project/openclaw-task-system/plugin
```

## 4. OpenClaw 插件配置

最常用的配置示例：

```json
{
  "plugins": {
    "entries": {
      "openclaw-task-system": {
        "enabled": true,
        "config": {
          "enabled": true,
          "taskMessagePrefix": "[wd] ",
          "pythonBin": "python3",
          "runtimeRoot": "/Users/redcreen/Project/openclaw-task-system",
          "configPath": "/Users/redcreen/Project/openclaw-task-system/config/task_system.json",
          "debugLogPath": "/Users/redcreen/Project/openclaw-task-system/data/plugin-debug.log",
          "defaultAgentId": "main",
          "registerOnBeforeDispatch": true,
          "sendImmediateAckOnRegister": true,
          "sendImmediateAckForShortTasks": true,
          "shortTaskFollowupTimeoutMs": 30000,
          "syncProgressOnMessageSending": true,
          "finalizeOnAgentEnd": true,
          "enableHostFeishuDelivery": true,
          "hostDeliveryPollMs": 3000,
          "enableContinuationRunner": true,
          "continuationPollMs": 3000,
          "enableWatchdogRecoveryRunner": true,
          "watchdogRecoveryPollMs": 30000
        }
      }
    }
  }
}
```

### 核心配置项

- `runtimeRoot`
  - 本仓库绝对路径
- `configPath`
  - task system runtime 配置路径
- `defaultAgentId`
  - 默认接入 agent，通常是 `main`
- `sendImmediateAckOnRegister`
  - 注册任务时发送 `[wd]`
- `sendImmediateAckForShortTasks`
  - 短任务也允许走统一 `[wd]`
- `shortTaskFollowupTimeoutMs`
  - 短任务 follow-up 超时
- `syncProgressOnMessageSending`
  - 在用户可见消息发送时同步进展
- `finalizeOnAgentEnd`
  - `agent_end` 时自动收口
- `enableHostFeishuDelivery`
  - 启用 Feishu 宿主外发
- `enableContinuationRunner`
  - 启用 delayed reply / continuation 轮询
- `enableWatchdogRecoveryRunner`
  - 启动 watchdog recovery runner

## 5. 安装后的最小验证

建议顺序：

1. 跑 `plugin_doctor.py`
2. 跑 `plugin_smoke.py`
3. 链接安装插件
4. 启用插件配置
5. 重启或重新加载 OpenClaw
6. 跑一次 dashboard / stable acceptance

示例：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --json
python3 workspace/openclaw-task-system/scripts/runtime/stable_acceptance.py --json
```

## 6. 插件当前边界

当前插件已经是 task-system 的主要 OpenClaw 扩展入口，但要注意边界：

- 它已经稳定接管 dispatch 之后的 control-plane 链路
- 它已经支持 delayed reply、watchdog recovery、host delivery、终态收口
- 它不代表“所有 channel 都已经做到 receive-time `[wd]`”

更准确地说：

- Feishu 当前是 `receive-side-producer`
- Telegram / WebChat 当前是 `dispatch-side-priority-only`

正式边界与验收结论，以这两份文档为准：

- [README.md](/Users/redcreen/Project/openclaw-task-system/README.md)
- [ROADMAP.md](/Users/redcreen/Project/openclaw-task-system/docs/ROADMAP.md)
