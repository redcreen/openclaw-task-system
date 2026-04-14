# Program Board

## Current Program Direction
- Direction: `Milestone 3: system performance testing and optimization`
- Status: `active`
- Why Now: Growware foundation 已收口，当前最值得排成主线的是 benchmark baseline、热点归因和回归门禁

## Program Orchestration Contract

- 程序编排必须引用 `.codex/strategy.md`、`.codex/plan.md`、`.codex/status.md` 和当前 durable 文档，而不是只凭聊天上下文。
- 程序编排层拥有多个 workstreams、切片、执行器输入和串并行边界；它不拥有业务方向变更。
- 任何跨到业务方向、兼容性承诺、外部定位或显著成本 / 时间边界的变化，必须继续升级给人类审批。
- program-board 必须让维护者一眼看出当前有哪些 active workstreams、哪些可并行、下一次调度点是什么。
- 重要的编排收口应写入 devlog，避免只留下结果而没有调度原因。

## Active Workstreams

| Workstream | Scope | State | Priority | Current Focus | Next Checkpoint |
| --- | --- | --- | --- | --- | --- |
| performance baseline foundation | benchmark surface / fixtures / budgets | active | P0 | 定义先测什么、如何测、预算是什么 | PL-1 完成 |
| measurement entrypoints | benchmark helpers / repeatable commands / baseline capture | active | P0 | 让基线可以稳定复跑 | PL-2 完成 |
| runtime-safety validation | Growware / runtime 安全验证栈 | active | P1 | 保持性能阶段不破坏已收口的 foundation | 基线采集前后都保持全绿 |
| post-performance activation planning | live rehearsal / operator evidence / rollout prep | next | P2 | 只做候选，不抢占当前性能主线 | 性能基线稳定后再复核 |

## Sequencing Queue

| Order | Workstream | Slice / Input | Executor | Status |
| --- | --- | --- | --- | --- |
| 1 | performance baseline foundation | benchmark surface + budgets | delivery worker | active |
| 2 | measurement entrypoints | 可复现命令、fixtures 与 baseline harness | delivery worker | active |
| 3 | runtime-safety validation | 保持 Growware / runtime 验证栈全绿 | docs-and-release | active |
| 4 | post-performance activation planning | activation rehearsal 的恢复顺序与证据要求 | PTL | next |

## Executor Inputs

| Executor | Current Input | Why It Exists | Status |
| --- | --- | --- | --- |
| PTL | `.codex/strategy.md` + `.codex/program-board.md` + `.codex/delivery-supervision.md` + `.codex/status.md` | 决定当前主线是否继续、重排或升级 | active |
| delivery worker | active slice + execution tasks + validator outputs | 推进当前 checkpoint 并保持与 program-board 对齐 | active |
| docs-and-release | roadmap + development-plan + baseline evidence + gate outputs | 保持 durable docs、交接说明和门禁一致 | active |

## Parallel-Safe Boundaries

| Boundary | Parallel-Safe? | Notes |
| --- | --- | --- |
| 读文件 / 快照 / 校验 / 测试 | yes | 安全的只读动作可以和主写入线并行 |
| benchmark 设计 vs 文档对齐 | yes | 文档可以跟着 benchmark 设计更新，但 `.codex/plan.md` / `.codex/status.md` 仍保持唯一真相源 |
| 同一批 benchmark helper 的双写入 | no | 共享写入面必须串行，不要并行改同一组测量入口 |
| 战略变化 vs 业务方向变化 | no | 一旦跨到业务方向、兼容性或外部定位，就必须停下来给人类审批 |

## Supporting Backlog Routing

| Topic | Current Position | Re-entry Rule | Notes |
| --- | --- | --- | --- |
| live pilot activation | supporting backlog | 只有 benchmark baseline 和回归门禁成形后，才允许回流主线 | 暂不抢占 M3 |
| host-side self-heal | supporting backlog | 只有 audit bootstrap 明确要升级成产品能力时，才回流 | 保持候选 |
| doc-only tidy-up | supporting backlog | 只有不会干扰当前主线且能降低恢复成本时，才并入下个 checkpoint | 按 sidecar 处理 |

## Next Orchestration Checks
1. 确认 benchmark surface 已经覆盖 runtime、control-plane 和 operator 入口，而不是只覆盖单一模块。
2. 判断哪些测量入口必须先落脚本，哪些还能先用现有命令收集 baseline。
3. 如果性能验证成本开始明显上升，再决定是否拆出 fast / deep 两层基线。
