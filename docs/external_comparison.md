[English](external_comparison.md) | [中文](external_comparison.zh-CN.md)

# External Comparison

## Purpose

This document records which ideas the project borrowed from external agent or control-plane systems and which directions it explicitly rejected.

## What The Project Borrowed

The repository intentionally adopted these patterns:

- control-plane as a first-class layer
- explicit queue / control-plane / worker separation
- formal same-session steering and queueing semantics
- operator-visible recovery and supervision views instead of black-box execution

## What The Project Rejected

The repository intentionally did not become:

- a generic orchestrator
- a distributed control plane product
- a multi-agent framework-first runtime

## Practical Conclusion

The correct shape for this repository remains:

- OpenClaw-native
- supervisor-first
- task runtime first, not orchestrator first
- user-visible control-plane as a product capability, not a side effect

## When To Use This Note

Use this page when explaining why the project keeps emphasizing supervision, truthful control-plane feedback, and recoverable runtime state instead of continuing to pile more execution logic into the agent path.
