[English](external_comparison.md) | [中文](external_comparison.zh-CN.md)

# External Comparison

## Purpose

This document records which external systems influenced the project and which directions were intentionally rejected.

For full Chinese detail, see [external_comparison.zh-CN.md](external_comparison.zh-CN.md).

## Main Takeaways

The project borrowed:

- control-plane as a first-class layer
- clearer queue / control-plane / worker separation
- explicit same-session steering and queueing semantics

The project intentionally did not become:

- a generic orchestrator
- a distributed control plane product
- a multi-agent framework-first runtime

## Practical Conclusion

The correct shape for this repository remains:

- OpenClaw-native
- supervisor-first
- task runtime first, not orchestrator first
- user-visible control-plane as a product capability, not a side effect
