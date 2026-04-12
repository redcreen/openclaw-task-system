[English](planning_acceptance_runbook.md) | [中文](planning_acceptance_runbook.zh-CN.md)

# Planning Acceptance Runbook

## 目标

这份 runbook 说明如何跑一轮真实或半真实的 planning acceptance，并把证据落回仓库。

## 最小顺序

1. 准备运行环境
2. 跑 acceptance helper / bundle
3. 收集 artifacts
4. 在 `docs/archive/` 下填写 acceptance 记录
5. 回写结论与下一步

## 常用入口

```bash
python3 scripts/runtime/prepare_planning_acceptance.py --json
python3 scripts/runtime/run_planning_acceptance_bundle.py --json
python3 scripts/runtime/capture_planning_acceptance_artifacts.py --json
```

如果你只是想先演练整条流程，而不往 `docs/archive/` 或 `docs/artifacts/` 真写仓库内容，就加 `--dry-run`：

```bash
python3 scripts/runtime/prepare_planning_acceptance.py --dry-run --json
python3 scripts/runtime/run_planning_acceptance_bundle.py --dry-run --json
python3 scripts/runtime/planning_acceptance_suite.py --dry-run --json
```

`dry-run` 会把 record 和 artifacts 写进临时工作区，并在 JSON 结果里返回该工作区路径。

## 升档策略

把 `--dry-run` 视为演练，不要把它当成最终 dated evidence。

只有同时满足下面三条时，才应该把 dry-run 升档进 `docs/archive/`：

1. 跑的是完整 bundle，并且结果全绿
2. 不是 `--label` 过滤后的局部演练
3. 当前改动触达 planning/runtime contract、release-facing acceptance 覆盖，或 planning evidence workflow 本身

满足这些条件后，执行：

```bash
python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date YYYY-MM-DD
```

这个升档动作会刷新 repo-side artifacts；如果同日期 archive record 已存在，会保留现有记录，不再回退成模板内容。

结构化策略字段的解释：

- `promotion_status=ready-for-archive`：这次 dry-run 已具备升档条件；如果当前改动需要正式 dated evidence，就应该补 archive
- `promotion_status=insufficient-signal`：只跑了局部 label，不能直接升档
- `promotion_status=blocked`：先把 dry-run 里的失败修掉
- `promotion_status=already-archived`：这次运行本身已经写了 repo-side evidence

现在 bundle 和 suite 的 JSON / markdown 输出都会直接带上这套 promotion policy。

更完整的步骤与判断标准见 [planning_acceptance_runbook.md](planning_acceptance_runbook.md)。
