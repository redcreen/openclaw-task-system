#!/usr/bin/env python3
from __future__ import annotations

import argparse
import cProfile
import json
import os
import platform
import pstats
import shutil
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from growware_preflight import build_preflight_report
from openclaw_hooks import (
    finalize_active_from_payload,
    progress_active_from_payload,
    register_from_payload,
    resolve_active_task_from_payload,
)
from plugin_smoke import run_plugin_smoke
from same_session_routing import build_same_session_routing_decision
from task_state import TaskPaths, TaskState, TaskStore
from task_status import build_system_overview

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER_SCRIPT = PROJECT_ROOT / "scripts" / "runtime" / "growware_feedback_classifier.py"
BENCHMARK_SCHEMA = "openclaw.task-system.performance-benchmark.v1"


@dataclass(frozen=True)
class ScenarioBudget:
    median_ms: float
    p95_ms: float


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    surface: str
    description: str
    fixture: str
    budgets: ScenarioBudget
    default_iterations: int
    default_warmup_iterations: int
    prepare: Callable[[], "PreparedScenario"]


@dataclass
class PreparedScenario:
    definition: ScenarioDefinition
    run: Callable[[], Any]
    cleanup: Callable[[], None]


@dataclass
class BenchmarkSample:
    elapsed_ms: float


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _measure(
    run: Callable[[], Any],
    *,
    iterations: int,
    warmup_iterations: int,
) -> list[BenchmarkSample]:
    for _ in range(max(0, warmup_iterations)):
        run()
    samples: list[BenchmarkSample] = []
    for _ in range(max(1, iterations)):
        started = time.perf_counter_ns()
        run()
        ended = time.perf_counter_ns()
        samples.append(BenchmarkSample(elapsed_ms=round((ended - started) / 1_000_000, 4)))
    return samples


def _quantile_ms(values: list[float], numerator: int, denominator: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = ((len(ordered) - 1) * numerator) / denominator
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    interpolated = ordered[lower] + ((ordered[upper] - ordered[lower]) * fraction)
    return round(interpolated, 4)


def _summarize_samples(samples: list[BenchmarkSample]) -> dict[str, float]:
    values = [sample.elapsed_ms for sample in samples]
    return {
        "min_ms": round(min(values), 4),
        "mean_ms": round(sum(values) / len(values), 4),
        "median_ms": _quantile_ms(values, 1, 2),
        "p95_ms": _quantile_ms(values, 95, 100),
        "max_ms": round(max(values), 4),
    }


def _budget_status(summary: dict[str, float], budget: ScenarioBudget) -> dict[str, Any]:
    median_ok = summary["median_ms"] <= budget.median_ms
    p95_ok = summary["p95_ms"] <= budget.p95_ms
    return {
        "ok": median_ok and p95_ok,
        "median_ok": median_ok,
        "p95_ok": p95_ok,
    }


def _capture_profile(run: Callable[[], Any], *, top: int) -> list[dict[str, Any]]:
    profiler = cProfile.Profile()
    profiler.enable()
    run()
    profiler.disable()
    stats = pstats.Stats(profiler)
    ranked = sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)[:top]
    profile_rows: list[dict[str, Any]] = []
    for (filename, line_no, function_name), stat in ranked:
        primitive_calls, total_calls, total_time, cumulative_time, _callers = stat
        profile_rows.append(
            {
                "function": f"{Path(filename).name}:{line_no}:{function_name}",
                "primitive_calls": primitive_calls,
                "total_calls": total_calls,
                "total_time_s": round(total_time, 6),
                "cumulative_time_s": round(cumulative_time, 6),
            }
        )
    return profile_rows


def _write_config(path: Path, *, data_dir: Path, agents: Optional[dict[str, Any]] = None) -> None:
    payload: dict[str, Any] = {"taskSystem": {"storageDir": str(data_dir)}}
    if agents:
        payload["taskSystem"]["agents"] = agents
    _write_json(path, payload)


def _new_fixture(agents: Optional[dict[str, Any]] = None) -> tuple[TaskPaths, Path, Callable[[], None]]:
    temp_dir = Path(tempfile.mkdtemp(prefix="task-system-perf."))
    paths = TaskPaths.from_root(temp_dir)
    config_path = temp_dir / "task_system.json"
    _write_config(config_path, data_dir=paths.data_dir, agents=agents)
    return paths, config_path, lambda: shutil.rmtree(temp_dir, ignore_errors=True)


