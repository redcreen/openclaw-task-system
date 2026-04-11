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

## Current Extension Areas

Remaining work is extension work, not unfinished mainline debt:

- broader planning anomaly coverage
- richer planning and channel acceptance samples
- additional operator UX and recovery depth
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
