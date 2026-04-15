# Reduce Runtime Registration Rescans

## Problem

After the first Milestone 3 baseline landed, the next profile still showed the same pattern inside `hooks-cycle` and the same-session classifier path:

- one inbound registration rebuilt active, observed, recoverable, and queue views separately
- `register_main_task` then re-entered task-store queue checks from a fresh path
- the same process kept paying for repeated inflight scans before the classifier subprocess cost was even isolated cleanly

That meant the next optimization should remove redundant runtime work first, not widen budgets or guess at classifier tuning.

## Key Thinking

The safest next cut was structural:

- keep the benchmark contract unchanged
- reuse one inflight snapshot inside a registration flow
- reuse the same `TaskStore` instead of rebuilding queue state through nested helpers
- add structural regression tests so the path does not silently drift back to repeated scans

This keeps the optimization evidence-backed and preserves the rule that Milestone 3 changes measured paths before it changes performance promises.

## Solution

Reduced the registration path in three layers:

1. task-store caching
- added a per-store inflight-task cache in `task_state.py`
- invalidated that cache on write paths so repeated `find_inflight_tasks` calls stay cheap without becoming stale

2. single-snapshot registration
- changed `openclaw_bridge.py` to derive active / observed / recoverable / queue state from one inflight snapshot
- reused that snapshot when computing post-save queue metrics instead of rescanning inflight state

3. shared-store task materialization
- changed `main_task_adapter.py` so `register_main_task` and `resume_main_task` can reuse the caller's `TaskStore`
- let registration materialize `running` / `queued` state directly from the already-known running-task fact instead of calling back into queue discovery again

4. regression protection
- `tests/test_task_state.py` now protects cache reuse and invalidation
- `tests/test_openclaw_bridge.py` now asserts that same-process registration reuses one inflight snapshot / store

## Validation

- `PYTHONPATH="$PWD:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}" python3 -m unittest tests.test_task_state tests.test_main_task_adapter tests.test_openclaw_bridge tests.test_performance_baseline -v`
- `python3 scripts/runtime/performance_baseline.py --profile-scenario hooks-cycle --profile-scenario same-session-routing-classifier --profile-top 8 --json`

## Follow-Up

The structural result is clear even when the machine-level timings fluctuate:

- end-to-end `hooks-cycle` inflight-snapshot calls dropped from `10` to `5`
- the registration portion of that path dropped from `6` inflight scans to `1`
- the reviewed follow-up run kept `hooks-cycle` inside its current `45ms` median / `60ms` p95 budget at `35.6638ms` median and `45.022ms` p95

What is not solved yet is also clearer now:

- the same-session classifier path is still dominated by subprocess cost and p95 variance
- the remaining `hooks-cycle` cost is now mostly active-task resolution and archive-backed ETA sampling rather than repeated registration rescans

So the next performance slice should stay narrow:

- decide whether to attack classifier subprocess variance or the remaining hook-side active-task / ETA scan cost first
- do not widen budgets yet just to absorb measurement noise
- keep installed-runtime drift separate from repo-local performance work unless a deliberate local deploy is requested
