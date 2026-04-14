[English](usage_guide.md) | [中文](usage_guide.zh-CN.md)

# 使用指南

这份文档只回答两类问题：

- 装好之后，日常怎么用
- 出问题时，最常用的命令入口是什么

项目范围与已交付状态统一看：

- [../README.zh-CN.md](../README.zh-CN.md)
- [roadmap.zh-CN.md](roadmap.zh-CN.md)

## 日常运行模型

当前系统的标准节奏是：

1. 用户消息进入 task-system 管理范围
2. runtime 登记或复用 task
3. runtime 返回首条 `[wd]`
4. 底层 agent 执行继续推进
5. runtime 视情况发送进展、follow-up 或 recovery 控制面消息
6. 最终以 `done / failed / blocked / paused` 等受控终态收口

这套模型现在覆盖：

- 普通长任务
- delayed reply / continuation
- same-session routing
- watchdog / continuity 恢复
- future-first planning contract

## 运维命令

### 健康与总览

```bash
python3 scripts/runtime/main_ops.py health
python3 scripts/runtime/main_ops.py dashboard
python3 scripts/runtime/main_ops.py dashboard --compact
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/main_ops.py dashboard --only-issues
python3 scripts/runtime/main_ops.py triage
python3 scripts/runtime/main_ops.py triage --compact
python3 scripts/runtime/main_ops.py triage --json
python3 scripts/runtime/openclaw_runtime_audit.py
python3 scripts/runtime/openclaw_runtime_audit.py --json
python3 scripts/runtime/openclaw_runtime_audit.py --lookback-hours 48 --recent-limit 20
```

当你需要基于 `~/.openclaw` 里的真实运行数据做宿主侧体检，而不是看仓库内 testcase 时，用 `openclaw_runtime_audit.py`。它会同时给出：

- 运维视角：最近 task runs、失败投递、cron 错误、配置健康
- 用户视角：最近用户请求与终态回复摘要
- 可执行的修复建议：卡死 running task、失败投递残留、cron 投递异常

### 队列与 Lane

```bash
python3 scripts/runtime/main_ops.py queues
python3 scripts/runtime/main_ops.py queues --json
python3 scripts/runtime/main_ops.py lanes
python3 scripts/runtime/main_ops.py lanes --json
```

### Continuity 与恢复

```bash
python3 scripts/runtime/main_ops.py continuity
python3 scripts/runtime/main_ops.py continuity --compact
python3 scripts/runtime/main_ops.py continuity --only-issues
python3 scripts/runtime/main_ops.py continuity --json
python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe --dry-run --json
python3 scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --dry-run
```

日常值守时优先用这两个快照参数：

- `--compact` 用于快速扫一眼当前值守状态
- `--only-issues` 只保留 continuity 里真正需要动作的项

### Planning 与 Phase 6 运维

```bash
python3 scripts/runtime/runtime_mirror.py --check
python3 scripts/runtime/main_ops.py planning
python3 scripts/runtime/main_ops.py planning --json
python3 scripts/runtime/planning_acceptance.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
python3 scripts/runtime/planning_acceptance_suite.py --dry-run --json
python3 scripts/runtime/run_planning_acceptance_bundle.py --dry-run --json
python3 scripts/runtime/main_ops.py plugin-install-drift --json
```

如果你想先演练 planning 证据工作流，而不把 record 或 artifacts 真写回仓库 `docs/` 目录，就用这些 `--dry-run` 入口。

如果完整 dry-run bundle 全绿，而且当前改动触达 planning/runtime contract、release-facing acceptance 覆盖或 evidence workflow 本身，就继续执行：

```bash
python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date YYYY-MM-DD
```

验收与历史记录入口：

- [planning_acceptance_runbook.zh-CN.md](planning_acceptance_runbook.zh-CN.md)
- [planning_acceptance_record_template.zh-CN.md](planning_acceptance_record_template.zh-CN.md)
- [archive/planning_acceptance_record_2026-04-09.zh-CN.md](archive/planning_acceptance_record_2026-04-09.zh-CN.md)

### Same-Session Routing

```bash
python3 scripts/runtime/same_session_routing_acceptance.py --json
python3 scripts/runtime/stable_acceptance.py --json
```

### Task 查询与控制

```bash
python3 scripts/runtime/task_cli.py tasks
python3 scripts/runtime/task_cli.py task <task_id>
python3 scripts/runtime/task_cli.py session '<session_key>'
python3 scripts/runtime/main_ops.py list
python3 scripts/runtime/main_ops.py show <task_id>
python3 scripts/runtime/main_ops.py cancel --task-id <task_id>
python3 scripts/runtime/main_ops.py stop
python3 scripts/runtime/main_ops.py stop-all
python3 scripts/runtime/main_ops.py purge --session-key '<session_key>'
```

## 验证快捷入口

完整自动化回归：

```bash
bash scripts/run_tests.sh
```

稳定验收：

```bash
python3 scripts/runtime/stable_acceptance.py --json
```

更宽的发布门禁：

```bash
python3 scripts/runtime/release_gate.py --json
```

`release_gate.py` 会把基础 testsuite、operator acceptance、stable acceptance、runtime mirror 和 install drift 检查收口成一份结构化结果，避免继续靠手工串命令。
