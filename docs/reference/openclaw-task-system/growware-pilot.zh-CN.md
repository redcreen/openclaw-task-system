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
- [`.growware/ops/daemon-interface.v1.json`](../../../.growware/ops/daemon-interface.v1.json)
- [`docs/policy/README.zh-CN.md`](../../../docs/policy/README.zh-CN.md)
- [`.policy/manifest.json`](../../../.policy/manifest.json)
- [`.policy/index.json`](../../../.policy/index.json)
- [`.policy/rules/growware.feedback-intake.same-session.v1.json`](../../../.policy/rules/growware.feedback-intake.same-session.v1.json)
- [`.policy/rules/growware.project.local-deploy.v1.json`](../../../.policy/rules/growware.project.local-deploy.v1.json)

当前合同是分层的：

- `docs/policy/*.md`：给人 review 的 policy source
- `.policy/`：Growware runtime 应优先消费的编译后机器执行层
- `.growware/contracts/` 和 `.growware/ops/`：项目本地控制面与可执行 wiring
- 旧的 `.growware/policies/*.json` 已在 Milestone 2 完成后退役，不再属于 live control surface

## 当前已落地的 Growware baseline

- `growware` agent 的 same-session classifier 已由编译后的 `.policy/rules/growware.feedback-intake.same-session.v1.json` 驱动
- `feishu6-chat` 上的自然语言反馈，默认先进入 daemon-owned intake，再决定是并入当前任务还是排成新任务
- Growware close-out 现在要求显式标记执行来源：`daemon-owned` 或 `terminal-takeover`
- 对 `growware` agent 而言，完成态会额外通过 control-plane lane 回到 `feishu6`，不再只依赖正文输出
- 运行时 intake 与 deploy 验证现在只读取编译后的 `.policy/`

## Session Hygiene

- `feishu6-chat` 是生产反馈入口，不允许长期复用被 `terminal-takeover` 污染过的 transcript
- 如果 `growware` 的直连 session 已经混入人工调试上下文，先轮换 session，再继续收真实反馈
- 轮换会同时保留旧 transcript 归档、生成新的 session id，并可顺手把卡住任务按可解释原因失败归档

检查当前生产 session：

```bash
python3 scripts/runtime/growware_session_hygiene.py \
  --session-key 'agent:growware:feishu:direct:ou_6bead7a2b071454aeed7239e9de15d62' \
  --json
```

轮换生产 session，并把卡住任务归档失败：

```bash
python3 scripts/runtime/growware_session_hygiene.py \
  --session-key 'agent:growware:feishu:direct:ou_6bead7a2b071454aeed7239e9de15d62' \
  --fail-task-id task_487d4937033a4a2da97d6044e1b53af2 \
  --failure-reason session-polluted-by-terminal-takeover \
  --reset \
  --restart \
  --json
```

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
- 运行时 intake 与 deploy 验证应读取编译后的 `.policy/`，而不是直接依赖 prose 文档或旧的 policy JSON
