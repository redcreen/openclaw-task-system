# delivery_bridge_real_spec.md / 真实投递桥接规范

## Goal / 目标

Replace placeholder delivery with a real OpenClaw-integrated delivery action.

把占位式投递替换为真正接入 OpenClaw 的消息投递动作。

## Required behavior / 必要行为

- route by `session_key` first when available
- fallback to `channel + chat_id` only when session-aware route is unavailable
- record delivery outcome
- keep retry / resend policy outside the delivery primitive itself

- 优先按 `session_key` 投递
- 仅在 session-aware 路径不可用时退回 `channel + chat_id`
- 记录发送结果
- 重试策略不要直接耦合在底层投递原语里

## Current blocker / 当前阻塞点

The runtime scripts are ready, but the final OpenClaw host delivery hook is not wired yet.

当前运行时脚本层已具备准备条件，但最终 OpenClaw 宿主的真实投递钩子还没有接上。