def _seed_overview_fixture(
    *,
    paths: TaskPaths,
    active_task_count: int = 48,
    archived_task_count: int = 96,
) -> None:
    store = TaskStore(paths=paths)
    for index in range(active_task_count):
        session_key = f"agent:main:feishu:direct:perf-overview:{index % 12}"
        base_meta: dict[str, Any] = {
            "source": "performance-baseline",
            "original_user_request": f"perf active task {index}",
        }
        if index % 8 == 0:
            task = store.observe_task(
                agent_id="main",
                session_key=session_key,
                channel="feishu",
                chat_id=f"chat:overview:{index}",
                task_label=f"observed task {index}",
                meta=base_meta,
            )
        else:
            task = store.register_task(
                agent_id="main",
                session_key=session_key,
                channel="feishu",
                chat_id=f"chat:overview:{index}",
                task_label=f"queued task {index}",
                meta=base_meta,
            )
        if index % 8 in {1, 2}:
            task = store.start_task(task.task_id)
            if index % 16 == 1:
                task.meta["side_effects_started"] = True
                store.save_task(task)
        elif index % 8 == 3:
            store.block_task(task.task_id, "waiting for external follow-up")
        elif index % 8 == 4:
            store.pause_task(task.task_id, "scheduled follow-up")
        elif index % 8 == 5:
            task.meta["tool_followup_plan"] = {
                "plan_id": f"plan_{index}",
                "status": "scheduled",
                "followup_due_at": "2030-01-01T00:00:00+00:00",
                "followup_summary": f"perf follow-up {index}",
                "main_user_content_mode": "immediate-summary",
            }
            task.meta["planning_promise_guard"] = {
                "status": "scheduled",
                "expected_by_finalize": True,
                "promise_summary": f"perf promise {index}",
                "main_user_content_mode": "immediate-summary",
            }
            task.meta["same_session_routing"] = {
                "schema": "openclaw.task-system.same-session-routing.v1",
                "version": 1,
                "routing_status": "decided",
                "same_session_followup": True,
                "classification": "steering",
                "execution_decision": "append-as-next-step",
                "reason_code": "perf-fixture-routing",
            }
            store.save_task(task)
        elif index % 8 == 6:
            task.meta["tool_followup_plan"] = {
                "plan_id": f"plan_{index}",
                "status": "anomaly",
                "followup_due_at": "2020-01-01T00:00:00+00:00",
            }
            task.meta["planning_promise_guard"] = {
                "status": "anomaly",
                "expected_by_finalize": True,
            }
            task.meta["planning_anomaly"] = "promise-without-task"
            store.save_task(task)
        if index % 3 == 0:
            _write_json(
                paths.data_dir / "dispatch-results" / f"{task.task_id}.json",
                {
                    "schema": "openclaw.task-system.dispatch-result.v1",
                    "task_id": task.task_id,
                    "action": "send",
                    "reason": "supported",
                    "execution_context": "dry-run",
                    "requested_execution_context": "host",
                },
            )
        if index % 5 == 0:
            _write_json(paths.data_dir / "outbox" / f"{task.task_id}.json", {"task_id": task.task_id})
        if index % 7 == 0:
            _write_json(paths.data_dir / "sent" / f"{task.task_id}.json", {"task_id": task.task_id})

    for index in range(archived_task_count):
        task = store.register_task(
            agent_id="main",
            session_key=f"agent:main:telegram:direct:perf-archive:{index % 16}",
            channel="telegram",
            chat_id=f"chat:archive:{index}",
            task_label=f"archived task {index}",
            meta={"source": "performance-baseline", "archived_index": index},
        )
        if index % 3 == 0:
            store.fail_task(task.task_id, "perf archived failure")
        else:
            store.complete_task(task.task_id)
        if index % 4 == 0:
            _write_json(paths.data_dir / "processed-instructions" / f"{task.task_id}.json", {"task_id": task.task_id})
        if index % 6 == 0:
            _write_json(paths.data_dir / "sent" / f"{task.task_id}.json", {"task_id": task.task_id})


