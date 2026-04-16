# Program Board

## Current Program Direction
- Direction: `wd reliability and task usefulness convergence`
- Status: `active`
- Why Now: 用户已经明确把性能/文档 side-track 从本项目里拿掉，而今天的宿主日志仍然暴露出 `wd` 的用户可见问题，当前最值得排成主线的是把 runtime-owned 反馈做准、做有用

## Program Orchestration Contract

- 程序编排必须引用 `.codex/strategy.md`、`.codex/plan.md`、`.codex/status.md` 和当前 durable 文档，而不是只凭聊天上下文。
- 程序编排层拥有多个 workstreams、切片、执行器输入和串并行边界；它不拥有业务方向变更。
- 任何跨到业务方向、兼容性承诺、外部定位或显著成本 / 时间边界的变化，必须继续升级给人类审批。
- program-board 必须让维护者一眼看出当前有哪些 active workstreams、哪些可并行、下一次调度点是什么。
- 重要的编排收口应写入 devlog，避免只留下结果而没有调度原因。

## Active Workstreams

| Workstream | Scope | State | Priority | Current Focus | Next Checkpoint |
| --- | --- | --- | --- | --- | --- |
| wd receipt truthfulness | register result + queue counters + runtime-owned receipt rendering | active | P0 | 修正首条 `wd` 的队列/开始文案，去掉误导性的自计数和“接上了”语义 | WU-2 完成 |
| terminal usefulness | finalize hook + completion rendering + visible-output policy | active | P0 | 让终态 `wd` 只在有价值时补充，不再复读原任务标签 | WU-3 完成 |
| public-doc scope cleanup | roadmap / development-plan / devlog spillover | active | P1 | 把上一轮性能/文档 side-track 从 public docs 移出 | WU-1 完成 |
| runtime-safety guardrails | Growware validation baseline + doctor / smoke / local deploy | active | P1 | 保持当前功能整改站在绿色验证栈上 | 每轮整改后保持全绿 |

## Sequencing Queue

| Order | Workstream | Slice / Input | Executor | Status |
| --- | --- | --- | --- | --- |
| 1 | public-doc scope cleanup | remove the performance/doc side-track from the active project line | delivery worker | active |
| 2 | wd receipt truthfulness | queue receipt rendering in Python + immediate ack wording in plugin | delivery worker | active |
| 3 | terminal usefulness | generic completion rendering and host-log verification | delivery worker | active |
| 4 | runtime-safety guardrails | targeted tests + mirror + doctor + smoke + local deploy | delivery worker | active |

## Executor Inputs

| Executor | Current Input | Why It Exists | Status |
| --- | --- | --- | --- |
| PTL | `.codex/strategy.md` + `.codex/program-board.md` + `.codex/delivery-supervision.md` + `.codex/status.md` | 判断当前 `wd` 问题是否已经收敛，以及哪些动作仍值得继续自动推进 | active |
| delivery worker | active slice + host-log evidence + validator outputs | 修正 runtime-owned 反馈、跑验证、刷新控制面 | active |
| docs-and-release | public-doc cleanup scope + gate outputs | 只负责把不该留在本项目 public docs 的 side-track 移除 | active |

## Parallel-Safe Boundaries

| Boundary | Parallel-Safe? | Notes |
| --- | --- | --- |
| 读文件 / 快照 / 校验 / 测试 | yes | 安全的只读动作可以和主写入线并行 |
| public-doc cleanup vs wd rendering fixes | yes | 公共文档移除可以与 runtime 修复并行，但共享写入面仍保持串行提交 |
| 同一批 receipt / terminal helper 的双写入 | no | 共享写入面必须串行，不要并行改同一组 `wd` 规则 |
| 战略变化 vs 业务方向变化 | no | 一旦跨到业务方向、兼容性或外部定位，就必须停下来给人类审批 |

## Supporting Backlog Routing

| Topic | Current Position | Re-entry Rule | Notes |
| --- | --- | --- | --- |
| performance side-track | dropped from active project line | 用户已明确要求忽略，不再通过 public docs 或当前主线继续推进 | 彻底移出当前轮次 |
| host-side self-heal | supporting backlog | 只有 `wd` 真正收敛后，才值得继续拉回 | 保持候选 |
| doc-only tidy-up | supporting backlog | 只有不会干扰当前主线且能降低恢复成本时，才并入下个 checkpoint | 按 sidecar 处理 |
| remaining repo-local performance hotspots | supporting backlog | 只有用户重新明确要求，才会回流 | 不再默认抢占主线 |

## Next Orchestration Checks
1. 确认 public docs 已经不再承载这轮性能/文档 side-track。
2. 确认 `wd` 首条 receipt 在 `received` / `queued` / `running` 三类状态下都不再误导用户。
3. 确认 terminal `wd` 只保留有价值的完成/失败信息，不再刷低价值回声。
