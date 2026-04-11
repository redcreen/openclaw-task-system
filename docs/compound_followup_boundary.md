[English](compound_followup_boundary.md) | [中文](compound_followup_boundary.zh-CN.md)

# Compound Follow-Up Boundary

## Status

Open design boundary.

For full Chinese detail, see [compound_followup_boundary.zh-CN.md](compound_followup_boundary.zh-CN.md).

## Problem

Single-intent delayed replies are supported.

Compound requests such as "do A now, then come back later" are not something that should be solved by growing regex, phrase lists, or ad hoc stopgaps.

## Current Product Boundary

- clear single-intent delayed replies: supported
- compound delayed requests without structured planning: do not silently materialize hidden follow-up state
- complex or ambiguous future-action requests: must move toward structured planning rather than more hardcoded text rules

## Long-Term Direction

The correct long-term direction is:

- structured task planning
- explicit runtime-owned follow-up creation
- durable truth-source state
- honest user-visible projection when planning is missing, late, or unhealthy
