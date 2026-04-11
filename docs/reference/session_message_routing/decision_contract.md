[English](decision_contract.md) | [中文](decision_contract.zh-CN.md)

# Decision Contract

## Purpose

This document defines the runtime-owned decision contract for same-session routing.

For full Chinese detail, see [decision_contract.zh-CN.md](decision_contract.zh-CN.md).

## Core Rules

- runtime owns the final routing decision
- the main conversation LLM does not freely decide routing semantics
- every automatic routing decision must produce a runtime-owned `[wd]` receipt
- execution actions such as merge, restart, append, or queue are chosen by runtime according to task stage