def _prepare_hook_cycle_scenario() -> PreparedScenario:
    paths, config_path, cleanup = _new_fixture()
    _seed_overview_fixture(paths=paths, active_task_count=24, archived_task_count=32)
    sequence = {"index": 0}

    def run() -> dict[str, Any]:
        sequence["index"] += 1
        session_key = f"agent:main:feishu:direct:perf-hooks:{sequence['index']}"
        payload = {
            "agent_id": "main",
            "session_key": session_key,
            "channel": "feishu",
            "chat_id": f"chat:perf-hooks:{sequence['index']}",
            "user_id": "ou_perf_hooks",
            "user_request": "帮我整理 benchmark 合同并验证热点。",
            "estimated_steps": 4,
            "needs_verification": True,
        }
        registered = register_from_payload(payload, config_path=config_path)
        resolve = resolve_active_task_from_payload(
            {
                "agent_id": "main",
                "session_key": session_key,
            },
            config_path=config_path,
        )
        progress = progress_active_from_payload(
            {
                "agent_id": "main",
                "session_key": session_key,
                "progress_note": "已建立 fixture，正在抓基线与 profile。",
            },
            config_path=config_path,
        )
        finalized = finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": session_key,
                "success": True,
                "result_summary": "已完成基线采集。",
            },
            config_path=config_path,
        )
        return {
            "registered": registered.get("task_id"),
            "resolved": resolve.get("task_id"),
            "progress_updated": progress.get("updated"),
            "finalized": (finalized.get("task") or {}).get("task_id"),
        }

    return PreparedScenario(
        definition=SCENARIO_DEFINITIONS["hooks-cycle"],
        run=run,
        cleanup=cleanup,
    )


def _prepare_same_session_rule_scenario() -> PreparedScenario:
    active_task = TaskState(
        task_id="task_perf_routing_rule",
        run_id="run_perf_routing_rule",
        agent_id="main",
        session_key="agent:main:feishu:direct:perf-routing-rule",
        channel="feishu",
        chat_id="chat:perf-routing-rule",
        task_label="整理 milestone 3 的 benchmark contract",
        status="running",
        created_at="2026-04-14T00:00:00+00:00",
        started_at="2026-04-14T00:00:00+00:00",
        updated_at="2026-04-14T00:00:00+00:00",
        last_user_visible_update_at="2026-04-14T00:00:00+00:00",
        last_internal_touch_at="2026-04-14T00:00:00+00:00",
        meta={
            "execution_stage": "running-no-side-effects",
            "original_user_request": "整理 milestone 3 的 benchmark contract",
        },
    )

    def run() -> dict[str, Any]:
        return build_same_session_routing_decision(
            session_key="agent:main:feishu:direct:perf-routing-rule",
            user_request="把预算改成先用基线导出的草案",
            should_register_task=True,
            classification_reason="default-new-task",
            active_task=active_task,
            recoverable_task=None,
            queue_state={"running_count": 1, "queued_count": 3, "active_count": 4},
            collecting_state=False,
            recent_user_messages=["先整理 benchmark surface", "再给预算草案"],
        )

    return PreparedScenario(
        definition=SCENARIO_DEFINITIONS["same-session-routing-rule"],
        run=run,
        cleanup=lambda: None,
    )


def _prepare_same_session_classifier_scenario() -> PreparedScenario:
    agents = {
        "growware": {
            "sameSessionRouting": {
                "enabled": True,
                "classifier": {
                    "enabled": True,
                    "command": [sys.executable, str(CLASSIFIER_SCRIPT)],
                    "timeoutMs": 1000,
                    "minConfidence": 0.75,
                },
            }
        }
    }
    paths, config_path, cleanup = _new_fixture(agents=agents)
    _seed_overview_fixture(paths=paths, active_task_count=16, archived_task_count=16)
    sequence = {"index": 0}

    def run() -> dict[str, Any]:
        sequence["index"] += 1
        session_key = f"agent:growware:feishu:direct:perf-classifier:{sequence['index']}"
        register_from_payload(
            {
                "agent_id": "growware",
                "session_key": session_key,
                "channel": "feishu",
                "account_id": "feishu6-chat",
                "chat_id": f"chat:perf-classifier:{sequence['index']}",
                "user_id": "ou_perf_classifier",
                "user_request": "请先整理当前任务的性能基线。",
                "estimated_steps": 3,
            },
            config_path=config_path,
        )
        return register_from_payload(
            {
                "agent_id": "growware",
                "session_key": session_key,
                "channel": "feishu",
                "account_id": "feishu6-chat",
                "chat_id": f"chat:perf-classifier:{sequence['index']}",
                "user_id": "ou_perf_classifier",
                "user_request": "再来一个版本，顺便补一个边界条件。",
                "observe_only": True,
            },
            config_path=config_path,
        )

    return PreparedScenario(
        definition=SCENARIO_DEFINITIONS["same-session-routing-classifier"],
        run=run,
        cleanup=cleanup,
    )


