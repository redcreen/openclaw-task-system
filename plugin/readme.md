# OpenClaw Task System Plugin

This package is the plugin-first integration layer for the OpenClaw Task System.

It is designed to keep OpenClaw core untouched:

- install the plugin
- enable it in OpenClaw config
- let the plugin call the task-system runtime hooks

Current first-stage hook behavior:

- registers long-task candidates during `before_dispatch`
- syncs active-task progress during `message_sending`
- finalizes active tasks during `agent_end`
- polls `data/send-instructions/` and host-delivers `feishu` notifications in-process

This package now bundles its runtime and config assets directly:

- `scripts/runtime/`
- `config/`
- generated runtime state under `data/`

That means the installed extension directory can act as a self-contained runtime root,
without hard-coding a local project path in OpenClaw config.
