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

- 当前队列拓扑：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues`

- 当前 lane 摘要：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes`

- 当前持续执行 / watchdog 风险摘要：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity`

- `main` 健康检查：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py health`

- 查看或切换某个会话的 taskmonitor：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action status`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action off`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --action list`

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
