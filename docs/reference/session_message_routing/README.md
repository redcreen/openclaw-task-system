[English](README.md) | [中文](README.zh-CN.md)

# Same-Session Message Routing

## Scope

This subproject defines how consecutive user messages inside the same session are routed across:

- `steering`
- `queueing`
- `control-plane`
- `collect-more`

For full Chinese detail, see [README.zh-CN.md](README.zh-CN.md).

## Shipped Result

This capability is shipped.

Runtime behavior now includes:

- runtime-owned structured routing records
- deterministic routing rules for obvious cases
- execution-stage gates for task-safe merge or restart decisions
- runtime-owned `[wd]` routing receipts
- runtime-owned classifier fallback for ambiguous same-session follow-up

## Main Entry Points

- [decision_contract.md](decision_contract.md)
- [development_plan.md](development_plan.md)
- [test_cases.md](test_cases.md)
- `python3 scripts/runtime/same_session_routing_acceptance.py --json`
