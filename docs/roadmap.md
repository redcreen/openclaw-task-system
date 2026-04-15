[English](roadmap.md) | [中文](roadmap.zh-CN.md)

# Roadmap

## Status

The mainline roadmap is complete through Phase 6 minimum closure and `Milestone 1: post-hardening closeout`.

The milestone state has now shifted to:

- `Milestone 2: Growware Project 1 pilot foundation` complete
- `Milestone 3: system performance testing and optimization` complete
- `reply-latency and context-weight governance` active

## Overall Progress

| Item | Current Value |
| --- | --- |
| Mainline Progress | Mainline is complete through `Milestone 3`; the repo has moved into reply-latency and context-weight governance before activation prep resumes |
| Current Phase | `reply-latency and context-weight governance` |
| Current Objective | turn the measured Telegram slowdown into durable repo truth, add repeatable session-latency audits, and bound the biggest context contributors before activation prep returns |
| Clear Next Move | `TG-1` freeze the slowdown trigger and add a reusable session-latency audit command |
| Next Candidate Move | resume bounded `feishu6-chat` activation preparation after context budgets and resume criteria are explicit |

See the detailed execution plan: [reference/openclaw-task-system/development-plan.md](reference/openclaw-task-system/development-plan.md)

Completed mainline milestones:

- Phase 0: project definition and boundaries
- Phase 1: protocol and truth-source alignment
- Phase 2: minimum control-plane lane and scheduler evidence
- Phase 3: unified user-facing status projection
- Phase 4: producer contract and same-session semantics
- Phase 5: channel rollout and acceptance
- Phase 6 minimum closure: supervisor-first planning runtime
- Milestone 1: post-hardening closeout
- Milestone 2: Growware Project 1 pilot foundation
- Milestone 3: system performance testing and optimization

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

## Milestone 2 Closeout

Milestone 2 is now closed with these durable outcomes:

- `.growware/` is the durable project-local control surface for Growware `Project 1`, with `feishu6-chat` as the primary feedback / approval / notification ingress
- `docs/policy/*.md` is the human policy source and `.policy/` is the compiled machine layer for Growware runtime decisions
- `growware_feedback_classifier.py`, `growware_project.py`, `growware_preflight.py`, and `growware_local_deploy.py` are converged on the compiled policy layer
- legacy `.growware/policies/*.json` has been retired from the live control surface and is no longer required by runtime or preflight
- `openclaw_runtime_audit.py` remains a read-only host-side bootstrap instead of expanding into a repair or rollout gate
- the reviewed activation baseline has been rerun successfully on the compiled `.policy/` path

## Milestone 3 Closeout

Milestone 3 is now closed with these durable outcomes:

- `scripts/runtime/performance_baseline.py` defines one reproducible repo-local benchmark / profile contract for runtime, control-plane, and operator surfaces
- `docs/reference/openclaw-task-system/performance-baseline*.md` records fixtures, budgets, hotspot attribution, and the measured optimization path instead of leaving performance work in ad-hoc command output
- the reviewed hotspot cuts are now durable repo truth: `system-overview` moved from roughly `484ms` median to about `18ms`, registration rescans collapsed to one inflight snapshot on the hot path, and the repo-owned same-session classifier moved from about `90ms` / `132ms` to about `25ms` / `39ms`
- structural regression checks and benchmark budgets now protect the improved paths without reopening runtime truth or control-surface drift
- installed-runtime drift remains visible in `plugin_doctor.py`, but it stays a separate activation-prep decision instead of a hidden blocker inside the repo-local performance milestone

## Current Governance Topic

The active mainline is now a dedicated reply-latency governance topic, because a real Telegram session after `2026-04-15 23:44` still showed `16s-50s` reply latency even though the repo-local performance baseline remained green.

The durable trigger evidence is:

- dominant latency in LLM segments rather than task-system hooks
- static context around `140,465 chars`
- tool schema surface as the largest static block
- per-turn wrapper payloads around `1.5k chars`
- startup and transcript carryover that increase later-turn cost

The repo now owns a repeatable audit entrypoint for that evidence:

- `python3 scripts/runtime/session_latency_audit.py --session-key 'agent:main:telegram:direct:8705812936' --json`

See the detailed governance plan: [reference/openclaw-task-system/reply-latency-governance.md](reference/openclaw-task-system/reply-latency-governance.md)

## Current / Next / Later

| Horizon | Focus | Exit Signal |
| --- | --- | --- |
| Current | execute `reply-latency and context-weight governance` on top of the closed benchmark baseline | slowdown evidence is rerunnable, top prompt/context contributors are ranked, and activation resume criteria are explicit |
| Next | return to bounded `feishu6-chat` activation preparation | activation entry criteria, operator evidence expectations, and install-sync decisions are explicit before any bounded live rehearsal |
| Later | consider conservative self-heal, stronger planning / steering, and richer real-channel evidence | new work does not reopen policy-ownership drift or bypass runtime truth and approval boundaries |

## Milestones

| Milestone | Status | Objective | Dependencies | Exit Condition |
| --- | --- | --- | --- | --- |
| Phase 0-2 | complete | establish the base task runtime, registration, state, and minimum control-plane behavior | plugin/runtime baseline wiring | long tasks use one task truth source |
| Phase 3-4 | complete | add delayed reply, watchdog, continuity, and host delivery | continuity and scheduler evidence chain | restart and recovery flows are explainable |
| Phase 5 | complete | strengthen dashboard, queues, lanes, triage, and operator projections | main ops toolchain | user and operator views project the same truth |
| Phase 6 minimum closure | complete | lock planning acceptance, future-first output, and same-session routing into a minimum shipped closure | planning acceptance toolchain | automation and semi-real acceptance stay green |
| Milestone 1: post-hardening closeout | complete | close the remaining compound / future-first boundary work, deepen release-facing evidence, and finish operator-facing closeout | current mainline stability and release-facing validation entrypoints | boundary docs, acceptance depth, and operator / release-facing closeout are converged without reopening architecture debt |
| Milestone 2: Growware Project 1 pilot foundation | complete | turn Growware `Project 1` from a future candidate into a durable repo-owned baseline by shipping project-local policy truth, activation gates, and host-audit bootstrap | `.growware/`, `docs/policy/`, `.policy/`, Growware runtime scripts, binding preview, session hygiene, and validation entrypoints | project-local policy is the only live runtime input, activation safety is documented and green, and the host-audit bootstrap has a clear milestone boundary |
| Milestone 3: system performance testing and optimization | complete | build reproducible performance baselines for runtime, control-plane, and operator entrypoints, then optimize the measured hotspots | Milestone 2 closeout, stable baseline commands, reproducible sample data, and performance measurement helpers | benchmark and profile baselines exist, the main hotspots are attributed, optimizations are verified, and regression gates protect the improved paths |

## Future Candidate Areas

Potential later candidates after the current governance line:

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
- [reference/openclaw-task-system/development-plan.md](reference/openclaw-task-system/development-plan.md)
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
