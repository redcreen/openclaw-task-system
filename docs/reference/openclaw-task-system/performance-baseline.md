[English](performance-baseline.md) | [中文](performance-baseline.zh-CN.md)

# Milestone 3 Performance Baseline

## What This Is

This document is the first benchmark contract for `Milestone 3: system performance testing and optimization`.

The goal is not a machine-independent user SLA. The goal is to freeze reproducible, attributable, regression-safe repo-local measurement entrypoints first.

The first baseline only covers repo-local, fixture-controlled runtime and operator surfaces. It intentionally excludes host-install drift and broader OpenClaw host state from the first budget layer.

## First Benchmark Surface

| Surface | Scenario | Entrypoint | Fixed Fixture | Current Budget |
| --- | --- | --- | --- | --- |
| runtime lifecycle hooks | `hooks-cycle` | [`scripts/runtime/performance_baseline.py`](../../../scripts/runtime/performance_baseline.py) | temp task root with 24 active + 32 archived tasks | median `45ms`, p95 `60ms` |
| same-session rule path | `same-session-routing-rule` | same entrypoint | one in-memory running task | median `0.05ms`, p95 `0.1ms` |
| same-session classifier path | `same-session-routing-classifier` | same entrypoint | 16 active + 16 archived tasks plus a classifier-enabled temp config | median `115ms`, p95 `150ms` |
| control-plane / operator projection | `system-overview` | same entrypoint | 48 active + 96 archived tasks plus planning / delivery artifacts | median `35ms`, p95 `50ms` |
| Growware preflight | `growware-preflight` | same entrypoint | current repo root | median `8ms`, p95 `15ms` |
| plugin smoke | `plugin-smoke` | same entrypoint | one fresh temp task root per iteration | median `20ms`, p95 `30ms` |

Budget rules:

- These budgets are repo-local guardrails, not cross-machine SLAs.
- They are derived from the current baseline with explicit headroom, so the first job is regression protection rather than squeezing absolute minimum numbers.
- `plugin_doctor.py`, the full `main_ops.py dashboard` surface, and host-install drift are intentionally deferred from the first gate because they still mix in host-environment variance. Add them only after repo-local and host-local cost are separated cleanly.

## Command Entrypoints

Run the full first-surface benchmark:

```bash
python3 scripts/runtime/performance_baseline.py --json
```

Run the regression gate with profiles:

```bash
python3 scripts/runtime/performance_baseline.py \
  --profile-scenario hooks-cycle \
  --profile-scenario same-session-routing-classifier \
  --profile-scenario system-overview \
  --profile-top 8 \
  --enforce-budgets \
  --json
```

Focus on one hotspot:

```bash
python3 scripts/runtime/performance_baseline.py \
  --scenario system-overview \
  --profile-scenario system-overview \
  --json
```

## First Baseline (2026-04-14)

Reviewed baseline command:

```bash
python3 scripts/runtime/performance_baseline.py \
  --profile-scenario hooks-cycle \
  --profile-scenario same-session-routing-classifier \
  --profile-scenario system-overview \
  --profile-top 8 \
  --enforce-budgets \
  --json
```

Current results:

| Scenario | Median | p95 | Reading |
| --- | --- | --- | --- |
| `hooks-cycle` | `30.716ms` | `37.628ms` | runtime lifecycle path now has a durable budget |
| `same-session-routing-rule` | `0.0084ms` | `0.0088ms` | the rule-only path is not the current bottleneck |
| `same-session-routing-classifier` | `91.4245ms` | `96.8046ms` | current cost is dominated by classifier subprocess + inflight lookup |
| `system-overview` | `17.5673ms` | `19.5657ms` | the first optimization moved this path into a stable guardrail |
| `growware-preflight` | `1.2168ms` | `1.7194ms` | repo-local preflight cost is low |
| `plugin-smoke` | `11.5485ms` | `13.6066ms` | smoke is not a current pressure point |

## First Hotspot Attribution

The first clear hotspot was `system-overview`.

Before optimization, on the same reviewed fixture, it measured roughly:

- median `484.315ms`
- p95 `494.1653ms`

The profile showed the fanout clearly:

- `build_system_overview`
- `build_status_summary`
- `build_queue_snapshot`
- `_build_base_status_summary`

On 48 inflight tasks, `_build_base_status_summary` ran 2352 times because the same inflight set was re-expanded for every task.

## First Landed Optimization

The first optimization is now in [`scripts/runtime/task_status.py`](../../../scripts/runtime/task_status.py):

- `list_inflight_statuses` and `build_system_overview` preload inflight base status once
- the same inflight batch reuses one queue snapshot instead of rebuilding it per task
- `build_status_summary` also reuses the shared inflight base-status batch for the single-task path

On the same hotspot and fixture after the change:

- median `17.5673ms`
- p95 `19.5657ms`

That is about a `27x` improvement, which is strong enough to count as Milestone 3's first evidence-backed optimization.

## Baseline Refresh After The Second Optimization (2026-04-14)

Once the first `system-overview` fix landed, the next profiles exposed two more concrete hotspots:

- repeated cold inflight reads across helper and hook boundaries inside `hooks-cycle`
- tail latency inside `system-overview` caused by repeated planning-time conversion plus delivery-artifact `stat` scans

Reviewed command:

```bash
python3 scripts/runtime/performance_baseline.py \
  --profile-scenario hooks-cycle \
  --profile-scenario same-session-routing-classifier \
  --profile-scenario system-overview \
  --profile-top 12 \
  --enforce-budgets \
  --json
```

Reviewed results:

