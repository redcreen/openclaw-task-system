[English](todo.md) | [中文](todo.zh-CN.md)

# Temporary Notes

This file is a temporary intake list, not the canonical roadmap or development plan.

## Current High-Level State

- Phase 6 minimum closure is already shipped
- Milestone 1: post-hardening closeout is already complete
- same-session message routing is already shipped
- `task_user_content` is deprecated as a runtime protocol
- architecture hardening is already closed and should now be read from [roadmap.md](roadmap.md) and [architecture.md](architecture.md)

## Reading Rules

- use [roadmap.md](roadmap.md) for the main delivery line
- use [test-plan.md](test-plan.md) and [testsuite.md](testsuite.md) for validation scope
- use this page only for items that are real but not yet mature enough to move back into the formal stack

## Future Candidate Intake

No active closeout debt should be tracked here.

Keep only items that are real but not yet mature enough to become a named roadmap candidate, for example:

- stronger structured planning or tool decomposition for broader compound requests
- higher-fidelity real planning or channel evidence when delivery contracts change
- deeper operator UX and recovery depth that still preserves runtime truth

## Graduation Rule

Once an item becomes durable, move it back into one of these pages:

- [roadmap.md](roadmap.md) for milestone-order work
- [architecture.md](architecture.md) for stable runtime shape or boundary changes
- [test-plan.md](test-plan.md) for release-facing validation
- [reference/README.md](reference/README.md) or a reference subpage for stable detailed facts
