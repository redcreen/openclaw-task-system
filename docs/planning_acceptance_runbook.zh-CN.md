[English](planning_acceptance_runbook.md) | [中文](planning_acceptance_runbook.zh-CN.md)

# Planning Acceptance Runbook

## 目标

这份 runbook 说明如何跑一轮真实或半真实的 planning acceptance，并把证据落回仓库。

## 最小顺序

1. 准备运行环境
2. 跑 acceptance helper / bundle
3. 收集 artifacts
4. 填写 acceptance 记录
5. 回写结论与下一步

## 常用入口

```bash
python3 scripts/runtime/prepare_planning_acceptance.py --json
python3 scripts/runtime/run_planning_acceptance_bundle.py --json
python3 scripts/runtime/capture_planning_acceptance_artifacts.py --json
```

更完整的步骤与判断标准见 [planning_acceptance_runbook.md](planning_acceptance_runbook.md)。
