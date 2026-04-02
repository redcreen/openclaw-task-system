# delivery_integration_notes.md / 投递集成说明

## Goal / 目标

Describe the final path from task-system notification event to real chat delivery.

描述从任务系统通知事件到真实聊天投递的最终路径。

## Desired flow / 目标流程

1. task becomes overdue
2. silence monitor marks task notified
3. event is written into outbox
4. outbox is consumed into sent
5. delivery payload is prepared
6. host delivery hook sends message into the correct conversation
7. delivery result is persisted

## Integration preference / 接入偏好

- reuse proven host reply delivery path where possible
- avoid duplicating transport logic in runtime scripts
- keep runtime layer transport-agnostic as much as possible

## First practical target / 第一阶段实际目标

Hook the prepared delivery payload into OpenClaw's existing reply or message delivery path without redesigning the whole host transport layer.
