# 项目助手交接

## 摘要

| 项目 | 当前值 |
| --- | --- |
| 仓库 | `/Users/redcreen/Project/openclaw-task-system` |
| 层级 | `中型` |
| 当前阶段 | `Milestone 2: Growware Project 1 pilot foundation` |
| 当前切片 | `growware pilot: policy truth + activation baseline` |
| 当前执行线 | 先收敛 policy truth、activation gate 和 host-audit bootstrap，再决定是否进入 live pilot activation。 |
| 执行进度 | `1 / 4` |
| 架构信号 | `黄色` |
| 升级 Gate | `提醒后继续` |
| 当前主要风险 | `.policy/` 与 `.growware/policies/*.json` 仍有兼容层漂移；activation baseline 还没在一条干净基线上全部跑通。 |

## 当前真相

- roadmap 已经正式打开 `Milestone 2: Growware Project 1 pilot foundation`
- `.growware/`、`docs/policy/*.md`、`.policy/`、Growware runtime scripts 和 `openclaw_runtime_audit.py` 是这轮 review 的核心实现面
- `EL-1` 已完成；当前重点是 `EL-2` 到 `EL-4`

## Restore Order

1. `.codex/status.md`
2. `.codex/plan.md`
3. `docs/roadmap.zh-CN.md`
4. `docs/reference/openclaw-task-system/development-plan.zh-CN.md`
5. `.codex/strategy.md`
6. `.codex/program-board.md`
7. `.codex/delivery-supervision.md`
8. `.codex/ptl-supervision.md`
9. `.codex/worker-handoff.md`

## Copy-Paste Commands

### Chinese

```text
项目助手 继续。先读取 .codex/status.md、.codex/plan.md、docs/roadmap.zh-CN.md、docs/reference/openclaw-task-system/development-plan.zh-CN.md、.codex/strategy.md、.codex/program-board.md、.codex/delivery-supervision.md、.codex/ptl-supervision.md、.codex/worker-handoff.md；然后继续当前执行线：关闭 Growware 的 policy truth 裂缝，跑 activation baseline，并决定 host audit 的 milestone 边界。
项目助手 进展
项目助手 继续当前执行线，并先运行 Growware 相关验证栈。
```

### English

```text
project assistant continue. Read .codex/status.md, .codex/plan.md, docs/roadmap.md, docs/reference/openclaw-task-system/development-plan.md, .codex/strategy.md, .codex/program-board.md, .codex/delivery-supervision.md, .codex/ptl-supervision.md, and .codex/worker-handoff.md first; then continue the current execution line: close the Growware policy-truth gap, run the activation baseline, and decide the host-audit milestone boundary.
project assistant progress
project assistant continue the current execution line and run the Growware validation stack first.
```

## Next 3 Actions

1. Close EL-2 by making compiled `.policy/` the only live policy truth the runtime depends on.
2. Run the reviewed activation baseline across policy sync, preflight, binding preview, runtime mirror, doctor, smoke, and targeted Growware / audit tests.
3. Decide whether host-side audit remains bootstrap-only or becomes the lead item of the next named milestone.
