# Program Board

## Current Program Direction
- Direction: `reply-latency and context-weight governance`
- Status: `active`
- Why Now: repo-local hotspot work已收口，但 host-observed Telegram 会话仍存在明显的回复慢问题，当前最值得排成主线的是把 slowdown 变成可重复治理对象，而不是直接推进 activation prep

## Program Orchestration Contract

- 程序编排必须引用 `.codex/strategy.md`、`.codex/plan.md`、`.codex/status.md` 和当前 durable 文档，而不是只凭聊天上下文。
- 程序编排层拥有多个 workstreams、切片、执行器输入和串并行边界；它不拥有业务方向变更。
- 任何跨到业务方向、兼容性承诺、外部定位或显著成本 / 时间边界的变化，必须继续升级给人类审批。
- program-board 必须让维护者一眼看出当前有哪些 active workstreams、哪些可并行、下一次调度点是什么。
- 重要的编排收口应写入 devlog，避免只留下结果而没有调度原因。

## Active Workstreams

| Workstream | Scope | State | Priority | Current Focus | Next Checkpoint |
| --- | --- | --- | --- | --- | --- |
| session-latency evidence | real session JSONL + metadata + reusable audit command | active | P0 | 固化 turn timing、LLM share、tool share 和上下文负载 | TG-1 完成 |
| prompt-surface diet | tools / system prompt / skills / workspace bootstrap | active | P0 | 第一刀已完成：收短 planning prompt 与默认 wrapper；继续处理 tool surface | TG-2 收口 |
| startup and transcript discipline | startup reads / wrapper tax / history growth | active | P1 | wrapper tax 第一刀已落地；继续识别 startup carryover 不该留到后续 turn 的部分 | carryover rules 写成真相 |
| activation resume gate | re-entry rule back to activation preparation | supporting | P1 | 让 activation 线有明确恢复条件，不抢当前治理主线 | TG-3 完成 |
| runtime-safety + repo-local performance guardrails | benchmark / Growware validation baseline | active | P1 | 保持当前优化 topic 站在绿色 guardrail 上 | 每轮治理后保持全绿 |

## Sequencing Queue

| Order | Workstream | Slice / Input | Executor | Status |
| --- | --- | --- | --- | --- |
| 1 | session-latency evidence | Telegram trigger session + durable audit command | delivery worker | active |
| 2 | prompt-surface diet | system prompt report + compact planning prompt / wrapper slice | delivery worker | active |
| 3 | startup and transcript discipline | startup carryover + post-wrapper transcript discipline | delivery worker | active |
| 4 | activation resume gate | measured unblock criteria | PTL + docs-and-release | supporting |
| 5 | runtime-safety + repo-local performance guardrails | benchmark budgets + Growware validation baseline | delivery worker | active |

## Executor Inputs

| Executor | Current Input | Why It Exists | Status |
| --- | --- | --- | --- |
| PTL | `.codex/strategy.md` + `.codex/program-board.md` + `.codex/delivery-supervision.md` + `.codex/status.md` | 判断当前 slowdown 是否仍是 measured blocker，以及何时恢复 activation 线 | active |
| delivery worker | active slice + session audit output + validator outputs | 固化治理证据、推进脚本 / 文档 / 代码切片并保持与 program-board 对齐 | active |
| docs-and-release | roadmap + development-plan + governance evidence + gate outputs | 保持 durable docs、devlog 和主线边界一致 | active |

## Parallel-Safe Boundaries

| Boundary | Parallel-Safe? | Notes |
| --- | --- | --- |
| 读文件 / 快照 / 校验 / 测试 | yes | 安全的只读动作可以和主写入线并行 |
| audit tooling vs 文档对齐 | yes | 文档可以跟着 audit contract 更新，但 `.codex/plan.md` / `.codex/status.md` 仍保持唯一真相源 |
| 同一批 prompt/context helper 的双写入 | no | 共享写入面必须串行，不要并行改同一组治理入口 |
| 战略变化 vs 业务方向变化 | no | 一旦跨到业务方向、兼容性或外部定位，就必须停下来给人类审批 |

## Supporting Backlog Routing

| Topic | Current Position | Re-entry Rule | Notes |
| --- | --- | --- | --- |
| live pilot activation prep | supporting backlog | 只有治理专题给出明确 resume 条件后，才回到主线 | 不等于取消，只是暂时退到 supporting backlog |
| host-side self-heal | supporting backlog | 只有 audit bootstrap 明确要升级成产品能力时，才回流 | 保持候选 |
| doc-only tidy-up | supporting backlog | 只有不会干扰当前主线且能降低恢复成本时，才并入下个 checkpoint | 按 sidecar 处理 |
| remaining repo-local performance hotspots | supporting backlog | 只有新的 repo-local benchmark 明确把它们升级成 blocker 时，才回流 | 不再默认抢占主线 |

## Next Orchestration Checks
1. 确认 TG-2 第一轮小闭环已经在 plan / status / docs / devlog 里变成 durable truth，而不是只留在代码 diff。
2. 把 prompt-surface 和 startup/transcript 的后续减负队列继续排成清晰顺序，而不是混成一个“感觉都该优化”的桶。
3. 给 activation 线写出恢复条件，避免治理专题结束后主线再次失焦。
