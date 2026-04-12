[English](README.md) | [中文](README.zh-CN.md)

# Same-Session Message Routing

## Scope

This subproject defines how consecutive user messages inside the same session are routed across:

- `steering`
- `queueing`
- `control-plane`
- `collect-more`

## Problem

Real follow-up messages are more complicated than a single label:

- some messages refine the current task
- some open a new independent task
- some mean `wait, I am still sending context`
- some are pure control-plane instructions such as `continue`, `stop`, or `status`

If that boundary stays implicit, the system oscillates between bad outcomes:

- independent work gets merged into the current task
- genuine task refinements get queued as a new task
- execution starts while the user is still adding context
- automatic decisions happen without a truthful user-visible explanation

## Shipped Result

This capability is shipped.

Runtime behavior now includes:

- runtime-owned structured routing records
- deterministic rules for obvious cases
- execution-stage gates for merge, restart, append, or queue decisions
- runtime-owned `[wd]` receipts for every automatic routing decision
- runtime-owned classifier fallback only for ambiguous same-session follow-up

## Core Model

The durable model is:

1. runtime rules handle obvious cases first
2. ambiguous same-session follow-up may invoke a runtime-owned structured classifier
3. runtime still makes the final execution decision
4. every automatic routing decision returns a runtime-owned `[wd]`

This is a runtime-supervised routing problem, not a free-form decision the main conversation LLM should own by itself.

## Main Entry Points

- [decision_contract.md](decision_contract.md): classifications, decisions, ownership, and receipt rules
- [development_plan.md](development_plan.md): shipped phase history and extension guidance
- [test_cases.md](test_cases.md): reference cases for deterministic, ambiguous, and regression coverage

## Validation Entry Point

```bash
python3 scripts/runtime/same_session_routing_acceptance.py --json
```
