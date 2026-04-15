# Close Milestone 3 Performance Optimization

## Problem

Milestone 3 had already produced the benchmark contract, hotspot attribution, and several reviewed optimization cuts, but the repo still described the milestone as active:

- roadmap, development plan, README, and control-surface docs still framed performance work as the current mainline
- remaining measured hotspots were still written as if they blocked closeout, even though the milestone exit criteria were already satisfied
- the repo risk had shifted from "unmeasured tuning" to "starting activation prep without explicitly closing the performance line"

That meant the repo could drift into another ambiguous phase boundary even after the performance milestone had effectively done its job.

## Key Thinking

The right closeout was evidence-based, not celebratory:

- close Milestone 3 only if the repo already had a reproducible benchmark contract, hotspot attribution, validated optimizations, and regression protection
- keep remaining performance candidates visible, but demote them to carry-forward backlog instead of pretending they still block closeout
- move the active line to post-performance live pilot activation preparation without implying that local deploy or live rehearsal had already been approved

## Solution

Closed the milestone in three layers:

1. milestone truth
- updated roadmap, development plan, README, and `.codex/status.md` / `.codex/plan.md` so Milestone 3 is explicitly complete
- moved the active phase to post-performance live pilot activation preparation

2. benchmark closeout evidence
- updated `performance-baseline*.md` to add a closeout signal section
- recast remaining `hooks-cycle`, `system-overview`, and second-surface work as carry-forward candidates rather than milestone blockers

3. next entry criteria
- documented the next phase around activation entry criteria, operator evidence, install-sync intent, and rollback boundaries
- kept installed-runtime drift visible as an explicit follow-up decision instead of silently absorbing it into the closed performance milestone

## Validation

- `python3 scripts/runtime/performance_baseline.py --profile-scenario hooks-cycle --profile-scenario same-session-routing-classifier --profile-top 8 --json`
- `PYTHONPATH="$PWD:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}" python3 -m unittest tests.test_openclaw_hooks tests.test_same_session_routing_acceptance tests.test_performance_baseline -v`
- `python3 scripts/runtime/growware_preflight.py --json`
- `python3 scripts/runtime/growware_openclaw_binding.py --json`
- `bash scripts/run_tests.sh`
- `python3 scripts/runtime/runtime_mirror.py --write`
- `python3 scripts/runtime/plugin_doctor.py --json`
- `python3 scripts/runtime/plugin_smoke.py --json`

## Follow-Up

Milestone 3 is closed because the repo now has:

- one reproducible benchmark / profile contract
- reviewed before / after evidence on the main hotspots
- structural and budget-based regression protection
- a green repo-local validation baseline

The next phase should not reopen broad tuning by default.

It should prepare the first bounded `feishu6-chat` live activation rehearsal by deciding:

- the minimum evidence package
- whether installed-runtime drift must be cleared first
- the rollback and re-entry rule if rehearsal exposes a new measured regression
