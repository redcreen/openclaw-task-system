# OpenClaw Task System Todo

> 最后整理：2026-04-04
> 说明：本文件只保留当前有效问题、结论和后续工作，避免历史测试噪音继续污染判断。

## P1 已解决

### 1. Delayed Reply / Continuation 主链路

- `5分钟后回复我ok`
  已修复：不再出现“提醒一次后就不继续”的情况。
- 连续发：
  - `1分钟后回复我ok1`
  - `1分钟后回复我ok2`
  - `1分钟后回复我ok3`
  已修复：现在会创建独立 continuation，不再复用旧任务。
- continuation 到点后
  已修复：直接送达最终回复，并在成功后完成任务收口。

### 2. 短任务回执 / `[wd]`

- 已接入统一前缀 `[wd]`
- 已修复短任务即时回执按 task 粒度发送，不再互相覆盖
- 已修复“正式结果已经发出后，又补一条 `当前仍在处理中`”的主要误发问题

### 3. Agent 与 Task System 混乱回复

- `ok1` 有时 agent 自己发回来，有时又不会
- 处理方向：不能代替 agent 回复信息，避免混乱
- 当前状态：已解决

### 4. ChatGPT Auth Profile 混用

- 现象：日志出现 `You have hit your ChatGPT usage limit (plus plan)`，但当前应走 Pro
- 原因：`main` agent 下同时存在 Plus 和 Pro 两个 `openai-codex` profile
- 已处理：`main` 已收紧为仅使用 `openai-codex:67560691@qq.com`
- 当前状态：新的 smoke test 未再出现 `plus plan` / `rate_limit` / `rotate_profile`


## P1 待真实验证

### 1. 连续延迟回复

当前状态：已通过真实验证

- `1分钟后回复我111`
- `2分钟后回复我222`
- `3分钟后回复我333`

当前代码与回归测试状态：

- 注册为独立 continuation：通过
- 逐条到期顺序 `111 -> 222 -> 333`：通过
- 同时到期排序稳定性：已补回归并通过

### 2. 短消息体感

待继续真实验证：

- 连续发 `在么`

重点确认：

- `[wd]` 是否每条都快速返回
- 正式回复后是否不再误发 30 秒 follow-up
- 队列文案是否符合当前真实队列状态


## P2 下一步建议优先做

### 1. 取消队列中的任务

当前状态：已完成

- 已支持按 `task_id` 取消排队任务
- 已支持按 `queue_position` 取消 `main` 队列中的排队任务
- 命令：`python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py cancel ...`

### 2. 预期时间 / 预计回复时间

当前状态：已完成

- 已根据最近已完成任务的真实耗时估算 `estimated_wait_seconds`
- 已接入 `[wd]` 即时回执和 follow-up 文案
- 当前为保守估算，后续可继续按 agent/session 做细化

### 3. 30 秒提醒附带原因

当前状态：已完成

- 队列中：会提示前面还有几个号，以及预计等待时间
- 运行中：优先带最近一次真实进展 `last_progress_note`
- 无进展笔记时：退回到预计秒数 / 分钟数


## P3 未开始 / 方案阶段

### 1. 连续执行任务的持续执行机制

当前状态：部分完成

已新增：

- `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity`
- `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --limit 1`

当前可以直接看到：

- `main` 当前是否存在连续执行风险
- watchdog 正在监控的超时任务数量
- 是否已经出现 `watchdog_blocked_task`
- 哪些任务可优先 `resume`
- 也可以直接按限额恢复 watchdog 拦住的主任务
- continuity 输出已按三类区分：
  - `Auto-Resumable`
  - `Needs Manual Review`
  - `Not Recommended For Auto Resume`
- 也已按 `session` 聚合，便于直接看问题集中在哪几个会话
- 已支持 `--session-key` 过滤，可只看某个具体会话的 continuity 状态

原问题：

- 任务看起来开始了
- 但没有持续推进机制
- 当前虽有监控，但还不是完整的执行闭环

这部分需要单独设计：

