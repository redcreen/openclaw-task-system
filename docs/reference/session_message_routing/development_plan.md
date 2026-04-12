[English](development_plan.md) | [中文](development_plan.zh-CN.md)

# Development Plan

## Purpose

This document records how same-session routing moved from design review into a shipped runtime capability.

Use it together with:

- [README.md](README.md) for the capability summary
- [decision_contract.md](decision_contract.md) for the durable runtime contract
- [test_cases.md](test_cases.md) for regression and extension coverage

## Current Position

This subproject is complete through the shipped routing closure.

Keep this page as a delivery record and as the starting point when future extension work needs to widen routing behavior, acceptance coverage, or classifier fallback rules.

## Delivered Phases

| Phase | Outcome |
| --- | --- |
| Phase 0 | design review locked the decision taxonomy, receipt style, classifier trigger boundary, and restart safety rules |
| Phase 1 | routing decisions became first-class structured runtime state |
| Phase 2 | deterministic rules covered obvious `control-plane`, `collect-more`, no-active-task, and obvious new-task cases |
| Phase 3 | execution-stage gating separated user semantics from safe runtime action |
| Phase 4 | runtime-owned `[wd]` receipts became part of the routing contract |
| Phase 5 | a runtime-owned structured classifier handled ambiguous same-session follow-up with explicit fallback |
| Phase 6 | collecting window state became a real runtime state instead of loose wording |
| Phase 7 | end-to-end acceptance covered the routing flow |
| Phase 8 | roadmap, testsuite, and usage docs were synchronized to the shipped behavior |

## Extension Rules

If this capability changes again:

- update [decision_contract.md](decision_contract.md) before widening semantics
- add or refresh cases in [test_cases.md](test_cases.md)
- keep the acceptance command green:

```bash
python3 scripts/runtime/same_session_routing_acceptance.py --json
```

- keep roadmap and testsuite wording aligned with the actual shipped boundary
