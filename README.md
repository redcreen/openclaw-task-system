# OpenClaw Task System

## 定位

这个目录是独立系统根目录。

后续与“OpenClaw 可配置任务管理系统”相关的工作，默认都在这里完成：

- 系统文档
- 设计方案
- 验证方案
- 使用说明
- 开发任务拆解
- 脚本实现
- OpenClaw 插件实现
- 测试代码
- 配置样例
- 本系统运行数据目录约定

除非明确需要接入 OpenClaw 主配置或主程序入口，否则不再继续把新工作散落到其他目录。

## 目标

本系统是一个全新的任务管理系统项目。

它负责长任务的完整生命周期管理：

- 任务创建
- 任务状态管理
- 用户可见进展回写
- 静默检测
- 通知兜底
- 终态收口
- 后续恢复与续跑

## 目录规划

### `docs/`

系统文档统一放这里，包括：

- 总体方案
- 验证方案
- 使用说明
- 开发任务拆解
- 后续设计文档

当前文件：

- `docs/SYSTEM_PLAN.md`
- `docs/VALIDATION_PLAN.md`
- `docs/USAGE_GUIDE.md`
- `docs/IMPLEMENTATION_TASKS.md`
- `docs/OPENCLAW_INTEGRATION_PLAN.md`
- `docs/PLUGIN_INSTALLATION.md`

### `scripts/`

系统脚本与运行时实现统一放这里。

当前已有：

- `scripts/runtime/`
  当前任务运行时实现目录，后续状态管理、静默检测、通知、发送、归档等能力都在这里继续发展

- `plugin/`
  OpenClaw 插件目录。后续宿主接入默认优先通过插件完成，而不是修改 OpenClaw 主程序

当前核心模块包括：

- `scripts/runtime/task_state.py`
- `scripts/runtime/task_config.py`
- `scripts/runtime/task_policy.py`
- `scripts/runtime/main_task_adapter.py`
- `scripts/runtime/openclaw_bridge.py`
- `scripts/runtime/openclaw_hooks.py`
- `scripts/runtime/task_status.py`
- `scripts/runtime/silence_monitor.py`
- `plugin/src/plugin/index.ts`

当前关键说明文档还包括：

- `docs/OPENCLAW_INTEGRATION_PLAN.md`
- `docs/OPENCLAW_INTEGRATION_EXAMPLE.md`

当前插件默认支持的长任务交互节奏是：

- 所有消息先立即回复“已收到，开始处理”
- 短任务如果超过设定时间还没返回，会自动补一条“仍在处理中”
- 长任务如果 30 秒内还没有新的阶段结果，watchdog 自动补一条“仍在处理中”
- 像“5分钟后回复我ok”这类延迟续跑任务，会先登记成计划任务，到点后再由 continuation runner 主动继续执行
- 有真实阶段结果时继续回写，直到最终收口

### `tests/`

本系统的自动化测试统一放这里。

当前阶段可以为空，但后续所有新增测试应尽量收敛到这里，避免继续散落。

### `config/`

本系统自己的配置样例、配置 schema、接入示例统一放这里。

后续可放：

- 配置示例 json
- schema 文档
- OpenClaw 接入样例

当前文件：

- `config/task_system.json`
- `config/task_system.example.json`
- `config/openclaw_plugin.example.json`

### `data/`

本系统运行时的数据目录约定。

后续正式实现时，任务状态、归档、outbox、发送中间态等都应优先归入这里。

## 工作约定

后续在这个系统里推进时，默认遵循以下规则：

1. 新文档优先写到 `docs/`
2. 新脚本优先写到 `scripts/`
3. 新测试优先写到 `tests/`
4. 新配置样例优先写到 `config/`
5. 新运行数据路径优先设计在 `data/`
6. OpenClaw 集成优先走 `plugin/`，避免修改 OpenClaw 主程序
7. 除非确有必要，不再把本系统的新逻辑写回其他旧目录

## 当前阶段

当前阶段仍是“系统定义优先”：

1. 把系统要做什么定义清楚
2. 把验证与验收方案定义清楚
3. 把使用方式和接入方式定义清楚
4. 把开发任务拆成可独立执行的小任务
5. 然后再进入正式实现

