# delivery_bridge_plan.md / 投递桥接规划

## Goal / 目标

Provide a real delivery bridge that can send task-system notifications into the correct OpenClaw conversation.

提供一个真实可用的投递桥接层，把任务系统产生的通知发送到正确的 OpenClaw 会话。

## Required inputs / 必要输入

- `session_key`
- `channel`
- `chat_id`
- `message`

## Preferred delivery order / 首选投递顺序

1. session-aware delivery keyed by `session_key`
2. fallback to `channel + chat_id`

## Required guarantees / 必须满足

- no cross-talk
- delivery result is persisted
- failed delivery is observable
- message wording remains conservative and truthful

- 不串话
- 有发送结果记录
- 发送失败可观测
- 消息文案保持保守真实

## Current first-phase rule / 第一阶段规则

- first version should prefer the same proven path already used by OpenClaw reply delivery
- do not invent a second parallel message stack if the host already has one

- 第一版优先复用 OpenClaw 已经验证可用的回复投递路径
- 不要额外再造一套平行消息栈
