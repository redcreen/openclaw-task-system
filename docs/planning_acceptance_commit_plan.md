[English](planning_acceptance_commit_plan.md) | [中文](planning_acceptance_commit_plan.zh-CN.md)

# Planning Acceptance Commit Plan

本文件用于把当前这轮 worktree 改动整理成更容易 review 的提交批次。

## 建议拆分

当前 worktree 除了 planning acceptance / install drift，还包含一整轮 `task_user_content` 废弃与历史审计工具，以及一次 continuity 清理动作，建议按 5 组拆开。

### 1. Phase 6 runtime closure

建议包含：

- `scripts/runtime/task_status.py`
- `scripts/runtime/health_report.py`
- `scripts/runtime/main_ops.py`
- `scripts/runtime/openclaw_hooks.py`
- `scripts/runtime/stable_acceptance.py`
- `tests/test_task_status.py`
- `tests/test_health_report.py`
- `tests/test_main_ops.py`
- `tests/test_openclaw_hooks.py`
- `tests/test_stable_acceptance.py`

同步包含 installable payload：

- `plugin/scripts/runtime/task_status.py`
- `plugin/scripts/runtime/health_report.py`
- `plugin/scripts/runtime/main_ops.py`
- `plugin/scripts/runtime/openclaw_hooks.py`
- `plugin/scripts/runtime/stable_acceptance.py`

目标：

- 让 runtime 真正认识 planning truth source / anomaly / ops projection
- 让 stable acceptance 把 planning-acceptance 纳入总闭环

### 2. Install drift and local install observability

建议包含：

- `scripts/runtime/plugin_install_drift.py`
- `scripts/runtime/plugin_doctor.py`
- `scripts/runtime/health_report.py`
- `scripts/runtime/main_ops.py`
- `tests/test_plugin_install_drift.py`
- `tests/test_plugin_doctor.py`
- `tests/test_health_report.py`
- `tests/test_main_ops.py`

同步包含 installable payload：

- `plugin/scripts/runtime/plugin_install_drift.py`
- `plugin/scripts/runtime/plugin_doctor.py`
- `plugin/scripts/runtime/health_report.py`
- `plugin/scripts/runtime/main_ops.py`

文档可一并归到这一组或放到 docs 组，至少包括：

- `docs/plugin_installation.md`
- `docs/local_install_validation_2026-04-09.md`
- `plugin/readme.md`

目标：

- 把 installable payload 与本地安装态 runtime 的漂移变成正式 truth source
- 让 `dashboard / dashboard --only-issues / triage / plugin-install-drift` 都能直接投影 drift
- 让本地安装被 dangerous-code 检测阻塞这件事有正式运维入口和记录

### 3. Planning acceptance toolchain

建议包含：

- `scripts/runtime/planning_acceptance.py`
- `scripts/runtime/create_planning_acceptance_record.py`
- `scripts/runtime/prepare_planning_acceptance.py`
- `scripts/runtime/capture_planning_acceptance_artifacts.py`
- `scripts/runtime/run_planning_acceptance_bundle.py`
- `tests/test_planning_acceptance.py`
- `tests/test_create_planning_acceptance_record.py`
- `tests/test_prepare_planning_acceptance.py`
- `tests/test_capture_planning_acceptance_artifacts.py`
- `tests/test_run_planning_acceptance_bundle.py`

同步包含 installable payload：

- `plugin/scripts/runtime/planning_acceptance.py`
- `plugin/scripts/runtime/create_planning_acceptance_record.py`
- `plugin/scripts/runtime/prepare_planning_acceptance.py`
- `plugin/scripts/runtime/capture_planning_acceptance_artifacts.py`
- `plugin/scripts/runtime/run_planning_acceptance_bundle.py`

目标：

- 把 planning 验收从单个脚本扩成可记录、可准备、可抓输出、可汇总的一套 helper

### 4. `task_user_content` removal and history audit tooling

建议包含：

- `plugin/src/plugin/index.ts`
- `plugin/tests/tool-planning-flow.test.mjs`
- `scripts/runtime/openclaw_hooks.py`
- `scripts/runtime/check_task_user_content_leaks.py`
- `scripts/runtime/scrub_task_user_content_history.py`
- `tests/test_openclaw_hooks.py`
- `tests/test_task_planning_tools.py`
- `tests/test_check_task_user_content_leaks.py`
- `tests/test_scrub_task_user_content_history.py`
- `docs/task_user_content_decision.md`

目标：

- 让 `task_user_content` 正式退出运行时主协议
- 只保留历史泄漏审计 / 历史清理工具
- 提供 `--since` 作为重启后新链路验证方式

### 5. Docs and handoff

建议包含：

- `README.md`
- `docs/testsuite.md`
- `docs/usage_guide.md`
- `docs/planning_acceptance_runbook.md`
- `docs/planning_acceptance_record_template.md`
- `docs/planning_acceptance_record_2026-04-09.md`
- `docs/planning_acceptance_handoff.md`
- `docs/planning_acceptance_commit_plan.md`
- `docs/task_user_content_decision.md`
- `plugin/readme.md`

如果这轮也改了 roadmap / todo，可视情况放进这一组：

- `docs/roadmap.md`
- `docs/todo.md`

目标：

- 让下一位维护者能看懂怎么跑、怎么记、怎么交接、怎么拆提交
- 明确 continuity 清理已完成，当前剩余运维告警只剩 install drift

## 建议顺序

1. 先提交 runtime closure
2. 再提交 install drift / local install observability
3. 再提交 planning acceptance toolchain
4. 再提交 `task_user_content` removal / history audit tooling
5. 最后提交 docs / handoff / commit plan

## 提交前检查

每组提交前至少跑：

```bash
python3 -m unittest discover -s tests -p 'test_main_ops.py' -v
python3 scripts/runtime/main_ops.py dashboard --only-issues
python3 scripts/runtime/main_ops.py triage --json
python3 scripts/runtime/main_ops.py plugin-install-drift --json
python3 -m unittest discover -s tests -p 'test_*planning_acceptance*.py' -v
python3 scripts/runtime/planning_acceptance.py --json
python3 scripts/runtime/stable_acceptance.py --json
python3 scripts/runtime/check_task_user_content_leaks.py --since 2026-04-11T12:18:34+08:00 --json
python3 -m unittest discover -s tests -p 'test_check_task_user_content_leaks.py' -v
python3 -m unittest discover -s tests -p 'test_scrub_task_user_content_history.py' -v
python3 scripts/runtime/main_ops.py continuity --json
python3 scripts/runtime/main_ops.py lanes --json
```

如果是最终合并前，建议再跑：

```bash
bash scripts/run_tests.sh
```
