# 项目助手交接

## 摘要

| 项目 | 当前值 |
| --- | --- |
| 仓库 | `/Users/redcreen/Project/openclaw-task-system` |
| 层级 | `中型` |
| 当前阶段 | `post-performance live pilot activation preparation` |
| 当前切片 | `activation-prep entry criteria + install-sync decision` |
| 当前执行线 | 先定义 activation 入口条件、证据包和 rollback 边界，再决定 install-sync 路径，最后才允许有界 rehearsal。 |
| 执行进度 | `0 / 3` |
| 架构信号 | `绿色` |
| 升级 Gate | `自动继续` |
| 当前主要风险 | 如果不先显式写清 install-sync 和 rehearsal 边界，下一阶段会重新掉回模糊执行。 |

## 当前真相

- `Milestone 2: Growware Project 1 pilot foundation` 已完成
- `Milestone 3: system performance testing and optimization` 已完成
- roadmap 已经把当前主线切到 `post-performance live pilot activation preparation`
- `.growware/`、`docs/policy/*.md`、`.policy/`、Growware runtime scripts 和 `openclaw_runtime_audit.py` 的 foundation 边界已经收口
- 当前重点不再是继续追 performance hotspot，而是进入 `AP-1` 到 `AP-3`

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
项目助手 继续。先读取 .codex/status.md、.codex/plan.md、docs/roadmap.zh-CN.md、docs/reference/openclaw-task-system/development-plan.zh-CN.md、.codex/strategy.md、.codex/program-board.md、.codex/delivery-supervision.md、.codex/ptl-supervision.md、.codex/worker-handoff.md；然后继续当前执行线：定义 activation 入口条件和 operator evidence 包，决定 installed-runtime drift 是否需要显式 deploy 清理，并在保持性能基线与 Growware / runtime 验证栈全绿的前提下再准备第一次有界 rehearsal。
项目助手 进展
项目助手 继续当前执行线，并先保持性能基线和 Growware 相关验证栈可复跑。
```

### English

```text
project assistant continue. Read .codex/status.md, .codex/plan.md, docs/roadmap.md, docs/reference/openclaw-task-system/development-plan.md, .codex/strategy.md, .codex/program-board.md, .codex/delivery-supervision.md, .codex/ptl-supervision.md, and .codex/worker-handoff.md first; then continue the current execution line: define the activation entry criteria and operator evidence package, decide whether installed-runtime drift needs an explicit deploy refresh, and prepare the first bounded rehearsal while keeping the benchmark and Growware / runtime safety stack green.
project assistant progress
project assistant continue the current execution line and keep the performance baseline plus Growware validation stack rerunnable first.
```

## Next 3 Actions

1. Define the activation entry criteria and operator evidence package for the first bounded rehearsal.
2. Decide whether installed-runtime drift must be cleared before rehearsal through an explicit local deploy.
3. Define the rollback rule and the re-entry condition for any newly observed measured regression.
