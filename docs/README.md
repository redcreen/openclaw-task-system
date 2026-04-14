# Docs Home

[English](README.md) | [中文](README.zh-CN.md)

## Start Here

Use the canonical stack below first. Everything else in `docs/` should either deepen, operationalize, or archive those primary answers.

## Canonical Stack

Start with these documents:

- [../README.md](../README.md): project overview and shipped capability map
- [roadmap.md](roadmap.md): main delivery line and shipped boundaries
- [architecture.md](architecture.md): runtime model and truth-source contracts
- [test-plan.md](test-plan.md): release gate and acceptance expectations

## By Goal

| Goal | Read This |
| --- | --- |
| Understand what the project ships today | [../README.md](../README.md) |
| Understand runtime layers and contracts | [architecture.md](architecture.md) |
| See what is complete vs extension work | [roadmap.md](roadmap.md) |
| Understand how release confidence is established | [test-plan.md](test-plan.md) |
| Find project-local policy source and compiled machine layer | [policy/README.md](policy/README.md) |
| Find detailed runtime and operator commands | [usage_guide.md](usage_guide.md) |
| Find install details and install drift notes | [plugin_installation.md](plugin_installation.md) |
| Find durable design references | [reference/README.md](reference/README.md) |

## Feature Index

- same-session routing: [reference/session_message_routing/README.md](reference/session_message_routing/README.md)
- project-local policy source: [policy/README.md](policy/README.md)
- planning and future-first boundary: [llm_tool_task_planning.md](llm_tool_task_planning.md)
- compound delayed boundary: [compound_followup_boundary.md](compound_followup_boundary.md)
- channel and continuation lane decisions: [continuation_lane_decision_log.md](continuation_lane_decision_log.md), [output_channel_separation_decision_log.md](output_channel_separation_decision_log.md)
- external comparison and architecture framing: [external_comparison.md](external_comparison.md)

## Directory Roles

- [reference/README.md](reference/README.md): durable contracts, deeper design references, and stable facts that are too specific for the landing stack
- [workstreams/README.md](workstreams/README.md): active investigations or retrofit tracks that have not yet converged into the main docs stack
- [archive/README.md](archive/README.md): dated evidence, superseded plans, and historical records kept for traceability
- [devlog/README.md](devlog/README.md): durable implementation narratives for non-obvious decisions, regressions, and fixes

Archive is for historical acceptance records, handoff notes, and superseded cleanup plans that should remain available without crowding the active docs stack.

## Markdown Governance

Keep one primary question per page and place it in the narrowest stable directory that still matches its role:

- landing docs stay at the repo root or `docs/`
- durable references live under [reference/](reference/README.md)
- active retrofit notes live under [workstreams/](workstreams/README.md) until they converge
- dated evidence and superseded material move to [archive/](archive/README.md)
- implementation reasoning with durable value belongs in [devlog/](devlog/README.md)
