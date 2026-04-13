[English](growware-pilot.md) | [中文](growware-pilot.zh-CN.md)

# Growware Pilot 接入草案

## 这是什么

这份文档描述的是：如何把 `openclaw-task-system` 接成 Growware 的 `Project 1`，并把 `feishu6-chat` 变成真实的人类反馈 / 审批 / 通知入口。

它不重写 OpenClaw，也不重写 task-system runtime。它只补一层项目本地控制面和安全接线。

## 当前默认值

- `Project 1 = openclaw-task-system`
- `A channel = feishu6-chat`
- `A roles = feedback + approval + notification`
- `Telegram = fallback candidate`
- 所有默认挂载 `openclaw-task-system` 的使用 channel 视为 `B` 面
- 项目级 durable 真相源落在仓库根目录的 [`.growware/`](../../../.growware/README.md)

## 落地结构

```text
feishu6-chat
  -> OpenClaw binding
  -> growware agent
  -> openclaw-task-system repo workspace
  -> Codex edits / tests / local deploy

task-system runtime
  -> plugin/runtime logs
  -> Growware judge / deploy gate
  -> feishu6 notification
```

## 项目内真相源

- [`.growware/project.json`](../../../.growware/project.json)
- [`.growware/channels.json`](../../../.growware/channels.json)
- [`.growware/contracts/feedback-event.v1.json`](../../../.growware/contracts/feedback-event.v1.json)
- [`.growware/contracts/incident-record.v1.json`](../../../.growware/contracts/incident-record.v1.json)
- [`.growware/policies/judge.v1.json`](../../../.growware/policies/judge.v1.json)
- [`.growware/policies/deploy-gate.v1.json`](../../../.growware/policies/deploy-gate.v1.json)
- [`.growware/ops/daemon-interface.v1.json`](../../../.growware/ops/daemon-interface.v1.json)

## 运维命令

预检：

```bash
python3 scripts/runtime/growware_preflight.py --json
```

预览 OpenClaw 绑定：

```bash
python3 scripts/runtime/growware_openclaw_binding.py --json
```

写入绑定并安全重启：

```bash
python3 scripts/runtime/growware_openclaw_binding.py --write --restart --json
```

本地 deploy：

```bash
python3 scripts/runtime/growware_local_deploy.py --json
```

## 当前边界

- `feishu6-chat` 的主动通知能力依赖 OpenClaw host delivery 和已有会话上下文
- `Telegram` 目前只保留为 fallback candidate，没有成为主通道
- deploy gate 仍默认需要人工审批，不直接假设生产自治
- 代码修改和 plugin 本地安装是自动化的，但仍先以本地 OpenClaw 环境为范围
