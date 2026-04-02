# OpenClaw Task System Plugin

This package is the plugin-first integration layer for the OpenClaw Task System.

It is designed to keep OpenClaw core untouched:

- install or link the plugin
- enable it in OpenClaw config
- let the plugin call the task-system runtime hooks

Current first-stage hook behavior:

- registers long-task candidates during `before_dispatch`
- syncs active-task progress during `message_sending`
- finalizes active tasks during `agent_end`
- polls `data/send-instructions/` and host-delivers `feishu` notifications in-process

The core runtime and state machine still live in:

- `workspace/openclaw-task-system/scripts/runtime/`

This plugin package only acts as the OpenClaw-facing adapter.