def _prepare_system_overview_scenario() -> PreparedScenario:
    paths, _config_path, cleanup = _new_fixture()
    _seed_overview_fixture(paths=paths)

    def run() -> dict[str, Any]:
        return build_system_overview(paths=paths)

    return PreparedScenario(
        definition=SCENARIO_DEFINITIONS["system-overview"],
        run=run,
        cleanup=cleanup,
    )


def _prepare_growware_preflight_scenario() -> PreparedScenario:
    def run() -> dict[str, Any]:
        return build_preflight_report(PROJECT_ROOT)

    return PreparedScenario(
        definition=SCENARIO_DEFINITIONS["growware-preflight"],
        run=run,
        cleanup=lambda: None,
    )


def _prepare_plugin_smoke_scenario() -> PreparedScenario:
    def run() -> dict[str, Any]:
        return run_plugin_smoke()

    return PreparedScenario(
        definition=SCENARIO_DEFINITIONS["plugin-smoke"],
        run=run,
        cleanup=lambda: None,
    )


SCENARIO_DEFINITIONS: dict[str, ScenarioDefinition] = {
    "hooks-cycle": ScenarioDefinition(
        scenario_id="hooks-cycle",
        surface="runtime lifecycle hooks",
        description="End-to-end register / resolve-active / progress / finalize path on a fixed repo-local fixture.",
        fixture="24 active + 32 archived tasks in a temp task-system root",
        budgets=ScenarioBudget(median_ms=45.0, p95_ms=60.0),
        default_iterations=20,
        default_warmup_iterations=3,
        prepare=_prepare_hook_cycle_scenario,
    ),
    "same-session-routing-rule": ScenarioDefinition(
        scenario_id="same-session-routing-rule",
        surface="same-session routing rule path",
        description="Pure in-memory same-session rule decision on an active running task without classifier subprocess cost.",
        fixture="one running task with fixed routing metadata",
        budgets=ScenarioBudget(median_ms=0.05, p95_ms=0.1),
        default_iterations=400,
        default_warmup_iterations=40,
        prepare=_prepare_same_session_rule_scenario,
    ),
    "same-session-routing-classifier": ScenarioDefinition(
        scenario_id="same-session-routing-classifier",
        surface="same-session routing classifier path",
        description="Follow-up register path with the repo-owned Growware classifier subprocess enabled.",
        fixture="16 active + 16 archived tasks plus a classifier-enabled temp config",
        budgets=ScenarioBudget(median_ms=115.0, p95_ms=150.0),
        default_iterations=10,
        default_warmup_iterations=1,
        prepare=_prepare_same_session_classifier_scenario,
    ),
    "system-overview": ScenarioDefinition(
        scenario_id="system-overview",
        surface="control-plane and operator projection",
        description="`task_status.build_system_overview` on a queue-heavy, delivery-heavy fixed fixture.",
        fixture="48 active + 96 archived tasks with planning and delivery artifacts",
        budgets=ScenarioBudget(median_ms=35.0, p95_ms=50.0),
        default_iterations=12,
        default_warmup_iterations=2,
        prepare=_prepare_system_overview_scenario,
    ),
    "growware-preflight": ScenarioDefinition(
        scenario_id="growware-preflight",
        surface="repo-local operator preflight",
        description="`growware_preflight.build_preflight_report` on the checked-out repository root.",
        fixture="current repo root only; no host install state",
        budgets=ScenarioBudget(median_ms=8.0, p95_ms=15.0),
        default_iterations=20,
        default_warmup_iterations=3,
        prepare=_prepare_growware_preflight_scenario,
    ),
    "plugin-smoke": ScenarioDefinition(
        scenario_id="plugin-smoke",
        surface="repo-local operator smoke",
        description="`plugin_smoke.run_plugin_smoke` using its own temp config and lifecycle sample.",
        fixture="fresh temp task-system root per iteration",
        budgets=ScenarioBudget(median_ms=20.0, p95_ms=30.0),
        default_iterations=8,
        default_warmup_iterations=1,
        prepare=_prepare_plugin_smoke_scenario,
    ),
}