- 任务持续推进
- 任务恢复
- 长任务收口
- 与 watchdog 的关系

### 2. 并发执行与 lane 感知

当前状态：部分完成

- 已新增 `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes`
- 已新增 `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues`
- 可以查看当前各 agent 的：
  - active_task_count
  - running_task_count
  - queued_task_count
  - paused_task_count
  - session_lane_count
  - running_lane_count
- 也会列出当前 running task 和 queued head，方便判断“前面是什么任务”
- `queues` 会直接展示当前有几个 agent 队列、每个队列下有哪些 session，便于解释“为什么前面有几个号”
- 已收紧 due continuation claim 规则：同一 session lane 一次最多 claim 1 条，避免多条到期任务同时变成 `running`
- 已补回归：前一条 continuation 完成后，下一轮 poll 会自动 claim 同 session 的下一条 continuation

仍待回答的问题：

- 能否改成并发执行
- OpenClaw 当前是否本身已并发
- 系统是否能感知当前并发 lane
- 当前实际有几个队列

### 3. 临时关闭功能 / `/taskmonitor`

当前状态：已完成

- 已支持：
  - `/taskmonitor`
  - `/taskmonitor status`
  - `/taskmonitor on`
  - `/taskmonitor off`
- 当前为按 session 粒度持久化开关
- 关闭后，该会话后续消息将跳过 task system 监控
- 已新增运维命令：
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action status`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action off`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --action list`
- runtime 命令级验证已通过


## 未单独处理的历史问题

### Telegram slash 解析失败

历史异常：

- `Telegram recipient @slash could not be resolved to a numeric chat ID`

当前状态：已处理

- `telegram:slash:*` 这类虚拟 recipient 不再尝试发送即时回执 / follow-up
- 插件现在会记录 `immediate-ack:skipped`
- 已避免再次触发 `chat not found`


## 历史样例保留

### 队列体感异常样例

- `在么？`
- `已收到，当前有 1 条任务正在处理；你的请求已进入队列，前面还有 1 个号，你现在排第 2 位。`
- `在。`
- `在么？`
- `已收到，当前有 1 条任务正在处理；你的请求已进入队列，前面还有 5 个号，你现在排第 6 位。`
- `在。`
- `在么？`
- `已收到，当前有 1 条任务正在处理；你的请求已进入队列，前面还有 9 个号，你现在排第 10 位。`
- `在么？`

问题记录：

- 如果前面有任务，为什么很快又执行了？
- 前面的任务具体是什么？

### Telegram slash 样例

- `23:39:26+08:00 [plugins] [task-system] immediate-ack failed for telegram:slash:8705812936: Telegram recipient @slash could not be resolved to a numeric chat ID (Call to 'getChat' failed! (400: Bad Request: chat not found))`
- `23:39:33+08:00 [telegram] sendMessage ok chat=8705812936 message=229`
- `23:39:35+08:00 [plugins] [task-system] immediate-ack failed for telegram:slash:8705812936: Telegram recipient @slash could not be resolved to a numeric chat ID (Call to 'getChat' failed! (400: Bad Request: chat not found))`
- `23:39:40+08:00 [hooks/session-memory] Session context saved to ~/.openclaw/workspace/memory/2026-04-02-session-greeting.md`
- `23:40:05+08:00 [telegram] sendMessage ok chat=8705812936 message=231`
- `23:40:07+08:00 [plugins] [task-system] immediate-ack failed for telegram:slash:8705812936: Telegram recipient @slash could not be resolved to a numeric chat ID (Call to 'getChat' failed! (400: Bad Request: chat not found))`


## 排障命令备忘

- 查看 `main` 当前 auth order：
  - `openclaw models auth order get --agent main --provider openai-codex`
- 清理测试残留：
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py purge --session-key '<session_key>'`
- 查看当前队列拓扑：
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues`
- 查看当前 lane 摘要：
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes`
- 查看或恢复 main 连续执行风险：
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key '<session_key>'`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --limit 1`
- 查看或切换 taskmonitor：
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action status`
