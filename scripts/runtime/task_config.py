#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from task_policy import DEFAULT_LONG_TASK_KEYWORDS
from task_state import DEFAULT_DATA_DIR, PROJECT_ROOT, TaskPaths

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "task_system.json"
EXAMPLE_CONFIG_PATH = PROJECT_ROOT / "config" / "task_system.example.json"


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
class AgentTaskConfig:
    enabled: bool = True
    auto_start: bool = True
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    silence_monitor: SilenceMonitorConfig = field(default_factory=SilenceMonitorConfig)


@dataclass(frozen=True)
class DeliveryConfig:
    mode: str = "session-aware"
    openclaw_bin: str = "/Users/redcreen/.local/bin/openclaw"
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


def _build_agent_config(raw: dict[str, Any]) -> AgentTaskConfig:
    return AgentTaskConfig(
        enabled=bool(raw.get("enabled", True)),
        auto_start=bool(raw.get("autoStart", True)),
        classification=_build_classification_config(raw.get("classification", {})),
        silence_monitor=_build_silence_monitor_config(raw.get("silenceMonitor", {})),
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
            openclaw_bin=(raw.get("delivery") or {}).get("openclawBin", "/Users/redcreen/.local/bin/openclaw"),
            auto_execute_instructions=bool((raw.get("delivery") or {}).get("autoExecuteInstructions", True)),
            retry_failed_instructions=bool((raw.get("delivery") or {}).get("retryFailedInstructions", False)),
            execution_context=str((raw.get("delivery") or {}).get("executionContext", "local")),
        ),
        config_path=path,
    )
