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


## P2 已完成的运维与可观测能力

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

### 4. 队列 / lane / continuity / taskmonitor 运维接口

当前状态：已完成

- 已支持：
  - `queues`
  - `lanes`
  - `continuity`
  - `taskmonitor`
- 已支持结构化输出：
  - `queues --json`
  - `lanes --json`
  - `continuity --json`
  - `taskmonitor --action status --json`
  - `taskmonitor --action list --json`
- `continuity` 已支持：
  - `--session-key`
  - `--resume-watchdog-blocked --limit N`
  - 分类输出：
    - `Auto-Resumable`
    - `Needs Manual Review`
    - `Not Recommended For Auto Resume`
    - `By Session`


## P3 下一步建议优先做

### 1. 短消息体感的真实验证与优化

当前状态：待继续真实验证

- 连续发 `在么`
- 重点确认：
  - `[wd]` 是否每条都快速返回
  - 正式回复后是否不再误发 30 秒 follow-up
  - 队列文案是否符合当前真实队列状态
- 现在逻辑已基本稳定，但体感速度和视觉时序还值得继续盯

### 2. 连续执行任务的持续执行闭环

当前状态：部分完成

- 当前已经具备：
  - 风险识别
  - 分类输出
  - 指定 session 过滤
  - watchdog blocked 任务限额恢复
  - watchdog blocked 任务按 session 精准恢复
  - 恢复结果附带 post-resume 状态摘要
  - 恢复结果附带每个 resumed session 的后续状态摘要
  - 恢复结果会区分哪些 resumed session 已经 settled、哪些仍需继续 follow-up
  - 恢复结果文本输出已支持按 `Needs Follow-up` / `Settled` 分组
  - 恢复结果文本输出已支持 `Follow-up Priorities`
  - `continuity --resume-watchdog-blocked --json` 已直接提供 `top_followup_session`
  - continuity / resume 结果附带推荐下一步命令
  - continuity / resume 结果附带当前建议执行方式
  - 可按当前建议执行方式收紧恢复范围
  - 真正恢复前可先 dry-run 预览
  - continuity 输出内置 execution_plan / runbook 视图
- 但还没有完全形成自动闭环：
  - 任务持续推进
  - 恢复后的后续收口
  - watchdog 与长任务续跑的完整策略

### 3. 并发执行策略与 lane 模型

当前状态：部分完成

- 当前已经能看到：
  - 当前有几个 queue
  - 当前有几个 lane
  - 哪些 task 在 running / queued / paused
  - 哪些 session 正在共享同一个 agent queue / lane
  - 为什么当前 queue / lane 被判断为 shared，以及是否已有 running lane
  - 当前更适合的执行建议：serial / serial-per-session / parallel-safe
- 但还没最终回答：
  - 是否要开放真正并发执行
  - OpenClaw 当前天然并发能力边界
  - lane 应如何影响叫号、恢复、持续执行

### 4. 预计时间进一步细化

当前状态：已做基础版，待细化

- 现在是保守估算
- 后续可继续按：
  - agent
  - session
  - 任务类型
  做更细粒度估算

## P4 未开始 / 方案阶段

### 1. 更产品化的开关与控制面板

当前状态：部分完成

- runtime 侧的 `/taskmonitor` 开关和运维命令已经完成
- 已新增统一状态入口：
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --compact`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --json`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --session-key '<session_key>'`
- 当前 dashboard 已能汇总：
  - `health`
  - `queues`
  - `lanes`
  - `continuity`
  - `taskmonitor`
- `dashboard --json` 已直接提供 `top_followup_session`
- 当前 dashboard 已支持按 `session` 聚焦，适合排某个具体会话
- 当前 dashboard 已支持 `--compact`，适合日常快速扫一眼
- 但更产品化的控制面板仍未完成，例如：
  - 面向普通使用者的开关与提示
  - 更低成本的日常管理界面
  - 更接近面板/小组件的交互入口


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
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues --json`
- 查看当前 lane 摘要：
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes --json`
- 查看或恢复 main 连续执行风险：
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key '<session_key>'`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --json`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --limit 1`
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --session-key '<session_key>' --limit 1`
- 查看或切换 taskmonitor：
  - `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action status`

是否可以通过 /tasks 展示当前队列任务？ 特别是长任务执行时，很有必要； 
