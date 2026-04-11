# Development Plan

[English](development_plan.md) | [中文](development_plan.zh-CN.md)

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
