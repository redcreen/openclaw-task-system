[English](roadmap.md) | [中文](roadmap.zh-CN.md)

# Roadmap

## Status

The mainline roadmap is complete through Phase 6 minimum closure and `Milestone 1: post-hardening closeout`.

A new named milestone is now active:

- `Milestone 2: Growware Project 1 pilot foundation`

Completed mainline milestones:

- Phase 0: project definition and boundaries
- Phase 1: protocol and truth-source alignment
- Phase 2: minimum control-plane lane and scheduler evidence
- Phase 3: unified user-facing status projection
- Phase 4: producer contract and same-session semantics
- Phase 5: channel rollout and acceptance
- Phase 6 minimum closure: supervisor-first planning runtime
- Milestone 1: post-hardening closeout

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

## Growware Pilot Snapshot

Delivered so far:

- `.growware/` is now the durable project-local control surface for Growware `Project 1`, with `feishu6-chat` as the primary feedback / approval / notification ingress
- `docs/policy/*.md` is now the human policy source and `.policy/` is the compiled machine layer for Growware runtime decisions
- `growware_feedback_classifier.py`, `growware_project.py`, `growware_preflight.py`, and `growware_local_deploy.py` now consume or enforce the compiled policy layer
- `openclaw_runtime_audit.py` now provides a read-only host-side audit bootstrap for real `~/.openclaw` data

Open edges before activation:

- close the remaining source-of-truth gap between compiled `.policy/` and legacy `.growware/policies/*.json`
- prove one clean activation baseline across policy sync, preflight, binding preview, runtime mirror, doctor / smoke, and session hygiene
- decide whether the read-only host audit is sufficient for Milestone 2 or whether repair planning should become the next named milestone

## Current / Next / Later

| Horizon | Focus | Exit Signal |
| --- | --- | --- |
| Current | close `Milestone 2: Growware Project 1 pilot foundation` by converging policy truth, pilot activation safety, and host-side audit positioning | compiled `.policy` is the only live intake / deploy truth, activation checks stay green, and operators have one documented baseline command set |
| Next | activate the local feedback -> code -> verify -> deploy pilot on `feishu6-chat` only after the foundation gate is clean | binding preview, session hygiene, and local deploy can be rehearsed without unresolved drift or host-side blockers |
| Later | consider conservative self-heal and broader planning / steering only after the pilot baseline is stable | new work does not reopen hidden ownership drift or bypass runtime truth |

## Milestones

| Milestone | Status | Objective | Dependencies | Exit Condition |
| --- | --- | --- | --- | --- |
| Phase 0-2 | complete | establish the base task runtime, registration, state, and minimum control-plane behavior | plugin/runtime baseline wiring | long tasks use one task truth source |
| Phase 3-4 | complete | add delayed reply, watchdog, continuity, and host delivery | continuity and scheduler evidence chain | restart and recovery flows are explainable |
| Phase 5 | complete | strengthen dashboard, queues, lanes, triage, and operator projections | main ops toolchain | user and operator views project the same truth |
| Phase 6 minimum closure | complete | lock planning acceptance, future-first output, and same-session routing into a minimum shipped closure | planning acceptance toolchain | automation and semi-real acceptance stay green |
| Milestone 1: post-hardening closeout | complete | close the remaining compound / future-first boundary work, deepen release-facing evidence, and finish operator-facing closeout | current mainline stability and release-facing validation entrypoints | boundary docs, acceptance depth, and operator / release-facing closeout are converged without reopening architecture debt |
| Milestone 2: Growware Project 1 pilot foundation | active | turn Growware `Project 1` from a future candidate into a durable repo-owned baseline by shipping project-local policy truth, activation gates, and host-audit bootstrap | `.growware/`, `docs/policy/`, `.policy/`, Growware runtime scripts, binding preview, session hygiene, and validation entrypoints | project-local policy is the only live runtime input, activation safety is documented and green, and the host-audit bootstrap has a clear milestone boundary |

## Future Candidate Areas

`Milestone 2` is active now. Do not treat Growware pilot foundation as ambient follow-up.

Potential later candidates after Milestone 2:

- live Growware pilot activation and real end-to-end evidence capture across `feishu6-chat`
- conservative host-side repair planning / self-heal on top of `openclaw_runtime_audit.py`
- stronger structured planning or tool decomposition for broader compound requests
- richer real-channel evidence refreshes when delivery or planning contracts change
- deeper steering or operator ergonomics that still preserve runtime truth and supervisor-first boundaries

The architecture hardening line remains closed with two explicit decisions:

- `lifecycle_coordinator.py` owns runtime lifecycle projection
- `scripts/runtime/` is canonical and `plugin/scripts/runtime/` is a strict synchronized mirror

Reference:

- [workstreams/architecture-hardening/README.md](workstreams/architecture-hardening/README.md)
- [reference/openclaw-task-system/development-plan.md](reference/openclaw-task-system/development-plan.md#milestone-2-growware-project-1-pilot-foundation)
- [reference/openclaw-task-system/growware-pilot.md](reference/openclaw-task-system/growware-pilot.md)
- [reference/openclaw-task-system/runtime-audit-self-heal-proposal.md](reference/openclaw-task-system/runtime-audit-self-heal-proposal.md)

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
