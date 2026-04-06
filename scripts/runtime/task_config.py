#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from task_policy import DEFAULT_LONG_TASK_KEYWORDS
from task_state import DEFAULT_DATA_DIR, PROJECT_ROOT, TaskPaths

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "task_system.json"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config" / "task_system.example.json"

DEFAULT_TASK_PLANNING_SYSTEM_PROMPT = """You are the normal request executor. task-system runtime is the supervisor and the owner of the task truth source.

Hard rules:
- Do not generate the first [wd]. That is owned by runtime.
- Do not generate the fixed 30-second progress message. That is owned by runtime.
- Do not generate fallback or recovery control-plane text unless runtime explicitly delegates that action.
- For every future promise, delayed follow-up, reminder, or dependent continuation, use task-system tools by default.
- Never say that you will come back later unless runtime has accepted a real scheduled follow-up.
- If task-system tool scheduling fails, times out, or is skipped, say that explicitly to the user.
- If the request is ambiguous, ask a clarification question instead of inventing a delayed task.

Decision policy:
- normal immediate work: stay on the normal agent path
- fixed control-plane messages: leave to runtime
- all other future-action planning: tool-first
"""


def resolve_openclaw_bin() -> str:
    env_value = os.environ.get("OPENCLAW_BIN", "").strip()
    if env_value:
        return env_value
    return shutil.which("openclaw") or "openclaw"


@dataclass(frozen=True)
class ClassificationConfig:
    min_request_length: int = 24
    min_reason_count: int = 2
    estimated_steps_threshold: int = 3
    keywords: tuple[str, ...] = DEFAULT_LONG_TASK_KEYWORDS


@dataclass(frozen=True)
class SilenceMonitorConfig:
    enabled: bool = True
    silent_timeout_seconds: int = 30
    resend_interval_seconds: int = 30


@dataclass(frozen=True)
class PlanningConfig:
    enabled: bool = True
    mode: str = "tool-first-after-first-ack"
    system_prompt_contract: str = DEFAULT_TASK_PLANNING_SYSTEM_PROMPT


@dataclass(frozen=True)
class AgentTaskConfig:
    enabled: bool = True
    auto_start: bool = True
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    silence_monitor: SilenceMonitorConfig = field(default_factory=SilenceMonitorConfig)
    planning: PlanningConfig = field(default_factory=PlanningConfig)


@dataclass(frozen=True)
class DeliveryConfig:
    mode: str = "session-aware"
    openclaw_bin: str = field(default_factory=resolve_openclaw_bin)
    auto_execute_instructions: bool = True
    retry_failed_instructions: bool = False
    execution_context: str = "local"


@dataclass(frozen=True)
class TaskSystemConfig:
    enabled: bool = True
    storage_dir: Path = DEFAULT_DATA_DIR
    agents: dict[str, AgentTaskConfig] = field(default_factory=dict)
    delivery: DeliveryConfig = field(default_factory=DeliveryConfig)
    config_path: Optional[Path] = None

    def agent_config(self, agent_id: str) -> AgentTaskConfig:
        return self.agents.get(agent_id, AgentTaskConfig())

    def build_paths(self) -> TaskPaths:
        return TaskPaths.from_root(PROJECT_ROOT, data_dir=self.storage_dir)


def _resolve_storage_dir(raw_value: Optional[str]) -> Path:
    if not raw_value:
        return DEFAULT_DATA_DIR
    raw_path = Path(raw_value).expanduser()
    if raw_path.is_absolute():
        return raw_path.resolve()
    return (PROJECT_ROOT / raw_path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_classification_config(raw: dict[str, Any]) -> ClassificationConfig:
    keywords = tuple(raw.get("keywords") or DEFAULT_LONG_TASK_KEYWORDS)
    return ClassificationConfig(
        min_request_length=int(raw.get("minRequestLength", 24)),
        min_reason_count=int(raw.get("minReasonCount", 2)),
        estimated_steps_threshold=int(raw.get("estimatedStepsThreshold", 3)),
        keywords=keywords,
    )


def _build_silence_monitor_config(raw: dict[str, Any]) -> SilenceMonitorConfig:
    return SilenceMonitorConfig(
        enabled=bool(raw.get("enabled", True)),
        silent_timeout_seconds=int(raw.get("silentTimeoutSeconds", 30)),
        resend_interval_seconds=int(raw.get("resendIntervalSeconds", 30)),
    )


def _build_planning_config(raw: dict[str, Any]) -> PlanningConfig:
    return PlanningConfig(
        enabled=bool(raw.get("enabled", True)),
        mode=str(raw.get("mode", "tool-first-after-first-ack")),
        system_prompt_contract=str(raw.get("systemPromptContract", DEFAULT_TASK_PLANNING_SYSTEM_PROMPT)),
    )


def _build_agent_config(raw: dict[str, Any]) -> AgentTaskConfig:
    return AgentTaskConfig(
        enabled=bool(raw.get("enabled", True)),
        auto_start=bool(raw.get("autoStart", True)),
        classification=_build_classification_config(raw.get("classification", {})),
        silence_monitor=_build_silence_monitor_config(raw.get("silenceMonitor", {})),
        planning=_build_planning_config(raw.get("planning", {})),
    )


def load_task_system_config(*, config_path: Optional[Path] = None) -> TaskSystemConfig:
    env_config = os.environ.get("OPENCLAW_TASK_SYSTEM_CONFIG")
    path = Path(env_config).expanduser() if env_config else (config_path or DEFAULT_CONFIG_PATH)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()

    if not path.exists():
        if path == DEFAULT_CONFIG_PATH and EXAMPLE_CONFIG_PATH.exists():
            path = EXAMPLE_CONFIG_PATH
        else:
            return TaskSystemConfig(config_path=path)

    payload = _read_json(path)
    raw = payload.get("taskSystem", {})
    agents = {
        agent_id: _build_agent_config(agent_payload)
        for agent_id, agent_payload in (raw.get("agents") or {}).items()
    }
    return TaskSystemConfig(
        enabled=bool(raw.get("enabled", True)),
        storage_dir=_resolve_storage_dir(raw.get("storageDir")),
        agents=agents,
        delivery=DeliveryConfig(
            mode=(raw.get("delivery") or {}).get("mode", "session-aware"),
            openclaw_bin=(raw.get("delivery") or {}).get("openclawBin", resolve_openclaw_bin()),
            auto_execute_instructions=bool((raw.get("delivery") or {}).get("autoExecuteInstructions", True)),
            retry_failed_instructions=bool((raw.get("delivery") or {}).get("retryFailedInstructions", False)),
            execution_context=str((raw.get("delivery") or {}).get("executionContext", "local")),
        ),
        config_path=path,
    )
