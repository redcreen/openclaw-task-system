[English](roadmap.md) | [中文](roadmap.zh-CN.md)

# Roadmap

## Status

The mainline roadmap is complete through Phase 6 minimum closure.

Completed:

- Phase 0: project definition and boundaries
- Phase 1: protocol and truth-source alignment
- Phase 2: minimum control-plane lane and scheduler evidence
- Phase 3: unified user-facing status projection
- Phase 4: producer contract and same-session semantics
- Phase 5: channel rollout and acceptance
- Phase 6 minimum closure: supervisor-first planning runtime

For the full Chinese detail, see [roadmap.zh-CN.md](roadmap.zh-CN.md).

## Mainline Outcomes

The mainline shipped these outcomes:

- runtime-owned `[wd]` and control-plane delivery
- unified queue identity and task truth source
- channel acceptance matrix and producer contract
- same-session message routing
- planning minimum closure with future-first output control
- continuity, watchdog, and recovery visibility
- install drift visibility in doctor, ops, and stable acceptance

## Current / Next / Later

| Horizon | Focus | Exit Signal |
| --- | --- | --- |
| Current | keep Phase 0-6 and the hardening closeout stable | the testsuite, release gate, and dated evidence workflow stay green |
| Next | execute one post-hardening closeout milestone as a single long-task line | compound/future-first boundary work, evidence depth, and operator-facing closeout converge without reopening architecture debt |
| Later | evaluate stronger planning or steering capability without replacing the original executor path | new capability still preserves `[wd]` independence, runtime truth, and supervisor-first boundaries |

## Milestones

| Milestone | Status | Objective | Dependencies | Exit Condition |
| --- | --- | --- | --- | --- |
| Phase 0-2 | complete | establish the base task runtime, registration, state, and minimum control-plane behavior | plugin/runtime baseline wiring | long tasks use one task truth source |
| Phase 3-4 | complete | add delayed reply, watchdog, continuity, and host delivery | continuity and scheduler evidence chain | restart and recovery flows are explainable |
| Phase 5 | complete | strengthen dashboard, queues, lanes, triage, and operator projections | main ops toolchain | user and operator views project the same truth |
| Phase 6 minimum closure | complete | lock planning acceptance, future-first output, and same-session routing into a minimum shipped closure | planning acceptance toolchain | automation and semi-real acceptance stay green |
| Milestone 1: post-hardening closeout | next long task | close the remaining compound/future-first boundary work, deepen release-facing evidence, and finish operator-facing closeout | current mainline stability and release-facing validation entrypoints | remaining work is either shipped, archived, or moved into a new explicit roadmap candidate |

## Current Extension Areas

Remaining work is extension work, not unfinished mainline debt:

- broader planning anomaly coverage
- richer planning and channel acceptance samples
- additional operator UX and recovery depth

The architecture hardening line is now closed with two explicit decisions:

- `lifecycle_coordinator.py` owns runtime lifecycle projection
- `scripts/runtime/` is canonical and `plugin/scripts/runtime/` is a strict synchronized mirror

Reference:

- [workstreams/architecture-hardening/README.md](workstreams/architecture-hardening/README.md)
- [reference/openclaw-task-system/development-plan.md](reference/openclaw-task-system/development-plan.md)
- future roadmap candidates under workstreams and todo tracking

## Delivered Subproject: Same-Session Message Routing

This shipped capability defines how consecutive messages in the same session are routed across:

- `steering`
- `queueing`
- `control-plane`
- `collect-more`

Runtime behavior:

1. runtime evaluates current task state first
2. only ambiguous cases invoke a runtime-owned structured classifier
3. runtime then chooses actions such as:
   - `merge-before-start`
   - `interrupt-and-restart`
   - `append-as-next-step`
   - `queue-as-new-task`
   - `enter-collecting-window`
4. every routing decision returns a runtime-owned `[wd]` receipt

Entry points:

- [reference/session_message_routing/README.md](reference/session_message_routing/README.md)
- [reference/session_message_routing/decision_contract.md](reference/session_message_routing/decision_contract.md)
- [reference/session_message_routing/test_cases.md](reference/session_message_routing/test_cases.md)
- [reference/session_message_routing/development_plan.md](reference/session_message_routing/development_plan.md)

## Working Rule

`docs/todo.md` is a temporary intake file.

The canonical delivery line remains this roadmap.
