# Runtime implementation notes / Runtime 实现说明

## Current runtime pieces / 当前运行时组成
- task_state.py: task lifecycle state store / 任务生命周期状态存储
- silence_monitor.py: overdue scan + notify state marking + outbox emit / 超时扫描 + 已通知状态回写 + outbox 事件产出
- notify.py: notify payload builder + mark_notified / 通知 payload 构造 + 已通知标记
- send_instruction.py: route-aware send instruction builder / 基于路由信息的发送指令构造
- emit_task_event.py: write overdue event into outbox / 把超时事件写入 outbox
- consume_outbox.py: consume outbox and archive sent records / 消费 outbox 并归档 sent 记录
- instruction_executor.py: execute or dry-run send instructions / 执行或 dry-run 发送指令

## Planned next step / 下一步
- connect outbox consumer to a real delivery path / 把 outbox consumer 接到真实发送路径
- validate end-to-end on a safe target session / 在安全目标会话上做端到端验证

## Candidate delivery paths / 候选发送路径
1. sessions_send(sessionKey, message)
2. message(action=send, channel, target/chat)
3. openclaw agent --session-id/--to --deliver

## Current preference / 当前偏好
- use session-aware delivery keyed by task session/chat metadata / 优先使用基于 task session/chat 元数据的会话感知发送
- keep first version conservative and explicit / 第一版保持保守、明确，不做花哨推断