## 当前入口

如果要继续推进，建议优先阅读：

1. `docs/SYSTEM_PLAN.md`
2. `docs/VALIDATION_PLAN.md`
3. `docs/USAGE_GUIDE.md`
4. `docs/IMPLEMENTATION_TASKS.md`

## 当前可直接执行的命令

- 运行测试：
  `bash workspace/openclaw-task-system/scripts/run_tests.sh`

- 查看某个任务状态：
  `python3 workspace/openclaw-task-system/scripts/runtime/task_status.py <task_id>`

- 查看当前进行中的任务：
  `python3 workspace/openclaw-task-system/scripts/runtime/task_status.py --list`

- 查看系统健康总览：
  `python3 workspace/openclaw-task-system/scripts/runtime/health_report.py`

- OpenClaw 插件入口：
  `workspace/openclaw-task-system/plugin/index.ts`

- 插件安装自检：
  `python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py`

- 插件联调 smoke：
  `python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py`

- 运行完整 watchdog 周期：
  `python3 workspace/openclaw-task-system/scripts/runtime/watchdog_cycle.py`

- dry-run 发送指令执行器：
  `python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py`

- 真正执行可外发通道：
  `python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py --execute`

- 给执行结果显式标记上下文：
  `python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py --execute --execution-context host`

- 只跑 watchdog 产物生成，不做真实外发：
  `python3 workspace/openclaw-task-system/scripts/runtime/watchdog_cycle.py workspace/openclaw-task-system/config/task_system.json --no-execute`

- 让 watchdog 结果显式标记为宿主实发：
  `python3 workspace/openclaw-task-system/scripts/runtime/watchdog_cycle.py workspace/openclaw-task-system/config/task_system.json --execution-context host`

- 生成一条测试外发指令：
  `python3 workspace/openclaw-task-system/scripts/runtime/enqueue_test_instruction.py --channel telegram --chat-id @example --message "task system test"`

- 运行 `main` 第一阶段总验收：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_acceptance.py`

- 运行稳定使用总验收：
  `python3 workspace/openclaw-task-system/scripts/runtime/stable_acceptance.py`

- `main` 运维入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py list`

- 统一状态总览：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --compact`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --only-issues`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --json`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --session-key '<session_key>'`
  会把 `health / queues / lanes / continuity / taskmonitor` 收成一个统一入口
  `dashboard --json` 也会直接给出 `top_followup_session`，方便快速定位当前最该优先跟进的 session
  `dashboard` / `dashboard --compact` / `dashboard --json` 现在也会附带 `action_hint`，直接提示下一步更推荐先看什么
  `action_hint_command` 会直接给出首选命令，并排在 `suggested_next_commands` 的第一位
  `dashboard` 也会附带统一结构的 `primary_action`
  `dashboard` / `continuity` / `resume result` 也会直接给出顶层 `primary_action_kind / primary_action_command`
  `dashboard` / `continuity` / `resume result` 也会直接给出顶层 `runbook_status`
  `dashboard` / `continuity` / `resume result` 也会直接给出顶层 `requires_action`
  `dashboard` / `continuity` / `resume result` 也会直接给出顶层 `focus_session_key`
  `dashboard --only-issues --json` 的 `issue_summary` 现在也会给出同样的顶层别名字段
  `dashboard --json` 还会附带 `runbook`，把首选动作和后续命令收成一组可直接消费的步骤
  文本版 `dashboard` 现在也会渲染 `Runbook` 段落
  `dashboard --only-issues` 会只保留非 OK 项，更适合日常巡检

- 当前队列拓扑：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues --json`
  输出会显式标出当前哪些 session 正在共享同一个 agent queue
  并会解释为什么当前 queue 被判断为 `shared` / `single-session`
  同时会给出当前更适合的执行建议：`serial` / `serial-per-session` / `parallel-safe`

- 当前 lane 摘要：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes --json`
  输出会显式标出当前 lane 是 `shared` 还是 `single-session`
  并会标出当前共享 lane 中是否已经存在 running lane
  同时会给出当前更适合的执行建议：`serial` / `serial-per-session` / `parallel-safe`

