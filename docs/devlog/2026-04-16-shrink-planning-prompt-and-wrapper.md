# Shrink Planning Prompt And Wrapper

## Problem

The governance topic had already proven that user-visible Telegram slowness was mostly model time spent on oversized context. That still left one practical question: which repo-owned cut should land first without weakening capability or safety?

The planning path was the cleanest first target because both the default planning system prompt and the runtime wrapper are paid repeatedly, fully owned by this repo, and do not require immediate tool-surface or startup-transcript decisions.

## What We Chose

We took the first `TG-2` closed loop on the default planning contract:

- shortened the default planning system prompt while keeping the same behavioral rules
- shortened the runtime planning wrapper while preserving the task-system control contract
- added tests that cap the prompt and wrapper lengths so this slice cannot silently regress

The key choice was to avoid starting with tool-schema pruning. Tool exposure is the largest static contributor overall, but it has a wider compatibility surface. The planning contract was a narrower, safer, and still meaningful first cut.

## Result

The measured reductions in repo-owned fixed planning context are:

- default planning system prompt: `1531` -> `954` chars
- default planning runtime wrapper: `1168` -> `696` chars

That gives the repo one completed context-diet slice with explicit before/after numbers, without changing the current planning semantics.

## Validation

- `PYTHONPATH="$PWD:$PWD/tests${PYTHONPATH:+:$PYTHONPATH}" python3 -m unittest tests.test_task_config -v`
- `node --test plugin/tests/tool-planning-flow.test.mjs`
- `python3 scripts/runtime/runtime_mirror.py --write`
- `python3 scripts/runtime/growware_local_deploy.py --json`
- `python3 scripts/runtime/plugin_doctor.py --json`
- `python3 scripts/runtime/plugin_smoke.py --json`
- `python3 scripts/runtime/growware_preflight.py --json`

## Follow-Up

- continue `TG-2` on tool-schema surface and startup transcript carryover
- keep rerunning `session_latency_audit.py` after each prompt-surface cut
- define the activation-resume gate only after the remaining high-cost context paths have explicit decisions
