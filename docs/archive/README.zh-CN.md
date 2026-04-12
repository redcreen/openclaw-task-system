# 归档文档

[English](README.md) | [中文](README.zh-CN.md)

## 目的

这个目录存放已被替代、探索性、或历史遗留的 Markdown 文档。它们保留历史价值，但不再作为当前主文档使用。

## 当前内容

- `planning_acceptance_record_2026-04-09.*`：带日期的验收样例
- `planning_acceptance_record_2026-04-12.*`：acceptance helper 扩展后的半真实验收刷新记录
- `planning_acceptance_handoff.*`：历史交接快照
- `planning_acceptance_commit_plan.*`：旧的提交拆分建议
- `cleanup_commit_plan.*`：一次性整改拆分方案
- `local_install_validation_2026-04-09.*`：带日期的本地安装验证记录

## 适合什么时候看

- 需要补历史验收证据时
- 需要回看旧的交接或整改决策时
- 需要核对某次带日期的安装验证记录时

## Planning Evidence 升档策略

当下面三条同时成立时，把 planning dry-run 升档成 dated archive record：

- 完整 dry-run bundle 全绿
- 不是 `--label` 过滤后的局部演练
- 当前改动触达 planning/runtime contract、release-facing acceptance 覆盖，或 planning evidence workflow

升档命令：

```bash
python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date YYYY-MM-DD
```

如果同日期 archive record 已存在，会保留现有记录，只刷新证据 artifacts。
