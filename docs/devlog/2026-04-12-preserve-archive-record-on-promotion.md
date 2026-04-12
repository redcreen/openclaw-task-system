# Preserve Archive Record On Promotion

## Problem

The new dry-run promotion policy exposed the correct next command, but executing the repo-writing bundle against an existing dated record still had a bad edge:

- `run_planning_acceptance_bundle.py --json --date 2026-04-12 --force` refreshed artifacts
- and also replaced the existing archive record with template content

That made the promotion path unsafe precisely when maintainers were trying to turn a green rehearsal into durable dated evidence.

## Key Thinking

The problem was not the promotion policy itself. The problem was that the repo-writing path still treated `--force` like permission to recreate the record file.

For this workflow, dated archive records are not disposable scratch files:

- artifacts should refresh
- the existing dated narrative should survive unless someone intentionally edits it

So the protection had to live in the preparation layer that decides whether the record file gets created at all.

## Solution

Changed `prepare_planning_acceptance.py` so repo-writing runs preserve an existing dated archive record even when `--force` is present.

Then aligned the surrounding workflow:

- bundle promotion output now points to `python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date YYYY-MM-DD`
- bundle / capture / suite help text now describes `--force` as backward-compatible wording rather than destructive overwrite behavior
- runbook, usage, archive guidance, and the dated 2026-04-12 record now reflect the safe promotion command

## Validation

- `python3 -m unittest discover -s tests -p 'test_prepare_planning_acceptance.py' -v`
- `python3 -m unittest discover -s tests -p 'test_run_planning_acceptance_bundle.py' -v`
- `python3 -m unittest discover -s tests -p 'test_planning_acceptance_suite.py' -v`
- `python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date 2026-04-12`
- `python3 scripts/runtime/release_gate.py --json`

## Follow-Up

Future planning archive promotions should use the no-`--force` command shown by `promotion_command`.

If maintainers ever need an intentional record rewrite, that should be a separate explicit workflow rather than an accidental side effect of routine evidence refresh.
