# Program Board

## Current Program Direction
- Direction: `Milestone 2: Growware Project 1 pilot foundation`
- Status: `active`
- Why Now: 把已经落地的 Growware policy / deploy / audit 基础收敛成一条明确执行线，而不是继续挂成 future candidate

## Program Orchestration Contract

- 程序编排必须引用 `.codex/strategy.md`、`.codex/plan.md`、`.codex/status.md` 和当前 durable 文档，而不是只凭聊天上下文。
- 程序编排层拥有多个 workstreams、切片、执行器输入和串并行边界；它不拥有业务方向变更。
- 任何跨到业务方向、兼容性承诺、外部定位或显著成本 / 时间边界的变化，必须继续升级给人类审批。
- program-board 必须让维护者一眼看出当前有哪些 active workstreams、哪些可并行、下一次调度点是什么。
- 重要的编排收口应写入 devlog，避免只留下结果而没有调度原因。

## Active Workstreams

| Workstream | Scope | State | Priority | Current Focus | Next Checkpoint |
| --- | --- | --- | --- | --- | --- |
| growware pilot foundation | policy truth / Growware scripts / binding boundary | active | P0 | 关闭 policy 真相与激活边界裂缝 | EL-2 和 EL-3 达成同一条基线 |
| control truth and docs alignment | plan / status / roadmap / development plan / docs | active | P1 | 保持控制面、文档与当前里程碑同步 | 避免继续把 active work 写成 future candidate |
| validation and activation gates | policy sync / preflight / mirror / doctor / smoke / targeted tests | active | P1 | 保持 Growware pilot baseline 可执行 | 下一轮验证收口 |
| host audit and next-milestone routing | runtime audit / session hygiene / self-heal boundary | active | P2 | 决定 audit 是 bootstrap 还是下一里程碑入口 | EL-4 完成时复核 |

## Sequencing Queue

| Order | Workstream | Slice / Input | Executor | Status |
| --- | --- | --- | --- | --- |
| 1 | growware pilot foundation | policy truth + activation baseline | delivery worker | active |
| 2 | control truth and docs alignment | 保持 roadmap / development plan / `.codex/*` 同步 | docs-and-release | active |
| 3 | validation and activation gates | 运行 Growware / runtime 验证并把结果写回真相 | delivery worker | active |
| 4 | host audit and next-milestone routing | 决定 audit 与 activation 工作如何分层 | PTL | next |

## Executor Inputs

| Executor | Current Input | Why It Exists | Status |
| --- | --- | --- | --- |
| PTL | `.codex/strategy.md` + `.codex/program-board.md` + `.codex/delivery-supervision.md` + `.codex/status.md` | 决定当前主线是否继续、重排或升级 | active |
| delivery worker | active slice + execution tasks + validator outputs | 推进当前 checkpoint 并保持与 program-board 对齐 | active |
| docs-and-release | README + roadmap + development-plan + gate outputs | 保持 durable docs、交接说明和门禁一致 | active |

## Parallel-Safe Boundaries

| Boundary | Parallel-Safe? | Notes |
| --- | --- | --- |
| 读文件 / 快照 / 校验 / 测试 | yes | 安全的只读动作可以和主写入线并行 |
| docs alignment vs control truth | yes | 文档更新可以跟随 control truth，但 `.codex/plan.md` / `.codex/status.md` 仍保持唯一真相源 |
| 同一批文件的双写入 | no | 共享写入面必须串行，不要并行改同一套控制面或主代码边界 |
| 战略变化 vs 业务方向变化 | no | 一旦跨到业务方向、兼容性或外部定位，就必须停下来给人类审批 |

## Supporting Backlog Routing

| Topic | Current Position | Re-entry Rule | Notes |
| --- | --- | --- | --- |
| maintainer-facing polish | supporting backlog | 只有明确降低接手成本时，才允许回流主线 | 保持在 backlog |
| doc-only tidy-up | supporting backlog | 只有不会干扰当前主线且能降低恢复成本时，才并入下个 checkpoint | 按 sidecar 处理 |
| post-foundation activation | supporting backlog | 只有当前 foundation gate 收干净后，才升级成新的正式主线 | 暂不抢占当前 milestone |

## Next Orchestration Checks
1. 确认当前 active slice、执行线和 supporting backlog 都围绕同一个 Growware milestone 排序。
2. 判断 activation baseline 里的哪些步骤必须串行，哪些 sidecar 工作还能并入同一个 checkpoint。
3. 如果 runtime audit 或 live activation 需要更强编排，再整理成后续多执行器候选。
