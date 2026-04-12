# Architecture Retrofit

## Trigger

- Tier: `medium`
- Active Slice: `runtime source-of-truth convergence`
- Current Execution Line: formalize `scripts/runtime/` as the canonical editable runtime tree, make `plugin/scripts/runtime/` a strict synchronized mirror, and close architecture hardening with explicit tooling and docs
- Architecture Signal: `green`
- Escalation Gate: `continue automatically`

## Primary Symptoms

- lifecycle ownership had already improved, but runtime source ownership was still ambiguous
- maintainers could still read `scripts/runtime/` and `plugin/scripts/runtime/` as peer-owned trees
- the mirror rule existed as drift tooling, but not yet as a clearly stated architecture decision
- the architecture signal stayed yellow because ownership clarity had not caught up with the actual runtime tooling

## Root-Cause Drivers

- Root Cause Hypothesis: once lifecycle coordination was centralized, the remaining debt lived in ownership ambiguity between the canonical source tree and the install payload mirror
- Signal Basis: the repo had mirror tooling, but ownership was not yet encoded consistently in docs, install flow, doctor, and control surfaces
- Correct Layer: runtime mirror tooling, install/doctor/test entrypoints, architecture docs, and control surfaces
- Rejected Shortcut: keep treating `plugin/scripts/runtime/` as a peer source and rely on drift checks without declaring a single canonical tree

## Affected Boundaries

- control surface (`.codex/plan.md`, `.codex/status.md`, `.codex/brief.md`)
- canonical architecture ownership (`docs/architecture*.md` and doc-governance question owners)
- execution slices and architecture supervision state
- tests and validation gates that enforce the intended architecture
- legacy or competing architecture documents that need demotion, merge, move, or archive

## Current Architecture Sources

- Canonical Owners:
- docs/architecture.md
- docs/architecture.zh-CN.md
- Additional Architecture-Like Docs:
- docs/workstreams/architecture-hardening/README.md
- docs/workstreams/architecture-hardening/README.zh-CN.md

## Current Risks / Open Decisions

- none currently.

## Target Architecture

- `scripts/runtime/` is the only canonical editable runtime tree
- `plugin/scripts/runtime/` is a strict synchronized mirror for the installable plugin payload
- `runtime_mirror.py --check`, `plugin_doctor.py`, `scripts/install_remote.sh`, and `./scripts/run_tests.sh` all enforce that mirror rule
- docs, control surfaces, progress outputs, and workstream notes all describe the same ownership model

## Retrofit Scope

- keep lifecycle projection ownership in `lifecycle_coordinator.py`
- make runtime source ownership explicit instead of convention-only
- align docs, control surfaces, install flow, doctor output, and tests to the same canonical-source rule
- leave the repo ready to resume feature work from a hardened boundary model

## Execution Strategy

- refresh the architecture working note and `.codex/*` around runtime source ownership
- make the canonical-source rule explicit in README, architecture docs, roadmap, workstream docs, and plugin maintainer docs
- surface the mirror rule in `plugin_doctor.py` and fail installation early if the mirror is stale
- rerun deep gates and the full repo testsuite to close the architecture signal

## Validation

- `python3 /Users/redcreen/.codex/skills/project-assistant/scripts/validate_gate_set.py /Users/redcreen/Project/openclaw-task-system --profile deep` passes
- `bash /Users/redcreen/Project/openclaw-task-system/scripts/run_tests.sh` passes
- architecture signal is green
- progress and handoff reflect the corrected architecture signal and active execution line

## Exit Conditions

- runtime source ownership is explicit and enforceable
- lifecycle ownership and runtime source ownership no longer compete as unresolved architecture debts
- execution slices and control-surface artifacts reflect the corrected layer and root cause
- the retrofit leaves the repo ready to resume feature work from a cleaner boundary model

## Usable Now

- 恢复当前状态与下一步
- 长任务执行线与可见任务板
- 默认架构监督与升级 gate
- 文档整改与 Markdown 治理
- 公开文档中英文切换