- 当前持续执行 / watchdog 风险摘要：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key '<session_key>'`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --json`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --session-key '<session_key>' --limit 1`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --respect-execution-advice`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --dry-run`
  文本输出会把恢复结果按 `Needs Follow-up` / `Settled` 分组显示
  文本输出会额外给出 `Follow-up Priorities`，帮助先盯最值得关注的 session
  恢复结果会附带 `post_resume_summary`，用于快速确认恢复后任务是否已进入 `running/queued/...`
  `post_resume_summary.sessions` 会继续给出每个恢复 session 的后续状态摘要，减少恢复后再手动追查一轮
  `post_resume_summary` 还会标出哪些恢复 session 已经 `settled`、哪些仍然 `needs-followup`
  `post_resume_summary.closure_state` 会直接标出本次恢复整体是否已收口：`no-resume-targets / settled / needs-followup`
  恢复结果顶层和 `post_resume_summary` 也会直接给出布尔值 `closure_complete`
  恢复结果顶层也会直接给出 `closure_state / closure_hint`，方便脚本和面板直接消费
  `post_resume_summary` 也会直接给出 `closure_hint / closure_hint_command`，提示恢复后下一步最推荐先做什么
  恢复结果顶层和 `post_resume_summary` 都会附带统一结构的 `primary_action`
  恢复结果顶层和 `post_resume_summary.runbook` 都会把恢复后的首选动作和后续命令收成一组可直接消费的步骤
  如果恢复后仍需继续 follow-up，恢复结果还会直接附带 `next_followup_summary`
  这样恢复后就不必立刻再跑第二条 continuity 命令才能看到该 session 的风险快照
  文本版 `continuity --resume-watchdog-blocked` 也会渲染 `Runbook` 段落
  每个 resumed session 还会带 `followup_state_reason`，直接说明为什么当前被判成 settled 或 needs-followup
  `post_resume_summary.top_followup_session` 会直接给出当前最值得优先跟进的 session，方便脚本和面板直接消费
  `continuity` / `continuity --json` 也会直接给出 `top_risk_session`，方便先从风险最高的 session 开始排
  `continuity` / `continuity --json` 同样会附带统一结构的 `primary_action`
  `continuity` / `continuity --json` 现在也会附带 `runbook`
  `continuity --json` 现在也会直接给出 `auto_resume_ready / auto_resume_mode / auto_resume_preview_command / auto_resume_apply_command`
  当存在 auto-resumable 任务时，`continuity` 的默认 `primary_action` 会优先指向 `preview-auto-resume`
  当不存在额外 blocker 时，`continuity` 的默认 `primary_action` 会进一步升级成 `apply-auto-resume`
  `continuity --auto-resume-if-safe` 现在会在 `safe_to_apply=true` 时直接执行自动恢复，否则返回受保护的 `noop / skipped` 结果
  `dashboard` 在 continuity 风险场景下也会继承这条 `primary_action`，优先指向 guarded auto-resume 入口
  文本输出和 JSON 输出都会附带推荐的下一步命令，方便继续检查对应 session 的连续执行状态
  同时会直接给出当前建议执行方式：`serial` / `serial-per-session` / `parallel-safe`
  并会附带一份 `execution_plan`，把 dry-run、尊重 advice、后续检查命令收成一份更像 runbook 的输出
  输出会分成：
  - `Auto-Resumable`
  - `Needs Manual Review`
  - `Not Recommended For Auto Resume`
  - `By Session`

- 恢复 watchdog 卡住的主任务：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --limit 1`

- `main` 健康检查：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py health`

- 查看或切换某个会话的 taskmonitor：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action status`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action status --json`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action off`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --action list`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --action list --json`

- 健康问题统一修复入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py repair`

- 当前问题分诊入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py triage`

- 陈旧 blocked 任务批处理入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py sweep`

- 失败指令收口入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py resolve-failures`

- 外发故障诊断入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py diagnose-delivery`

## 下一步建议

下一阶段建议直接在这个目录内继续推进：

1. 继续增强 `scripts/runtime/` 作为宿主无关核心
2. 继续增强 `plugin/` 作为 OpenClaw 插件接入层
3. 保持插件接入优先，不回退到修改 OpenClaw 主程序

从这一刻开始，这里应当被视为这个系统的唯一主工作区。
