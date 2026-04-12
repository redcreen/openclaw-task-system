[English](continuation_lane_decision_log.md) | [中文](continuation_lane_decision_log.zh-CN.md)

# Continuation Lane Decision Log

## Purpose

This note records the durable decisions behind the continuation lane: what belongs there, what does not, and which bridge behaviors must remain temporary.

## Accepted Decisions

- continuation work is a first-class runtime concern because it represents future execution, recovery, and eventual completion, not ordinary reply text
- continuation scheduling must not be treated as a side effect of the normal reply lane
- runtime-owned evidence must explain why a message entered continuation, how it will resume, and what recovery path applies
- stopgap compatibility behavior may exist, but it must not redefine the long-term contract of the lane

## Boundary With Other Lanes

- normal reply lane: immediate business content for work that is happening now
- control-plane lane: `[wd]`, queue state, status, cancel, retry, and recovery notices
- continuation lane: future execution, delayed follow-up, dependent continuation, and recovered scheduled work

The continuation lane exists so the runtime can preserve the truth of future work across reloads, watchdog intervention, and continuity recovery.

## Operational Implications

- watchdog and continuity tooling need first-class continuation state, not inferred text
- future-first planning must land in continuation-oriented runtime state instead of hiding inside natural-language promises
- lane decisions must remain explainable from the runtime truth source so operators can recover or audit them later

## Review Reminder

When a behavior seems like it could fit both the normal reply lane and the continuation lane, prefer the question:

> does this represent immediate content, or does it represent future work that must survive recovery?

If the answer is future work, it belongs in continuation-oriented runtime state even if the first user-visible symptom looks conversational.
