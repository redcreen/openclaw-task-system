[English](output_channel_separation_decision_log.md) | [中文](output_channel_separation_decision_log.zh-CN.md)

# Output Channel Separation Decision Log

## Purpose

This note records the separation between:

- control-plane output
- business output
- planning-internal state

For full Chinese detail, see [output_channel_separation_decision_log.zh-CN.md](output_channel_separation_decision_log.zh-CN.md).

## Current Conclusions

- runtime-owned control-plane output must stay independent from normal business replies
- planning-internal state should not be sent directly to the user
- future-first and same-session behavior both depend on this separation remaining stable
