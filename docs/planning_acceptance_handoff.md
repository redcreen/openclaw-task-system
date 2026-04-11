[English](planning_acceptance_handoff.md) | [中文](planning_acceptance_handoff.zh-CN.md)

# Planning Acceptance Handoff

目标：

- 把当前 worktree 整理成可提交、可接手、可继续验收的状态。
- 当前重点不再是补 `task_user_content` 机制，而是维护 `mode-first + structured planning state` 的主链路。

当前状态：

- `task_user_content`
  - Phase 4 已完成：运行时主链路已废弃 marker 协议。
  - Phase 5 已完成：主代码里的 marker 兼容分支已经物理删除。
  - 历史审计 / 清理工具保留：
    - `scripts/runtime/check_task_user_content_leaks.py`
    - `scripts/runtime/scrub_task_user_content_history.py`
- 真实运行验证
  - `main` 新链路已验证干净。
  - 推荐命令：
    - `python3 scripts/runtime/check_task_user_content_leaks.py --since 2026-04-11T12:18:34+08:00 --json`
  - 当前该命令返回 `ok: true`
- continuity
  - 之前的 `main` 积压风险已不再存在。
  - 过程中误 claim 出一个老的 `test-user` 延迟回复测试残留：
    - `task_ba234cada9e54bcfa1d79a0d4984b9c8`
    - 已按 `stale test-user delayed-reply artifact claimed during continuity cleanup` 失败归档
  - 当前验证：
    - `python3 scripts/runtime/main_ops.py continuity --json`
    - `python3 scripts/runtime/main_ops.py lanes --json`
  - 两者都已清空 active continuity 风险
- 当前唯一仍然明确存在的运维告警：
  - install drift
  - 验证命令：
    - `python3 scripts/runtime/plugin_install_drift.py --json`
  - 目前 installed runtime 仍缺 8 个脚本

本轮关键结果：

- planning truth source / health / ops projection 已落地
- planning acceptance 工具链已落地
- install drift observability 已落地
- `task_user_content` 已降为历史审计问题，不再是运行时协议
- CLI 级“重启后新日志验证”已可用

推荐继续顺序：

1. 先按提交面拆 worktree
2. 再决定是否手工同步 installable payload 到本地安装态 runtime
3. 最后再做更完整的真实 channel 验收记录

建议提交分组：

1. Phase 6 runtime closure
2. Install drift and local install observability
3. Planning acceptance toolchain
4. `task_user_content` removal and history audit tooling
5. Docs and handoff

建议先跑的命令：

```bash
python3 scripts/runtime/main_ops.py continuity --json
python3 scripts/runtime/main_ops.py lanes --json
python3 scripts/runtime/plugin_install_drift.py --json
python3 scripts/runtime/check_task_user_content_leaks.py --since 2026-04-11T12:18:34+08:00 --json
node --test plugin/tests/tool-planning-flow.test.mjs
python3 -m unittest discover -s tests -p 'test_task_planning_tools.py' -v
python3 -m unittest discover -s tests -p 'test_openclaw_hooks.py' -v
python3 -m unittest discover -s tests -p 'test_check_task_user_content_leaks.py' -v
```

注意事项：

- 不要动未跟踪空文件 `t1`
- 不要回滚用户已有改动
- `plugin/scripts/runtime/` 和 `scripts/runtime/` 需要持续保持同步
- 当前不建议把 install drift 误当成 continuity 问题；它们已经是两类不同信号
