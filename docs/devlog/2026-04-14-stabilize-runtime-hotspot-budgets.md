# Stabilize Runtime Hotspot Budgets

## Problem

After the registration-rescan slice landed, the benchmark contract was better but not yet stable:

- `hooks-cycle` still paid repeated inflight cold reads when different helpers rebuilt fresh `TaskStore` instances inside the same lifecycle
- `system-overview` still had a long tail because planning summaries kept recomputing `now` and delivery projection kept issuing repeated file-existence probes
- benchmark medians were already down, but the reviewed gate could still miss on p95 for reasons that were now mostly runtime structure and filesystem overhead

Milestone 3 needed the budget line to be durable again before moving on to a third hotspot.

## Key Thinking

The right cut was not a budget change.

It was to remove the remaining redundant work that the second profile made explicit:

- share inflight snapshots across `TaskStore` instances in the same process
- keep active hook lifecycles on one store instead of resolving the same task through nested fresh stores
- move planning time and delivery artifact discovery to batch scope so overview code stops paying per-task control-plane overhead

This keeps the benchmark contract intact and makes the next hotspot ranking cleaner.

## Solution

Stabilized the measured paths in four layers:

1. cross-store inflight reuse
- `task_state.py` now keeps a same-process inflight snapshot cache keyed by inflight root plus generation
- write paths still invalidate that cache, so shared reuse does not survive state changes

2. active hook store threading
- `openclaw_hooks.py`, `lifecycle_coordinator.py`, `openclaw_bridge.py`, and `main_task_adapter.py` now thread one `TaskStore` through register / progress / finalize-active flows
- this removes repeated store construction and queue re-resolution in the same lifecycle

3. control-plane tail trimming
- `task_status.py` now computes one batch-level `now_dt` for planning summaries
- the same file also builds one delivery-artifact index up front and uses set membership instead of repeated `Path.exists()` fanout

4. structural protection
- `tests/test_task_state.py` now protects cross-store inflight snapshot reuse and invalidation
- `tests/test_main_task_adapter.py` now protects update paths that are expected to reuse the caller store

## Validation

- `python3 scripts/runtime/performance_baseline.py --profile-scenario hooks-cycle --profile-scenario same-session-routing-classifier --profile-scenario system-overview --profile-top 12 --enforce-budgets --json`
- `PYTHONPATH="$PWD:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}" python3 -m unittest tests.test_task_state tests.test_task_status tests.test_main_task_adapter tests.test_openclaw_bridge tests.test_openclaw_hooks tests.test_main_ops tests.test_performance_baseline -v`

Reviewed green benchmark sample:

- `hooks-cycle`: median `20.5577ms`, p95 `34.4193ms`
- `same-session-routing-classifier`: median `20.3786ms`, p95 `32.1622ms`
- `system-overview`: median `14.574ms`, p95 `17.1183ms`
- `plugin-smoke`: median `11.2371ms`, p95 `16.0221ms`

## Follow-Up

With the benchmark line green again, the next performance choice is narrower:

- decide whether the next slice should attack archive-backed ETA sampling inside `hooks-cycle`
- or explicitly isolate / optimize classifier subprocess cost without letting benchmark budgets drift

The important thing is that both candidates now sit on top of a stable benchmark contract instead of a noisy, structurally redundant runtime path.