def run_benchmarks(
    *,
    scenario_ids: list[str],
    iterations: Optional[int] = None,
    warmup_iterations: Optional[int] = None,
    profile_scenarios: Optional[list[str]] = None,
    profile_top: int = 10,
) -> dict[str, Any]:
    profiles = set(profile_scenarios or [])
    scenario_results: list[dict[str, Any]] = []
    profile_results: dict[str, list[dict[str, Any]]] = {}

    for scenario_id in scenario_ids:
        definition = SCENARIO_DEFINITIONS[scenario_id]
        prepared = definition.prepare()
        scenario_iterations = max(1, iterations if iterations is not None else definition.default_iterations)
        scenario_warmups = max(0, warmup_iterations if warmup_iterations is not None else definition.default_warmup_iterations)
        try:
            samples = _measure(
                prepared.run,
                iterations=scenario_iterations,
                warmup_iterations=scenario_warmups,
            )
            summary = _summarize_samples(samples)
            budget_state = _budget_status(summary, definition.budgets)
            scenario_results.append(
                {
                    "scenario_id": scenario_id,
                    "surface": definition.surface,
                    "description": definition.description,
                    "fixture": definition.fixture,
                    "iterations": scenario_iterations,
                    "warmup_iterations": scenario_warmups,
                    "budgets": {
                        **asdict(definition.budgets),
                        **budget_state,
                    },
                    "summary": summary,
                }
            )
            if scenario_id in profiles:
                profile_results[scenario_id] = _capture_profile(prepared.run, top=profile_top)
        finally:
            prepared.cleanup()

    budget_failures = [
        result["scenario_id"]
        for result in scenario_results
        if not bool(((result.get("budgets") or {}).get("ok")))
    ]
    return {
        "schema": BENCHMARK_SCHEMA,
        "generated_at": now_iso(),
        "project_root": str(PROJECT_ROOT),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "processor": platform.processor() or None,
            "cwd": os.getcwd(),
        },
        "summary": {
            "scenario_count": len(scenario_results),
            "budget_failures": budget_failures,
            "all_budgets_ok": not budget_failures,
        },
        "scenarios": scenario_results,
        "profiles": profile_results,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Performance Baseline", ""]
    lines.append(f"- generated_at: {payload['generated_at']}")
    lines.append(f"- python: {payload['environment']['python']}")
    lines.append(f"- platform: {payload['environment']['platform']}")
    lines.append(f"- all_budgets_ok: {payload['summary']['all_budgets_ok']}")
    if payload["summary"]["budget_failures"]:
        lines.append(f"- budget_failures: {', '.join(payload['summary']['budget_failures'])}")
    lines.append("")
    for scenario in payload["scenarios"]:
        lines.append(f"## {scenario['scenario_id']}")
        lines.append("")
        lines.append(f"- surface: {scenario['surface']}")
        lines.append(f"- fixture: {scenario['fixture']}")
        lines.append(f"- iterations: {scenario['iterations']}")
        lines.append(f"- median_ms: {scenario['summary']['median_ms']}")
        lines.append(f"- p95_ms: {scenario['summary']['p95_ms']}")
        lines.append(f"- budget_ok: {scenario['budgets']['ok']}")
        lines.append("")
    if payload["profiles"]:
        lines.append("## Profiles")
        lines.append("")
        for scenario_id, rows in payload["profiles"].items():
            lines.append(f"- {scenario_id}")
            for row in rows:
                lines.append(
                    f"  {row['function']} | cumulative={row['cumulative_time_s']}s | total={row['total_time_s']}s | calls={row['total_calls']}"
                )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture reproducible performance baselines for the OpenClaw task runtime.")
    parser.add_argument(
        "--scenario",
        action="append",
        choices=sorted(SCENARIO_DEFINITIONS.keys()),
        help="Limit the run to one or more scenario IDs. Defaults to the full first-surface baseline.",
    )
    parser.add_argument("--iterations", type=int, help="Override the default iteration count for every selected scenario.")
    parser.add_argument("--warmup-iterations", type=int, help="Override the default warmup count for every selected scenario.")
    parser.add_argument(
        "--profile-scenario",
        action="append",
        choices=sorted(SCENARIO_DEFINITIONS.keys()),
        help="Capture one cProfile sample for the selected scenario after benchmark collection.",
    )
    parser.add_argument("--profile-top", type=int, default=10, help="How many profile rows to retain per profiled scenario.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    parser.add_argument(
        "--enforce-budgets",
        action="store_true",
        help="Exit non-zero when any selected scenario exceeds its current draft budget.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenario_ids = args.scenario or list(SCENARIO_DEFINITIONS.keys())
    payload = run_benchmarks(
        scenario_ids=scenario_ids,
        iterations=args.iterations,
        warmup_iterations=args.warmup_iterations,
        profile_scenarios=args.profile_scenario,
        profile_top=args.profile_top,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    if args.enforce_budgets and not payload["summary"]["all_budgets_ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