| Scenario | Median | p95 | Reading |
| --- | --- | --- | --- |
| `hooks-cycle` | `20.5577ms` | `34.4193ms` | the hook path is back inside budget with substantial room |
| `same-session-routing-rule` | `0.0039ms` | `0.0043ms` | the rule-only path stays negligible |
| `same-session-routing-classifier` | `20.3786ms` | `32.1622ms` | inflight lookup is no longer the dominant cost and the subprocess path is back inside budget |
| `system-overview` | `14.574ms` | `17.1183ms` | the second tail-latency cut moved this path below the first reviewed baseline |
| `growware-preflight` | `1.2391ms` | `3.4425ms` | still not a pressure point |
| `plugin-smoke` | `11.2371ms` | `16.0221ms` | smoke remains stable |

## Second Landed Optimization

The second optimization landed in three layers:

- [`scripts/runtime/task_state.py`](../../../scripts/runtime/task_state.py) now promotes inflight snapshots to same-process, cross-`TaskStore` reuse with generation-based invalidation, so hook / bridge / adapter paths stop rereading the same inflight files repeatedly
- [`scripts/runtime/openclaw_hooks.py`](../../../scripts/runtime/openclaw_hooks.py), [`scripts/runtime/lifecycle_coordinator.py`](../../../scripts/runtime/lifecycle_coordinator.py), [`scripts/runtime/openclaw_bridge.py`](../../../scripts/runtime/openclaw_bridge.py), and [`scripts/runtime/main_task_adapter.py`](../../../scripts/runtime/main_task_adapter.py) now thread one `TaskStore` through register / progress / finalize-active flows instead of rebuilding store and queue views along the way
- [`scripts/runtime/task_status.py`](../../../scripts/runtime/task_status.py) now reuses one batch-level `now_dt` and a one-time delivery-artifact directory index, removing repeated `astimezone` and `stat` overhead from planning and delivery projection

## Baseline Refresh After The Third Optimization (2026-04-14)

Once repeated inflight rescans were collapsed, the next focused profile made the remaining repo-owned classifier cost explicit:

- the Growware same-session natural-language follow-up path still spawned `python3 scripts/runtime/growware_feedback_classifier.py` as a fresh subprocess every time
- the dominant profile cost shifted away from inflight lookup and into classifier process startup plus the task-state / ETA reads that still sit behind the classifier decision

Focused follow-up command:

```bash
python3 scripts/runtime/performance_baseline.py \
  --profile-scenario hooks-cycle \
  --profile-scenario same-session-routing-classifier \
  --profile-top 8 \
  --json
```

Reviewed classifier-path results on the same fixture:

- before the in-process fast path: median `90.0957ms`, p95 `132.2014ms`
- after the in-process fast path: median `24.9839ms`, p95 `38.5312ms`

That turns the repo-owned classifier path into a roughly `3.6x` median improvement without changing the behavior contract for custom classifier commands.

## Third Landed Optimization

The third optimization stays intentionally narrow:

- [`scripts/runtime/openclaw_hooks.py`](../../../scripts/runtime/openclaw_hooks.py) now detects when the configured same-session classifier command resolves to the repo-owned `growware_feedback_classifier.py` under the current runtime root
- that known local command is now executed in-process through `growware_feedback_classifier.classify(...)` instead of paying subprocess startup for every follow-up classification
- custom classifier commands still keep the existing `subprocess.run(...)` path, so the optimization does not silently broaden into a generic command-execution change
- `register_from_payload` now reuses the already-loaded runtime config when it hands off to inbound lifecycle registration, avoiding one more local config reload on the same hot path

## Regression Protection

The protection layer now has both benchmark and structural checks:

- [`tests/test_task_status.py`](../../../tests/test_task_status.py) explicitly asserts that `list_inflight_statuses` and `build_system_overview` load each inflight task only once
- [`tests/test_task_state.py`](../../../tests/test_task_state.py) protects `TaskStore` inflight-cache reuse, cross-store snapshot sharing, and write-path invalidation
- [`tests/test_openclaw_bridge.py`](../../../tests/test_openclaw_bridge.py) asserts that same-process task registration reuses one inflight snapshot / store instead of rebuilding queue state repeatedly
- [`tests/test_main_task_adapter.py`](../../../tests/test_main_task_adapter.py) protects update paths that should reuse the caller's `TaskStore`
- [`tests/test_openclaw_hooks.py`](../../../tests/test_openclaw_hooks.py) asserts that the repo-owned Growware classifier path stays in-process and does not fall back to subprocess spawn
- [`tests/test_performance_baseline.py`](../../../tests/test_performance_baseline.py) validates the benchmark and profile entrypoints themselves

## Milestone 3 Closeout Signal

Milestone 3 can now close on benchmark evidence instead of intuition:

- the repo owns one reproducible benchmark / profile contract with fixed fixtures, budgets, and reviewed commands
- the most visible reviewed hotspots now have before / after evidence rather than hand-wavy “seems faster” claims
- the improved paths are protected by both benchmark budgets and structural tests
- the reviewed repo-local validation baseline stays green while installed-runtime drift remains visible as a separate activation-prep concern

## Carry-Forward Candidates After Closeout

The remaining measured candidates now become carry-forward topics instead of Milestone 3 blockers:

- the remaining `hooks-cycle` cost in active-task resolution and archive-backed ETA sampling after registration rescans and repo-owned classifier subprocess startup were removed from the main path
- `system-overview` tail variance from archive / projection fanout, which can still spike above its `50ms` p95 budget on noisy runs even after the first two structural cuts
- a second-surface expansion for the repo-local portions of `main_ops` / `plugin_doctor` once host-state noise is isolated
