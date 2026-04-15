# Inline Growware Same-Session Classifier

## Problem

After the registration-rescan slice landed, the next focused benchmark showed a narrower remaining hotspot inside same-session natural-language routing:

- the repo-owned Growware classifier still launched `python3 scripts/runtime/growware_feedback_classifier.py` as a fresh subprocess on every follow-up classification
- inflight lookup was no longer the main cost, so classifier startup overhead became visible in the profile
- Milestone 3 needed to remove that fixed tax without changing the behavior contract for custom classifier commands

## Key Thinking

The safe cut was to optimize only the path the repo fully owns:

- fast-path the local `growware_feedback_classifier.py` command only when the configured command resolves to the current runtime root
- keep arbitrary classifier commands on the existing subprocess path
- reuse already-loaded config on the same registration flow so the slice trims hot-path overhead without widening behavior changes

That preserves the benchmark contract and avoids turning one measured optimization into a broader command-execution refactor.

## Solution

Reduced the classifier path in three steps:

1. repo-owned in-process classifier
- `openclaw_hooks.py` now detects when the configured same-session classifier command points at the repo-owned `growware_feedback_classifier.py`
- that known local path now calls `growware_feedback_classifier.classify(...)` in-process instead of spawning a subprocess

2. preserved custom-command behavior
- custom classifier commands still execute through `subprocess.run(...)`
- the optimization stays scoped to the repo-owned Growware path instead of silently changing generic command semantics

3. structural protection
- `register_from_payload` now reuses the already-loaded runtime config when it hands off to inbound lifecycle registration
- `tests/test_openclaw_hooks.py` now asserts that the repo-owned classifier fast path does not fall back to subprocess spawn

## Validation

- `PYTHONPATH="$PWD:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}" python3 -m unittest tests.test_openclaw_hooks tests.test_same_session_routing_acceptance tests.test_performance_baseline -v`
- `python3 scripts/runtime/performance_baseline.py --profile-scenario hooks-cycle --profile-scenario same-session-routing-classifier --profile-top 8 --json`

## Follow-Up

The focused classifier result moved clearly in the right direction:

- before the in-process fast path: median `90.0957ms`, p95 `132.2014ms`
- after the in-process fast path: median `24.9839ms`, p95 `38.5312ms`

What remains unsolved is also clearer now:

- `hooks-cycle` still has active-task resolution and archive-backed ETA sampling cost after registration rescans were removed
- `system-overview` can still show noisy p95 spikes from archive / projection fanout
- installed-runtime drift should stay separate from this repo-local performance slice unless a deliberate local deploy is requested
