# Development Plan

[English](#english) | [中文](#中文)

## English

### 1. Purpose

This document turns the same-session message routing design into an executable subproject plan.

It is meant to be used as the working checklist until the subproject is complete.

Current status:

- implemented through Phase 8
- kept as the shipped execution record for this subproject

The plan assumes:

- the design packet has been reviewed
- the core contract in [decision_contract.md](./decision_contract.md) is accepted
- the scenario expectations in [test_cases.md](./test_cases.md) are the baseline for implementation

### 2. Completion goal

This subproject is complete only when all of the following are true:

1. same-session follow-up messages are formally routed across:
   - `control-plane`
   - `steering`
   - `queueing`
   - `collect-more`
2. runtime can choose:
   - `merge-before-start`
   - `interrupt-and-restart`
   - `append-as-next-step`
   - `queue-as-new-task`
   - `enter-collecting-window`
3. ambiguous cases are handled by a runtime-owned structured LLM classifier
4. every automatic routing decision produces a runtime-owned `[wd]` receipt
5. the behavior is covered by:
   - contract tests
   - classifier trigger tests
   - end-to-end session tests
6. roadmap, testsuite, usage, and acceptance docs are updated to reflect the shipped behavior

### 3. Delivery strategy

This subproject should not be implemented as one large patch.

Recommended strategy:

1. formalize the runtime contract first
2. ship deterministic rule-only cases first
3. add the execution-stage gate
4. add `[wd]` routing receipts
5. only then introduce the LLM classifier for ambiguous cases
6. finish with acceptance coverage and operational visibility

### 4. Phase plan

#### Phase 0. Review lock

Goal:

- freeze the design contract before implementation starts

Deliverables:

- reviewed [README.md](./README.md)
- reviewed [decision_contract.md](./decision_contract.md)
- reviewed [test_cases.md](./test_cases.md)
- reviewed this [development_plan.md](./development_plan.md)

Exit criteria:

- accepted decision taxonomy
- accepted `[wd]` receipt style
- accepted classifier trigger boundary
- accepted interrupt/restart safety boundary

#### Phase 1. Runtime routing truth source

Goal:

- add a formal truth-source shape for same-session follow-up routing

Current implementation checkpoint:

- runtime now records a structured same-session routing record in task truth source and hook output
- the record is intentionally provisional for same-session follow-up cases that still wait for the remaining Phase 2 rule gate
- obvious `control-plane` and `no-active-task` cases can already be represented as explicit structured decisions

Recommended outputs:

- structured routing decision record
- reason code and reason text fields
- target task/session references
- explicit execution decision field

Suggested implementation areas:

- producer/runtime state layer
- task truth source projection layer
- debug/event trace output

Exit criteria:

- routing decisions are first-class structured state
- decisions are inspectable without reading raw logs

#### Phase 2. Deterministic rule path

Goal:

- ship the obvious non-LLM routing cases first

Must-cover cases:

- obvious `control-plane`
- obvious `collect-more`
- no-active-task default new request
- obvious independent new request during active task

Recommended outputs:

- rule gate implementation
- explicit “classifier not needed” path
- baseline rule-only tests

Exit criteria:

- obvious cases route correctly without classifier
- no regression to existing control-plane behavior

Current implementation checkpoint:

- deterministic rules now cover obvious `control-plane`, `collect-more`, `no-active-task`, and obvious independent new requests
- ambiguous same-session follow-ups now escalate into a runtime-owned classifier path or an explicit safe fallback, instead of staying implicit

#### Phase 3. Execution-stage gate

Goal:

- separate “message meaning” from “safe execution action”

Must-cover stage gates:

- `received / queued` -> `merge-before-start`
- `running-no-side-effects` -> `interrupt-and-restart`
- `running-with-side-effects` -> `append-as-next-step` or `queue-as-new-task`
- `paused / continuation` -> bounded non-destructive handling

Recommended outputs:

- formal stage enum or equivalent projection
- safe-restart gate
- side-effect-aware routing behavior

Exit criteria:

- steering no longer implies one fixed execution action
- runtime can explain why it merged, restarted, appended, or queued

#### Phase 4. `[wd]` routing receipts

Goal:

- make every routing decision visible to the user

Current implementation checkpoint:

- runtime now emits same-session routing receipt payloads for deterministic routing decisions
- the plugin immediate-ack path now prefers runtime-owned receipt wording over local fallback wording

Must-cover:

- decision-specific receipt templates
- short human-readable reason
- runtime-owned rendering only

Recommended outputs:

- `[wd]` template table in code
- structured receipt payload
- transcript and channel delivery tests

Exit criteria:

- every automatic routing decision returns a user-visible receipt
- receipts are short, truthful, and decision-specific

#### Phase 5. Runtime-owned LLM classifier

Goal:

- handle ambiguous same-session follow-up messages without turning the system into a front-door semantic classifier

Current implementation checkpoint:

- runtime now supports a config-driven same-session classifier adapter instead of leaving classifier ownership to the main LLM
- only ambiguous same-session follow-ups become classifier candidates after deterministic rules fail
- disabled, error, timeout, and low-confidence classifier outcomes now fall back through explicit runtime-owned safe paths

Must-cover:

- classifier input schema
- classifier output schema
- timeout and low-confidence fallback
- runtime-owned invocation path

Explicit non-goals:

- free-form main-LLM self-routing
- classifier on every message
- replacing the main execution LLM

Exit criteria:

- ambiguous cases can trigger classifier
- low-confidence results fall back safely
- classifier ownership stays on runtime

Current implementation checkpoint:

- ambiguous same-session follow-ups now trigger a runtime-owned injectable structured classifier path
- classifier input/output are now formalized as structured payloads inside routing decision state
- timeout/error/unavailable/low-confidence outcomes now fall back to explicit safe routing decisions instead of staying recorded-only

#### Phase 6. Collecting window

Goal:

- support “I’m still sending more, don’t start yet” as a first-class behavior

Must-cover:

- collecting state in session truth source
- configurable short collecting window
- timeout behavior when no more messages arrive
- `[wd]` receipt for collect-more activation

Exit criteria:

- collect-more is a real state, not a loose phrase convention
- batch start behavior is predictable and testable

Current implementation checkpoint:

- runtime now persists a session-level collecting window truth source with `status / expires_at / buffered_user_messages`
- explicit `collect-more` requests now activate the collecting window instead of immediately registering a new task
- follow-up messages inside the active window are buffered and keep returning runtime-owned `[wd]` collecting receipts
- when the window expires, runtime now materializes either the buffered merged request or the existing pre-start task and dispatches an internal wake prompt

#### Phase 7. End-to-end tests and acceptance

Goal:

- prove the routing model works in realistic multi-message flows

Must-cover:

- pure contract tests
- classifier trigger tests
- end-to-end same-session flows
- receipt delivery tests

Recommended acceptance flows:

- clarify current task before start
- clarify current task during safe-running stage
- introduce a new task during active execution
- ask runtime to wait for more inputs
- send control-plane follow-up while a task is active

Exit criteria:

- the shipped scenarios in [test_cases.md](./test_cases.md) are covered
- acceptance docs describe how to validate this in a real channel

Current implementation checkpoint:

- end-to-end same-session flows now run in `same_session_routing_acceptance.py`
- stable acceptance now includes the same-session routing acceptance bundle as a required step

#### Phase 8. Docs and operational rollout

Goal:

- make the feature operable, explainable, and reviewable after shipping

Must-cover docs:

- roadmap
- testsuite
- usage guide
- architecture if runtime boundaries changed
- acceptance/runbook docs if user-facing behavior changed

Must-cover ops visibility:

- decision trace visibility
- classifier invocation visibility
- low-confidence / fallback visibility

Exit criteria:

- maintainers can explain the feature without reading source code
- operations can inspect why a routing decision happened

Current implementation checkpoint:

- roadmap, testsuite, and usage docs now describe the shipped same-session routing behavior
- acceptance coverage is exposed through `same_session_routing_acceptance.py --json` and `stable_acceptance.py --json`

### 5. Recommended implementation order

The recommended order is:

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6
7. Phase 7
8. Phase 8

Reason:

- first make routing state explicit
- then ship deterministic behavior
- then add user-visible receipts
- then add classifier support only where needed

### 6. Suggested code slices

These are the likely code slices, not a guaranteed file list:

- producer contract / runtime routing state
- plugin receive-side decision path
- same-session task binding / routing metadata
- `[wd]` rendering path
- classifier invocation adapter
- tests for contract and end-to-end session routing
- docs and runbooks

### 7. Testing plan

Minimum per-phase test expectations:

| Phase | Minimum tests |
|---|---|
| 1 | truth-source contract tests |
| 2 | rule-only routing tests |
| 3 | execution-stage gate tests |
| 4 | `[wd]` receipt rendering and delivery tests |
| 5 | classifier trigger / fallback tests |
| 6 | collecting window state tests |
| 7 | end-to-end multi-message session tests |
| 8 | docs and acceptance sync check |

### 8. Risks to manage

Main risks:

1. classifier scope drift
   - avoid calling LLM for every follow-up message
2. restart safety drift
   - do not interrupt tasks after external side effects without an explicit safe path
3. invisible automation
   - never ship routing automation without `[wd]`
4. boundary drift into planner-first behavior
   - keep routing classifier small and runtime-owned

### 9. Definition of done

This subproject is done only when:

- the design packet is fully implemented
- all core cases in [test_cases.md](./test_cases.md) have test coverage
- ambiguous cases are handled through runtime-owned classifier calls
- `[wd]` routing receipts are stable and human-readable
- docs and roadmap are updated to reflect shipped behavior

## 中文

### 1. 目的

这份文档把 same-session message routing 的设计稿进一步整理成一份可执行的子项目开发计划。

它应该作为后续持续推进这条子项目的工作清单来使用，直到整个子项目完成。

当前状态：

- 已实现到 Phase 8
- 这份文档现在保留为该子项目的交付记录

默认前提：

- 设计稿已经进入 review
- [decision_contract.md](./decision_contract.md) 里的核心 contract 已被接受
- [test_cases.md](./test_cases.md) 里的样例是后续实现与验收的基线

### 2. 完成目标

只有同时满足下面几条，这条子项目才能算完成：

1. 同一 session 的后续输入可以被正式路由到：
   - `control-plane`
   - `steering`
   - `queueing`
   - `collect-more`
2. runtime 可以正式决定：
   - `merge-before-start`
   - `interrupt-and-restart`
   - `append-as-next-step`
   - `queue-as-new-task`
   - `enter-collecting-window`
3. 歧义场景通过 runtime-owned structured LLM classifier 处理
4. 每一次自动路由都能返回 runtime-owned `[wd]` 回执
5. 行为有完整覆盖：
   - contract tests
   - classifier trigger tests
   - end-to-end session tests
6. roadmap、testsuite、usage、acceptance 文档都已同步到最终行为

### 3. 交付策略

这条子项目不适合一次性大 patch 落完。

推荐策略：

1. 先把 runtime contract 固定
2. 先做纯确定性的 rule-only 场景
3. 再补 execution-stage gate
4. 再补 `[wd]` routing receipts
5. 然后才引入 LLM classifier 处理歧义场景
6. 最后补 acceptance 和运维可见性

### 4. 分阶段计划

#### Phase 0. Review lock

目标：

- 在正式开做前，把设计 contract 锁住

交付物：

- review 过的 [README.md](./README.md)
- review 过的 [decision_contract.md](./decision_contract.md)
- review 过的 [test_cases.md](./test_cases.md)
- review 过的这份 [development_plan.md](./development_plan.md)

退出条件：

- decision taxonomy 被接受
- `[wd]` 回执风格被接受
- classifier 触发边界被接受
- interrupt/restart 安全边界被接受

#### Phase 1. Runtime routing truth source

目标：

- 把 same-session follow-up routing 做成正式 truth source

当前实现检查点：

- runtime 已开始把 same-session routing decision 记录进 task truth source 与 hook 输出
- 对仍等待剩余 `Phase 2` rule gate 的 same-session follow-up case，会明确标成 provisional
- 明显的 `control-plane` 与 `no-active-task` 场景，已经可以先落成结构化 decision

推荐交付物：

- 结构化 routing decision record
- reason code / reason text 字段
- target task / session references
- 显式 execution decision 字段

建议落点：

- producer/runtime state layer
- task truth source projection layer
- debug/event trace output

退出条件：

- routing decisions 成为一等结构化状态
- 不需要翻原始日志也能看到 decision

#### Phase 2. Deterministic rule path

目标：

- 先把不依赖 LLM 的明显路由场景正式落地

必须覆盖：

- 明显 `control-plane`
- 明显 `collect-more`
- 无 active task 的普通新消息
- active task 期间的明显独立新请求

推荐交付物：

- rule gate 实现
- 显式 “classifier not needed” 路径
- baseline rule-only tests

退出条件：

- 明显场景在不触发 classifier 的情况下能稳定路由
- 不破坏现有控制面行为

当前实现检查点：

- deterministic rules 已覆盖 obvious `control-plane`、`collect-more`、`no-active-task` 与明显独立新请求
- 模糊的 same-session follow-up 仍会先保持 provisional，等待 stage gate 或后续 classifier 路径继续判断

#### Phase 3. Execution-stage gate

目标：

- 把“消息语义”和“可安全执行动作”正式分开

必须覆盖的 gate：

- `received / queued` -> `merge-before-start`
- `running-no-side-effects` -> `interrupt-and-restart`
- `running-with-side-effects` -> `append-as-next-step` 或 `queue-as-new-task`
- `paused / continuation` -> bounded non-destructive handling

推荐交付物：

- 正式的 stage enum 或等价投影
- safe-restart gate
- side-effect-aware routing behavior

退出条件：

- `steering` 不再意味着固定一种执行动作
- runtime 能解释为什么是 merge、restart、append 或 queue

#### Phase 4. `[wd]` routing receipts

目标：

- 让每一次 routing decision 都对用户可见

当前实现检查点：

- runtime 已开始为 deterministic routing decision 产出 same-session routing receipt payload
- plugin 的 immediate-ack 路径现在会优先采用 runtime-owned receipt 文案，而不是本地兜底文案

必须覆盖：

- 各 decision 对应的 receipt template
- 简短、可读的 reason
- 只能由 runtime 渲染

推荐交付物：

- 代码里的 `[wd]` 模板表
- 结构化 receipt payload
- transcript / channel delivery tests

退出条件：

- 每个自动 routing decision 都能回给用户一条 `[wd]`
- 文案够短、够真、够具体

#### Phase 5. Runtime-owned LLM classifier

目标：

- 在不把系统带偏成前置语义分类器的前提下，处理歧义的 same-session follow-up message

当前实现检查点：

- runtime 已开始支持 config-driven 的 same-session classifier adapter，不再把 classifier ownership 交给主 LLM
- 只有 deterministic rules 失败后的歧义 same-session follow-up 才会进入 classifier candidate 路径
- classifier 未启用、报错、超时、低置信度时，现在都会走显式 runtime-owned safe fallback

必须覆盖：

- classifier input schema
- classifier output schema
- timeout / low-confidence fallback
- runtime-owned invocation path

明确非目标：

- 主 LLM 自由自发地 self-routing
- 每条消息都调用 classifier
- 用 classifier 替代主执行 LLM

退出条件：

- 歧义 case 能触发 classifier
- 低置信度结果有安全回退
- classifier ownership 明确留在 runtime

#### Phase 6. Collecting window

目标：

- 把“我还没发完，先别开始”做成正式一等能力

必须覆盖：

- session truth source 里的 collecting state
- 可配置的短 collecting window
- 后续消息没来时的 timeout 行为
- collect-more 激活时的 `[wd]`

退出条件：

- collect-more 成为正式状态，而不是一句松散短语
- batch start 行为可预测、可测试

#### Phase 7. End-to-end tests and acceptance

目标：

- 用真实多消息流证明整条 routing 模型成立

必须覆盖：

- pure contract tests
- classifier trigger tests
- end-to-end same-session flows
- receipt delivery tests

推荐 acceptance flow：

- 任务开始前补充说明
- 任务运行中但仍可安全重启时补充说明
- 当前任务执行时插入独立新任务
- 明确要求先收集后执行
- 有 active task 时发送 control-plane follow-up

退出条件：

- [test_cases.md](./test_cases.md) 里的 shipped 场景有测试覆盖
- acceptance 文档写清楚真实 channel 怎么验

当前实现检查点：

- end-to-end same-session flow 已进入 `same_session_routing_acceptance.py`
- stable acceptance 现已把 same-session routing acceptance 作为必跑步骤

#### Phase 8. Docs and operational rollout

目标：

- 让这条能力在上线后也可运维、可解释、可 review

必须覆盖的文档：

- roadmap
- testsuite
- usage guide
- 如果 runtime 边界变化明显，补 architecture
- 如果用户可见行为变化明显，补 acceptance/runbook

必须覆盖的 ops visibility：

- decision trace visibility
- classifier invocation visibility
- low-confidence / fallback visibility

退出条件：

- 维护者不看源码也能解释这条功能
- 运维能看清楚一次 routing decision 为什么发生

当前实现检查点：

- roadmap、testsuite、usage 文档都已同步到已交付行为
- acceptance 入口已通过 `same_session_routing_acceptance.py --json` 与 `stable_acceptance.py --json` 暴露

### 5. 推荐实现顺序

推荐顺序：

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6
7. Phase 7
8. Phase 8

原因：

- 先把 routing state 做成正式结构
- 再把确定性行为落地
- 再补用户可见回执
- 最后只在真正需要的地方引入 classifier

### 6. 建议代码切片

下面是比较可能的代码切片，不是硬性文件清单：

- producer contract / runtime routing state
- plugin receive-side decision path
- same-session task binding / routing metadata
- `[wd]` rendering path
- classifier invocation adapter
- contract tests 和 end-to-end session routing tests
- docs / runbooks

### 7. 测试计划

每个阶段最少测试期待：

| Phase | Minimum tests |
|---|---|
| 1 | truth-source contract tests |
| 2 | rule-only routing tests |
| 3 | execution-stage gate tests |
| 4 | `[wd]` receipt rendering and delivery tests |
| 5 | classifier trigger / fallback tests |
| 6 | collecting window state tests |
| 7 | end-to-end multi-message session tests |
| 8 | docs and acceptance sync check |

### 8. 主要风险

需要重点控住的风险：

1. classifier scope drift
   - 不要把 classifier 变成“每条 follow-up 都问一次”
2. restart safety drift
   - 已有外部副作用后，不要默认直接 interrupt
3. invisible automation
   - 没有 `[wd]` 就不要上线自动 routing
4. planner-first drift
   - classifier 必须小而受控，且 runtime-owned

### 9. Done 的定义

只有同时满足下面几条，这条子项目才能算 done：

- 设计稿已全部被实现
- [test_cases.md](./test_cases.md) 里的核心场景都有自动化覆盖
- 歧义场景已通过 runtime-owned classifier 处理
- `[wd]` routing receipt 已稳定、可读
- 文档和 roadmap 已与最终行为同步
