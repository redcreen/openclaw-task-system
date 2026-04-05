# Runtime Data Layout

This directory is created and owned by the installed plugin runtime.

Expected generated subdirectories include:

- `tasks/`
  - inflight and archived task records
- `send-instructions/`
  - pending outbound delivery instructions
- `dispatch-results/`
  - delivery execution records
- `processed-instructions/`
  - successfully archived delivery instructions
- `failed-instructions/`
  - failed delivery instructions pending repair or retry
- `resolved-failed-instructions/`
  - resolved failure records
- `outbox/`, `sent/`, `delivery-ready/`
  - delivery pipeline staging areas
- `diagnostics/`
  - runtime health and outage diagnostics
- `watchdog/`
  - watchdog bridge and recovery staging areas

This data is intentionally runtime-generated and should not be committed.
