[English](planning_acceptance_runbook.md) | [中文](planning_acceptance_runbook.zh-CN.md)

# Planning Acceptance Runbook

本手册用于做 `Phase 6` 的真实 / 半真实验收。

它不替代自动化 testsuite，而是回答另一类问题：

- planning 路径在真实 channel 里看起来对不对
- 首条 `[wd]`、30 秒 follow-up、计划物化、到点 continuation 是否仍符合当前 contract
- 运维面看到的 truth source，是否和用户体感一致

相关自动化入口：

- [../scripts/runtime/planning_acceptance.py](../scripts/runtime/planning_acceptance.py)
- [../scripts/runtime/stable_acceptance.py](../scripts/runtime/stable_acceptance.py)
- [../scripts/runtime/create_planning_acceptance_record.py](../scripts/runtime/create_planning_acceptance_record.py)
- [../scripts/runtime/prepare_planning_acceptance.py](../scripts/runtime/prepare_planning_acceptance.py)
- [../scripts/runtime/capture_planning_acceptance_artifacts.py](../scripts/runtime/capture_planning_acceptance_artifacts.py)
- [../scripts/runtime/run_planning_acceptance_bundle.py](../scripts/runtime/run_planning_acceptance_bundle.py)
- [../scripts/runtime/planning_acceptance_suite.py](../scripts/runtime/planning_acceptance_suite.py)
- [planning_acceptance_record_template.md](./planning_acceptance_record_template.md)
- [archive/planning_acceptance_record_2026-04-09.md](./archive/planning_acceptance_record_2026-04-09.md)

说明：

- `docs/artifacts/` 用于存放运行时抓取的临时验收产物，目录默认通过局部 `.gitignore` 忽略。
- 如果某次验收产物需要正式保留，请手动挑选需要的文件再纳入版本控制。

## 1. 适用场景

适合在这些时候跑：

- 刚改完 planning / follow-up / continuity 逻辑
- 准备发版前做一轮人工确认
- 怀疑“用户看见的”和“运维面显示的”不一致

## 2. 验收前准备

先确认基础入口正常：

```bash
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py --json
python3 scripts/runtime/planning_acceptance.py --json
python3 scripts/runtime/stable_acceptance.py --json
```

如果这里已经失败，就先不要做真实通道验收。

如果准备开始一轮新的记录，可以先生成一份当天记录草稿：

```bash
python3 scripts/runtime/create_planning_acceptance_record.py
python3 scripts/runtime/create_planning_acceptance_record.py --print-next-steps
python3 scripts/runtime/create_planning_acceptance_record.py --json
python3 scripts/runtime/prepare_planning_acceptance.py --json
python3 scripts/runtime/capture_planning_acceptance_artifacts.py --json
python3 scripts/runtime/run_planning_acceptance_bundle.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
```

## 3. 半真实验收

半真实验收的目标是：不依赖真实用户，但用一条固定脚本把 planning 最小闭环走完。

推荐顺序：

1. 跑 `planning_acceptance.py --json`
2. 看 `main_ops.py planning --json`
3. 看 `main_ops.py continuity --json`
4. 对照 acceptance 输出确认 evidence chain 完整

命令：

```bash
python3 scripts/runtime/planning_acceptance.py --json
python3 scripts/runtime/main_ops.py planning --json
python3 scripts/runtime/main_ops.py continuity --json
```

重点确认：

- `register-source-task` 成功
- `create-planning-tools-state` 成功
- `materialize-and-finalize-followup` 成功
- `claim-overdue-followup-and-project-ops` 成功
- planning 视图里能看到 planning task / pending / anomaly / overdue 统计

如果使用 `capture_planning_acceptance_artifacts.py` 或 `run_planning_acceptance_bundle.py`，还应检查：

- `docs/artifacts/planning_acceptance_<date>/capture_manifest.json`
- `docs/artifacts/planning_acceptance_<date>/bundle_summary.json`

这两个文件分别提供：

- capture 阶段写了哪些产物
- bundle 阶段的汇总结论与失败标签

## 4. 真实通道验收

建议优先在 Feishu 或 Telegram 里用一个测试会话完成。

推荐样例请求：

```text
先整理这批问题，5 分钟后回来同步结论。
```

期望体验：

1. 用户先收到首条 `[wd]`
2. 这条首回执仍是 runtime-owned，而不是 tool 直接发出的自由文本
3. 在任务运行过程中，如果 30 秒 follow-up 被触发，内容应能说明当前进展 / 计划状态 / 是否存在 planning anomaly
4. 到了 follow-up 时间，系统能把计划物化为 continuation 并执行
5. 最终收口后，不应残留 `promise-without-task`

## 5. 运维面核对

在真实会话进行时，建议同时开三个窗口：

```bash
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/main_ops.py planning --json
python3 scripts/runtime/main_ops.py continuity --json
```

看点分别是：

- `dashboard`
  - 是否把 planning 风险投影成当前主问题
- `planning`
  - 是否看得到 planning task、pending、anomaly、overdue 和推荐动作
- `continuity`
  - 到点 continuation 是否被稳定 claim / resume / close

## 6. 失败判定

出现下面任一情况，就应该视为验收失败：

- 首条 `[wd]` 不是第一条可见控制面回执
- 30 秒 follow-up 退化成空泛“仍在处理中”，没有带出可解释状态
- promise 已写入，但没有对应 follow-up task，且 finalize 后仍未报 anomaly
- follow-up 已 overdue，但 continuity / planning 视图看不到证据
- 用户看到的状态与 `planning --json` / `continuity --json` 明显不一致

## 7. 记录建议

每次真实 / 半真实验收，至少保留这些证据：

- 用户侧消息截图或转录
- `planning_acceptance.py --json` 输出
- `main_ops.py planning --json` 输出
- `main_ops.py continuity --json` 输出
- 如果失败，再补 `dashboard --json` 和 `triage --json`

推荐直接用：

- [planning_acceptance_record_template.md](./planning_acceptance_record_template.md)
- [archive/planning_acceptance_record_2026-04-09.md](./archive/planning_acceptance_record_2026-04-09.md)
