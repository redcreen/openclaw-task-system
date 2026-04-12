# Add Channel Acceptance Samples

- Date: 2026-04-12
- Status: resolved

## Problem

The repo already had channel rollout metadata and summary renderers, but the release-facing acceptance line still trusted a static matrix.

That left an avoidable gap:

- focus-channel projection could drift from the producer contract
- fallback channels could silently lose bounded coverage
- `stable_acceptance.py` would stay green without proving those sample paths

## Thinking

The missing piece was not more channel metadata.

It was a contract-level sample entrypoint.

For channel rollout, the critical question is not only whether the summary says Phase 5 is complete. It is whether runtime-facing helpers still produce the same answer for:

- the full shipped matrix
- a receive-side channel focused by session key
- a dispatch-side channel focused by session key
- an observed fallback channel outside the known rollout list

If those sample paths are not pinned together, summary builders and release gates can drift apart.

## Solution

Extend `scripts/runtime/channel_acceptance.py` into a standalone acceptance helper with four concrete checks:

- full channel matrix contract
- Feishu session-focused contract
- Telegram session-focused contract
- observed-channel fallback contract

Then wire `stable_acceptance.py` to run that helper, and update channel/stable acceptance tests plus test-plan / testsuite docs so the new contract becomes explicit.

## Validation

- `python3 scripts/runtime/channel_acceptance.py --json`
- `python3 -m unittest discover -s tests -p 'test_channel_acceptance.py' -v`
- `python3 -m unittest discover -s tests -p 'test_stable_acceptance.py' -v`

All passed after the acceptance expansion.

## Follow-Ups

- Keep `channel_acceptance.py`, `producer_contract.py`, and `stable_acceptance.py` aligned if new channels or rollout boundaries are added.
- Treat any future mismatch between focus-channel acceptance and producer contract summaries as a release-facing regression, not a docs-only issue.

## Related Files

- scripts/runtime/channel_acceptance.py
- scripts/runtime/stable_acceptance.py
- tests/test_channel_acceptance.py
- tests/test_stable_acceptance.py
- .codex/status.md
- .codex/plan.md
