[English](cleanup_commit_plan.md) | [中文](cleanup_commit_plan.zh-CN.md)

# Cleanup Commit Plan

> 更新日期：2026-04-11
> 目的：把当前 dirty worktree 拆成可 review、可提交、可继续整改的边界。

## 1. 先不要提交的内容

这些内容更像运行产物、临时记录或明显杂项，不建议混进主提交：

- `docs/artifacts/planning_acceptance_2026-04-11/*`
- `t1`

这些内容是否提交，需要你明确决定：

- `docs/planning_acceptance_record_2026-04-09.md`
- `docs/planning_acceptance_record_2026-04-11.md`

建议保留并提交：

- `docs/artifacts/.gitignore`

## 2. 推荐提交顺序

### Commit 1. Planning Acceptance / Install Drift Tooling

目标：

- 收口 `Phase 6` 的 planning acceptance 工具链
- 收口 install drift observability / doctor / stable acceptance

建议包含：

- `scripts/runtime/capture_planning_acceptance_artifacts.py`
- `scripts/runtime/create_planning_acceptance_record.py`
- `scripts/runtime/planning_acceptance.py`
- `scripts/runtime/planning_acceptance_suite.py`
- `scripts/runtime/plugin_install_drift.py`
- `scripts/runtime/prepare_planning_acceptance.py`
- `scripts/runtime/run_planning_acceptance_bundle.py`
- `scripts/runtime/plugin_doctor.py`
- `scripts/runtime/stable_acceptance.py`
- `scripts/runtime/health_report.py`
- `scripts/runtime/main_ops.py`
- `plugin/scripts/runtime/` 下对应镜像文件
- `tests/test_capture_planning_acceptance_artifacts.py`
- `tests/test_create_planning_acceptance_record.py`
- `tests/test_planning_acceptance.py`
- `tests/test_planning_acceptance_suite.py`
- `tests/test_plugin_doctor.py`
- `tests/test_plugin_install_drift.py`
- `tests/test_prepare_planning_acceptance.py`
- `tests/test_run_planning_acceptance_bundle.py`
- `tests/test_health_report.py`
- `tests/test_main_ops.py`
- `tests/test_stable_acceptance.py`
- `docs/plugin_installation.md`
- `docs/local_install_validation_2026-04-09.md`
- `docs/planning_acceptance_commit_plan.md`
- `docs/planning_acceptance_handoff.md`
- `docs/planning_acceptance_record_template.md`
- `docs/planning_acceptance_runbook.md`
- `docs/testsuite.md`
- `docs/usage_guide.md`
- `docs/artifacts/.gitignore`

### Commit 2. `task_user_content` 废弃与历史审计

目标：

- 彻底把 `task_user_content` 从主链路降级为历史问题
- 保留 leak audit / scrub tooling
- 统一 mode-first contract

建议包含：

- `scripts/runtime/check_task_user_content_leaks.py`
- `scripts/runtime/scrub_task_user_content_history.py`
- `scripts/runtime/task_config.py`
- `plugin/scripts/runtime/check_task_user_content_leaks.py`
- `plugin/scripts/runtime/task_config.py`
- `plugin/src/plugin/index.ts`
- `plugin/tests/tool-planning-flow.test.mjs`
- `tests/test_check_task_user_content_leaks.py`
- `tests/test_scrub_task_user_content_history.py`
- `tests/test_task_config.py`
- `tests/test_task_planning_tools.py`
- `config/task_system.json`
- `config/task_system.example.json`
- `plugin/config/task_system.json`
- `plugin/config/task_system.example.json`
- `docs/task_user_content_decision.md`
- `README.md`
- `plugin/readme.md`

说明：

- 这一组与 planning tool / transcript / immediate content mode 高度耦合。
- `plugin/src/plugin/index.ts` 如果不做 hunk 级拆分，建议整文件跟这一组走。

### Commit 3. Same-Session Routing 子项目

目标：

- 收口 same-session routing 的 truth source / classifier / receipts / acceptance / docs

建议包含：

- `docs/reference/session_message_routing/README.md`
- `docs/reference/session_message_routing/decision_contract.md`
- `docs/reference/session_message_routing/development_plan.md`
- `docs/reference/session_message_routing/test_cases.md`
- `scripts/runtime/same_session_routing.py`
- `scripts/runtime/same_session_routing_acceptance.py`
- `scripts/runtime/session_state.py`
- `scripts/runtime/openclaw_bridge.py`
- `scripts/runtime/openclaw_hooks.py`
- `scripts/runtime/task_status.py`
- `plugin/scripts/runtime/same_session_routing.py`
- `plugin/scripts/runtime/same_session_routing_acceptance.py`
- `plugin/scripts/runtime/session_state.py`
- `plugin/scripts/runtime/openclaw_bridge.py`
- `plugin/scripts/runtime/openclaw_hooks.py`
- `plugin/scripts/runtime/task_status.py`
- `plugin/src/plugin/index.ts`
- `plugin/tests/pre-register-and-ack.test.mjs`
- `plugin/tests/control-plane-lane.test.mjs`
- `tests/test_same_session_routing.py`
- `tests/test_same_session_routing_acceptance.py`
- `tests/test_openclaw_bridge.py`
- `tests/test_openclaw_hooks.py`
- `tests/test_task_status.py`
- `docs/roadmap.md`
- `docs/todo.md`

说明：

- 这一组已经含后续真实链路修复：
  - stale observed takeover
  - runtime-owned `[wd]` receipt 覆盖 generic early ack
  - Feishu completed delivery target fallback

### Commit 4. UX / Follow-up 文案强化

目标：

- 收口近期补的两类用户可见文案优化：
  - 30 秒 running follow-up 进展化
  - `followup-scheduled` 摘要 fallback

如果你要最少 commit 数，建议直接并入 Commit 2 或 Commit 3。

如果你坚持单独拆，需要做 hunk 级 staging，重点文件：

- `scripts/runtime/main_task_adapter.py`
- `plugin/scripts/runtime/main_task_adapter.py`
- `scripts/runtime/openclaw_hooks.py`
- `plugin/scripts/runtime/openclaw_hooks.py`
- `tests/test_openclaw_hooks.py`
- `plugin/tests/tool-planning-flow.test.mjs`
- `docs/todo.md`

## 3. 当前最大的提交边界阻塞点

这些文件承载了多条主题，默认不适合直接整文件提交：

- `plugin/src/plugin/index.ts`
- `scripts/runtime/openclaw_hooks.py`
- `plugin/scripts/runtime/openclaw_hooks.py`
- `tests/test_openclaw_hooks.py`
- `docs/todo.md`

如果不想做复杂 hunk 拆分，最稳妥的做法是：

1. Planning acceptance / install drift 单独一组
2. 其余 runtime + plugin + same-session + task_user_content + recent UX fix 合成一组较大的“runtime behavior closure”

## 4. 最稳的实际执行方案

如果目标是尽快进入“项目整改”，建议不要追求最细 commit。推荐这 3 组：

1. `planning acceptance + install drift + doctor + stable acceptance`
2. `task_user_content removal + planning mode-first + same-session routing`
3. `docs cleanup + handoff + optional dated acceptance records`

这样风险最小，且 review 仍然能看懂。

## 5. 建议先做的人工动作

1. 明确是否要保留两份 dated acceptance record：
   - `docs/planning_acceptance_record_2026-04-09.md`
   - `docs/planning_acceptance_record_2026-04-11.md`
2. 删除或忽略 `t1`
3. 不要把 `docs/artifacts/planning_acceptance_2026-04-11/*` 混进提交
