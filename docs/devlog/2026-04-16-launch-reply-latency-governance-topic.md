# Launch Reply Latency Governance Topic

## Problem

Milestone 3 closed on green repo-local benchmark evidence, but a real Telegram session still felt slow to the user. The key risk was not only the slowdown itself. The bigger risk was that the repo had no durable way to explain whether the delay came from task-system code, tool calls, provider latency, or oversized context.

## What Changed The Decision

We measured the trigger session instead of arguing from feel:

- several turns took roughly `16s-50s`
- the majority of time sat in LLM segments
- tool time was secondary
- static prompt weight was already about `140,465 chars`
- later turns inherited startup and transcript carryover cost

That evidence justified opening a governance topic instead of jumping straight into activation preparation.

## Chosen Direction

We did three things in one pass:

1. moved the active mainline from activation preparation to reply-latency and context-weight governance
2. added `scripts/runtime/session_latency_audit.py` so future incidents can be rerun through one durable command
3. published the topic, queue, and resume gate in `.codex/` and public docs

The key design choice was to keep Milestone 3 closed. The repo-local hotspot work remains done. The new topic governs host-observed reply latency on top of that closed baseline.

## Why This Shape

Treating the slowdown as a milestone reopen would blur two different problems:

- repo-owned runtime hotspot cost
- model-facing context weight in real host sessions

The new audit command keeps those surfaces separate. It reports turn timing, LLM/tool shares, transcript growth, and static prompt composition from real session data, which is the minimum evidence needed before trimming prompt surfaces or resuming activation prep.

## Validation

- `python3 -m unittest tests.test_session_latency_audit -v`
- `python3 scripts/runtime/session_latency_audit.py --session-key 'agent:main:telegram:direct:8705812936' --json`
- full repo validation stack after control-surface and docs updates

## Follow-Up

- rank and reduce the largest prompt/context contributors
- define startup/transcript carryover rules
- write the explicit gate for when activation preparation returns as the next bounded phase
