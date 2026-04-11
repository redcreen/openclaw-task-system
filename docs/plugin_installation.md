[English](plugin_installation.md) | [中文](plugin_installation.zh-CN.md)

# Plugin Installation Guide

本文件只负责：

- 安装前检查
- 插件正式安装
- OpenClaw 插件配置
- 安装后的最小验证

项目背景、能力边界、路线图统一看：

- [README.md](../README.md)
- [roadmap.md](./roadmap.md)
- [local_install_validation_2026-04-09.md](./local_install_validation_2026-04-09.md)

## 1. 前提

以下内容应存在：

- [plugin/](../plugin)
- [scripts/runtime/openclaw_hooks.py](../scripts/runtime/openclaw_hooks.py)
- [config/task_system.json](../config/task_system.json)

如果还没有正式配置，可以从样例开始：

- [config/task_system.example.json](../config/task_system.example.json)
- [config/openclaw_plugin.example.json](../config/openclaw_plugin.example.json)

## 2. 安装前检查

```bash
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py
```

机器可读输出：

```bash
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
```

## 3. 正式安装插件

推荐普通用户直接用稳定版远程一键安装：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/v0.1.0/scripts/install_remote.sh)
```

如果你更喜欢 OpenClaw 原生的远程安装方式，也可以直接：

```bash
openclaw plugins install git+https://github.com/redcreen/openclaw-task-system.git#v0.1.0
```

开发用户如果需要主干最新版，可以用：

```bash
OPENCLAW_TASK_SYSTEM_REF=main bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/main/scripts/install_remote.sh)
```

如果你已经在源码目录里，也可以继续用本地正式安装方式：

```bash
openclaw plugins install ./plugin
```

当前本地源码安装有一个现实边界需要注意：

- `openclaw-task-system` 的 plugin runtime 通过 `child_process.spawn(...)` 调用 Python hooks
- OpenClaw 2026.4.2 的插件安装器会把这一模式识别为 dangerous code pattern
- 即使显式加上 `--dangerously-force-unsafe-install`，当前 CLI 仍可能拒绝重新安装这个插件

本地实测报错类似：

```text
Plugin "openclaw-task-system" installation blocked: dangerous code patterns detected:
Shell command execution detected (child_process)
```

因此，当前推荐做法是：

1. 继续维护 `plugin/` installable payload
2. 用 `plugin_doctor.py`、`plugin_smoke.py`、`stable_acceptance.py` 和 planning acceptance 工具链做源码侧验证
3. 真正需要切换安装态时，先确认 OpenClaw 后续是否放宽该插件的本地安装策略，或采用项目内部认可的安装路径

不要默认假设 `openclaw plugins install ./plugin` 在当前版本一定可用。

当前如果只是想确认“源码 payload”和“本地安装态”是否已经漂移，不必只记独立脚本名：

- `python3 scripts/runtime/main_ops.py dashboard --only-issues`
- `python3 scripts/runtime/main_ops.py triage --json`
- `python3 scripts/runtime/main_ops.py plugin-install-drift --json`

其中 `dashboard / triage` 已经会直接投影 install drift 计数与建议动作；如果只有 install drift 这一类问题，`dashboard` 现在也会直接显示 `warn`。

## 4. OpenClaw 插件配置

远程安装脚本会自动写入一个最小可用配置到：

- `~/.openclaw/openclaw.json`

如果你想先预览或手动重写最小配置，可以运行：

```bash
python3 scripts/runtime/configure_openclaw_plugin.py
python3 scripts/runtime/configure_openclaw_plugin.py --write
```

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
  - 可选。默认就是插件安装目录
- `configPath`
  - 可选。默认是 `<runtimeRoot>/config/task_system.json`
- `debugLogPath`
  - 可选。默认是 `<runtimeRoot>/data/plugin-debug.log`
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

此外，runtime config 里还有一组现在已经正式可改的 planning 配置：

- `agents.main.planning.enabled`
- `agents.main.planning.mode`
- `agents.main.planning.systemPromptContract`

其中最关键的是：

- `agents.main.planning.systemPromptContract`
  - 这是给 LLM 的 planning prompt contract
  - 用户现在可以直接在 `task_system.json` 里修改它

当前可用版本默认约束是：

- 第一条 `[wd]` 由 runtime 负责
- 固定 30 秒进度消息由 runtime 负责
- fallback / recovery 文案由 runtime 负责
- 除这些固定控制面消息外，future-action planning 默认走 task-system tools

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
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/stable_acceptance.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
python3 scripts/runtime/plugin_install_drift.py --json
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

- [README.md](../README.md)
- [roadmap.md](./roadmap.md)
