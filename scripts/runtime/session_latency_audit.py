#!/usr/bin/env python3
from __future__ import annotations

import json
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


UTC = timezone.utc
DEFAULT_OPENCLAW_HOME = Path.home() / ".openclaw"
AUDIT_SCHEMA = "openclaw.task-system.session-latency-audit.v1"


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _render_dt(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.astimezone().isoformat(timespec="seconds")


def _parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _safe_excerpt(value: Optional[str], *, limit: int = 96) -> Optional[str]:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def _extract_text(content: Any) -> str:
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                texts.append(str(item["text"]))
        return "".join(texts)
    if isinstance(content, str):
        return content
    return ""


def _extract_tool_names(content: Any) -> list[str]:
    if not isinstance(content, list):
        return []
    names: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "toolCall" and item.get("name"):
            names.append(str(item["name"]))
    return names


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _quantile(values: list[float], numerator: int, denominator: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 4)
    rank = ((len(ordered) - 1) * numerator) / denominator
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    interpolated = ordered[lower] + ((ordered[upper] - ordered[lower]) * fraction)
    return round(interpolated, 4)


def _openclaw_home(path: Optional[Path]) -> Path:
    return (path or DEFAULT_OPENCLAW_HOME).expanduser().resolve()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_sessions_file(
    *,
    session_key: Optional[str],
    openclaw_home: Optional[Path],
    sessions_file: Optional[Path],
) -> Optional[Path]:
    if sessions_file is not None:
        return sessions_file.expanduser().resolve()
    if not session_key:
        return None
    parts = session_key.split(":")
    if len(parts) < 2 or parts[0] != "agent":
        return None
    agent_id = parts[1]
    return _openclaw_home(openclaw_home) / "agents" / agent_id / "sessions" / "sessions.json"


def _load_session_metadata(
    *,
    session_key: Optional[str],
    session_jsonl: Optional[Path],
    openclaw_home: Optional[Path],
    sessions_file: Optional[Path],
) -> tuple[Optional[str], Optional[dict[str, Any]], Optional[Path]]:
    resolved_sessions_file = _resolve_sessions_file(
        session_key=session_key,
        openclaw_home=openclaw_home,
        sessions_file=sessions_file,
    )
    if resolved_sessions_file is None or not resolved_sessions_file.exists():
        return session_key, None, resolved_sessions_file
    payload = _load_json(resolved_sessions_file)
    if not isinstance(payload, dict):
        return session_key, None, resolved_sessions_file
    if session_key and isinstance(payload.get(session_key), dict):
        return session_key, dict(payload[session_key]), resolved_sessions_file
    if session_jsonl is None:
        return session_key, None, resolved_sessions_file
    candidate = session_jsonl.expanduser().resolve()
    for key, entry in payload.items():
        if not isinstance(entry, dict):
            continue
        session_file = entry.get("sessionFile")
        if not session_file:
            continue
        if Path(str(session_file)).expanduser().resolve() == candidate:
            return str(key), dict(entry), resolved_sessions_file
    return session_key, None, resolved_sessions_file


def _build_static_context(metadata: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not metadata:
        return {"status": "unavailable"}
    report = metadata.get("systemPromptReport")
    if not isinstance(report, dict):
        return {"status": "missing"}
    system_prompt = report.get("systemPrompt") if isinstance(report.get("systemPrompt"), dict) else {}
    skills = report.get("skills") if isinstance(report.get("skills"), dict) else {}
    tools = report.get("tools") if isinstance(report.get("tools"), dict) else {}
    workspace_files = report.get("injectedWorkspaceFiles") if isinstance(report.get("injectedWorkspaceFiles"), list) else []

    system_prompt_chars = _as_int(system_prompt.get("chars"))
    tools_chars = _as_int(tools.get("listChars")) + _as_int(tools.get("schemaChars"))
    skills_chars = _as_int(skills.get("promptChars"))
    workspace_chars = sum(_as_int(item.get("injectedChars")) for item in workspace_files if isinstance(item, dict))
    static_total = system_prompt_chars + tools_chars + skills_chars + workspace_chars

    components = [
        {"name": "tools", "chars": tools_chars},
        {"name": "systemPrompt", "chars": system_prompt_chars},
        {"name": "workspaceBootstrap", "chars": workspace_chars},
        {"name": "skills", "chars": skills_chars},
    ]
    for item in components:
        item["sharePct"] = round((item["chars"] / static_total) * 100, 2) if static_total else 0.0
    components.sort(key=lambda item: item["chars"], reverse=True)

    top_workspace_files = [
        {
            "name": str(item.get("name") or ""),
            "path": str(item.get("path") or ""),
            "chars": _as_int(item.get("injectedChars")),
            "truncated": bool(item.get("truncated")),
        }
        for item in workspace_files
        if isinstance(item, dict)
    ]
    top_workspace_files.sort(key=lambda item: item["chars"], reverse=True)

    tool_entries = []
    for item in tools.get("entries") or []:
        if not isinstance(item, dict):
            continue
        prompt_chars = _as_int(item.get("summaryChars")) + _as_int(item.get("schemaChars"))
        tool_entries.append(
            {
                "name": str(item.get("name") or ""),
                "promptChars": prompt_chars,
                "propertiesCount": _as_int(item.get("propertiesCount")),
            }
        )
    tool_entries.sort(key=lambda item: item["promptChars"], reverse=True)

    skill_entries = []
    for item in skills.get("entries") or []:
        if not isinstance(item, dict):
            continue
        skill_entries.append(
            {
                "name": str(item.get("name") or ""),
                "chars": _as_int(item.get("blockChars")),
            }
        )
    skill_entries.sort(key=lambda item: item["chars"], reverse=True)

    return {
        "status": "ok",
        "staticTotalChars": static_total,
        "components": components,
        "topWorkspaceFiles": top_workspace_files[:8],
        "topToolEntries": tool_entries[:8],
        "topSkillEntries": skill_entries[:8],
        "provider": str(report.get("provider") or metadata.get("modelProvider") or ""),
        "model": str(report.get("model") or metadata.get("model") or ""),
        "bootstrapMaxChars": _as_int(report.get("bootstrapMaxChars")),
        "bootstrapTotalMaxChars": _as_int(report.get("bootstrapTotalMaxChars")),
    }


def _finalize_open_tool_phase(turn: dict[str, Any], *, llm_after_s: float = 0.0) -> None:
    phase = turn.get("_open_tool_phase")
    if not isinstance(phase, dict):
        return
    tool_use_time = phase.get("_tool_use_time")
    last_tool_result_time = phase.get("_last_tool_result_time")
    tool_duration_s = 0.0
    if isinstance(tool_use_time, datetime) and isinstance(last_tool_result_time, datetime):
        tool_duration_s = max(0.0, round((last_tool_result_time - tool_use_time).total_seconds(), 4))
    turn["toolDurationS"] = round(_as_float(turn.get("toolDurationS")) + tool_duration_s, 4)
    phase_payload = {
        "toolNames": sorted(set(str(name) for name in phase.get("tool_call_names") or [])),
        "toolResultCount": _as_int(phase.get("tool_result_count")),
        "llmBeforeS": round(_as_float(phase.get("llm_before_s")), 4),
        "toolDurationS": round(tool_duration_s, 4),
        "llmAfterS": round(llm_after_s, 4),
    }
    turn["toolPhases"].append(phase_payload)
    turn["toolCallCount"] = _as_int(turn.get("toolCallCount")) + len(phase.get("tool_call_names") or [])
    del turn["_open_tool_phase"]


def _finalize_turn(turn: dict[str, Any]) -> dict[str, Any]:
    _finalize_open_tool_phase(turn)
    started_at = turn.get("_started_at")
    last_event_at = turn.get("_last_event_at") or started_at
    if isinstance(started_at, datetime) and isinstance(last_event_at, datetime):
        duration_s = max(0.0, round((last_event_at - started_at).total_seconds(), 4))
    else:
        duration_s = 0.0
    llm_duration_s = round(_as_float(turn.get("llmDurationS")), 4)
    tool_duration_s = round(_as_float(turn.get("toolDurationS")), 4)
    llm_share_pct = round((llm_duration_s / duration_s) * 100, 2) if duration_s else 0.0
    tool_share_pct = round((tool_duration_s / duration_s) * 100, 2) if duration_s else 0.0
    if llm_share_pct >= 70:
        likely_bottleneck = "llm"
    elif tool_share_pct >= 60:
        likely_bottleneck = "tools"
    elif duration_s >= 8 and max(llm_share_pct, tool_share_pct) >= 40:
        likely_bottleneck = "mixed"
    else:
        likely_bottleneck = "minor"

    return {
        "turnIndex": _as_int(turn.get("turnIndex")),
        "lineNumber": _as_int(turn.get("lineNumber")),
        "startedAt": _render_dt(started_at),
        "endedAt": _render_dt(last_event_at if isinstance(last_event_at, datetime) else None),
        "userExcerpt": turn.get("userExcerpt"),
        "userChars": _as_int(turn.get("userChars")),
        "transcriptCharsBeforeTurn": _as_int(turn.get("transcriptCharsBeforeTurn")),
        "transcriptCharsAfterTurn": _as_int(turn.get("transcriptCharsAfterTurn")),
        "durationS": duration_s,
        "llmDurationS": llm_duration_s,
        "toolDurationS": tool_duration_s,
        "llmSharePct": llm_share_pct,
        "toolSharePct": tool_share_pct,
        "assistantCallCount": _as_int(turn.get("assistantCallCount")),
        "toolCallCount": _as_int(turn.get("toolCallCount")),
        "toolNames": sorted(set(str(name) for name in turn.get("toolNames") or [])),
        "toolPhases": list(turn.get("toolPhases") or []),
        "usage": {
            "input": _as_int((turn.get("usage") or {}).get("input")),
            "output": _as_int((turn.get("usage") or {}).get("output")),
            "cacheRead": _as_int((turn.get("usage") or {}).get("cacheRead")),
            "cacheWrite": _as_int((turn.get("usage") or {}).get("cacheWrite")),
            "totalTokens": _as_int((turn.get("usage") or {}).get("totalTokens")),
            "costTotal": round(_as_float(((turn.get("usage") or {}).get("cost") or {}).get("total")), 8),
        },
        "likelyBottleneck": likely_bottleneck,
        "isStartupTurn": bool(turn.get("isStartupTurn")),
    }


def build_session_latency_audit(
    *,
    session_jsonl: Path,
    session_key: Optional[str] = None,
    session_metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    resolved_session_jsonl = session_jsonl.expanduser().resolve()
    lines = resolved_session_jsonl.read_text(encoding="utf-8").splitlines()
    transcript_chars = 0
    turns: list[dict[str, Any]] = []
    current_turn: Optional[dict[str, Any]] = None
    session_header: dict[str, Any] = {}

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if line_number == 1 and payload.get("type") == "session":
            session_header = payload
        message = payload.get("message") if payload.get("type") == "message" else None
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        entry_time = _parse_timestamp(payload.get("timestamp"))
        text = _extract_text(message.get("content"))
        text_chars = len(text)

        if role == "user":
            if current_turn is not None:
                current_turn["transcriptCharsAfterTurn"] = transcript_chars
                turns.append(_finalize_turn(current_turn))
            current_turn = {
                "turnIndex": len(turns) + 1,
                "lineNumber": line_number,
                "userChars": text_chars,
                "userExcerpt": _safe_excerpt(text),
                "isStartupTurn": "A new session was started via /new or /reset" in text,
                "transcriptCharsBeforeTurn": transcript_chars,
                "assistantCallCount": 0,
                "toolCallCount": 0,
                "toolNames": [],
                "toolPhases": [],
                "llmDurationS": 0.0,
                "toolDurationS": 0.0,
                "usage": {
                    "input": 0,
                    "output": 0,
                    "cacheRead": 0,
                    "cacheWrite": 0,
                    "totalTokens": 0,
                    "cost": {"total": 0.0},
                },
                "_started_at": entry_time,
                "_last_event_at": entry_time,
                "_segment_cursor": entry_time,
            }
            transcript_chars += text_chars
            continue

        if role in {"assistant", "toolResult"} and current_turn is not None:
            current_turn["_last_event_at"] = entry_time or current_turn.get("_last_event_at")

        if role == "assistant" and current_turn is not None:
            segment_cursor = current_turn.get("_segment_cursor")
            llm_delta = 0.0
            if isinstance(segment_cursor, datetime) and isinstance(entry_time, datetime):
                llm_delta = max(0.0, round((entry_time - segment_cursor).total_seconds(), 4))
            current_turn["assistantCallCount"] = _as_int(current_turn.get("assistantCallCount")) + 1
            current_turn["llmDurationS"] = round(_as_float(current_turn.get("llmDurationS")) + llm_delta, 4)
            usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
            current_turn_usage = current_turn["usage"]
            current_turn_usage["input"] += _as_int(usage.get("input"))
            current_turn_usage["output"] += _as_int(usage.get("output"))
            current_turn_usage["cacheRead"] += _as_int(usage.get("cacheRead"))
            current_turn_usage["cacheWrite"] += _as_int(usage.get("cacheWrite"))
            current_turn_usage["totalTokens"] += _as_int(usage.get("totalTokens"))
            current_turn_usage["cost"]["total"] = round(
                _as_float(current_turn_usage["cost"]["total"])
                + _as_float((usage.get("cost") or {}).get("total")),
                8,
            )

            stop_reason = str(message.get("stopReason") or "")
            tool_names = _extract_tool_names(message.get("content"))
            current_turn["toolNames"].extend(tool_names)
            if stop_reason == "toolUse":
                _finalize_open_tool_phase(current_turn)
                current_turn["_open_tool_phase"] = {
                    "_tool_use_time": entry_time,
                    "_last_tool_result_time": None,
                    "tool_result_count": 0,
                    "llm_before_s": llm_delta,
                    "tool_call_names": tool_names,
                }
            else:
                _finalize_open_tool_phase(current_turn, llm_after_s=llm_delta)
            current_turn["_segment_cursor"] = entry_time

        elif role == "toolResult" and current_turn is not None:
            phase = current_turn.get("_open_tool_phase")
            if isinstance(phase, dict):
                phase["tool_result_count"] = _as_int(phase.get("tool_result_count")) + 1
                phase["_last_tool_result_time"] = entry_time
            current_turn["_segment_cursor"] = entry_time

        transcript_chars += text_chars

    if current_turn is not None:
        current_turn["transcriptCharsAfterTurn"] = transcript_chars
        turns.append(_finalize_turn(current_turn))

    durations = [float(turn["durationS"]) for turn in turns]
    llm_total_s = round(sum(float(turn["llmDurationS"]) for turn in turns), 4)
    tool_total_s = round(sum(float(turn["toolDurationS"]) for turn in turns), 4)
    total_duration_s = round(sum(durations), 4)
    startup_detected = bool(turns and turns[0].get("isStartupTurn"))
    startup_transcript_carryover_chars = _as_int(turns[1]["transcriptCharsBeforeTurn"]) if startup_detected and len(turns) > 1 else 0

    findings: list[dict[str, Any]] = []
    static_context = _build_static_context(session_metadata)
    if static_context.get("status") == "ok" and _as_int(static_context.get("staticTotalChars")) >= 100000:
        findings.append(
            {
                "code": "heavy-static-context",
                "severity": "warn",
                "summary": f"Static prompt surface is {_as_int(static_context.get('staticTotalChars'))} chars before transcript growth.",
            }
        )
    components = static_context.get("components") if isinstance(static_context.get("components"), list) else []
    if components and components[0].get("name") == "tools" and _as_int(components[0].get("chars")) >= 40000:
        findings.append(
            {
                "code": "tool-schema-dominates-static-context",
                "severity": "warn",
                "summary": f"Tool prompt surface is {_as_int(components[0].get('chars'))} chars and is the largest static component.",
            }
        )
    user_chars = [int(turn["userChars"]) for turn in turns]
    if user_chars and _quantile([float(value) for value in user_chars], 1, 2) >= 1200:
        findings.append(
            {
                "code": "bulky-user-wrapper",
                "severity": "warn",
                "summary": f"Median user payload is {_quantile([float(value) for value in user_chars], 1, 2)} chars, which implies wrapper-heavy turns.",
            }
        )
    if startup_transcript_carryover_chars >= 4000:
        findings.append(
            {
                "code": "startup-transcript-carryover",
                "severity": "warn",
                "summary": f"Startup turn leaves {startup_transcript_carryover_chars} chars in transcript before the first business turn.",
            }
        )
    if total_duration_s and total_duration_s >= 15 and round((llm_total_s / total_duration_s) * 100, 2) >= 70:
        findings.append(
            {
                "code": "llm-dominant-latency",
                "severity": "warn",
                "summary": f"LLM time contributes {round((llm_total_s / total_duration_s) * 100, 2)}% of measured turn latency.",
            }
        )
    max_transcript_before = max((int(turn["transcriptCharsBeforeTurn"]) for turn in turns), default=0)
    if max_transcript_before >= 12000:
        findings.append(
            {
                "code": "transcript-growth-pressure",
                "severity": "warn",
                "summary": f"Transcript reaches {max_transcript_before} chars before a user turn, so later turns pay growing history cost.",
            }
        )

    session_id = None
    session_started_at = _parse_timestamp(session_header.get("timestamp")) if session_header else None
    if session_header:
        session_id = session_header.get("id")
    if session_metadata:
        session_id = session_metadata.get("sessionId") or session_id

    return {
        "schema": AUDIT_SCHEMA,
        "generatedAt": _render_dt(_utc_now()),
        "sessionKey": session_key,
        "sessionId": str(session_id or ""),
        "sessionJsonl": str(resolved_session_jsonl),
        "sessionStartedAt": _render_dt(session_started_at),
        "metadataFound": session_metadata is not None,
        "model": str((session_metadata or {}).get("model") or ""),
        "modelProvider": str((session_metadata or {}).get("modelProvider") or ""),
        "staticContext": static_context,
        "summary": {
            "turnCount": len(turns),
            "durationS": total_duration_s,
            "llmDurationS": llm_total_s,
            "toolDurationS": tool_total_s,
            "llmSharePct": round((llm_total_s / total_duration_s) * 100, 2) if total_duration_s else 0.0,
            "toolSharePct": round((tool_total_s / total_duration_s) * 100, 2) if total_duration_s else 0.0,
            "medianTurnDurationS": _quantile(durations, 1, 2),
            "p95TurnDurationS": _quantile(durations, 95, 100),
            "maxTurnDurationS": round(max(durations), 4) if durations else 0.0,
            "startupDetected": startup_detected,
            "startupTranscriptCarryoverChars": startup_transcript_carryover_chars,
            "maxTranscriptCharsBeforeTurn": max_transcript_before,
        },
        "slowestTurns": [
            {
                "turnIndex": int(turn["turnIndex"]),
                "userExcerpt": turn.get("userExcerpt"),
                "durationS": float(turn["durationS"]),
                "llmDurationS": float(turn["llmDurationS"]),
                "toolDurationS": float(turn["toolDurationS"]),
                "likelyBottleneck": turn.get("likelyBottleneck"),
            }
            for turn in sorted(turns, key=lambda item: float(item["durationS"]), reverse=True)[:3]
        ],
        "findings": findings,
        "turns": turns,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    lines = [
        "# Session Latency Audit",
        "",
        f"- Session: `{payload.get('sessionKey') or payload.get('sessionId')}`",
        f"- Model: `{payload.get('modelProvider') or 'unknown'}/{payload.get('model') or 'unknown'}`",
        f"- Turns: `{summary.get('turnCount', 0)}`",
        f"- Total duration: `{summary.get('durationS', 0)}s`",
        f"- LLM share: `{summary.get('llmSharePct', 0)}%`",
        f"- Tool share: `{summary.get('toolSharePct', 0)}%`",
    ]
    static_context = payload.get("staticContext") if isinstance(payload.get("staticContext"), dict) else {}
    if static_context.get("status") == "ok":
        lines.extend(
            [
                f"- Static context: `{static_context.get('staticTotalChars', 0)} chars`",
                "",
                "## Static Components",
            ]
        )
        for item in static_context.get("components") or []:
            lines.append(f"- `{item['name']}`: `{item['chars']} chars` ({item['sharePct']}%)")
    findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
    if findings:
        lines.extend(["", "## Findings"])
        for item in findings:
            lines.append(f"- `{item['code']}`: {item['summary']}")
    lines.extend(["", "## Slowest Turns"])
    for turn in payload.get("slowestTurns") or []:
        lines.append(
            f"- `#{turn['turnIndex']}` `{turn['userExcerpt']}` -> `{turn['durationS']}s` "
            f"(LLM `{turn['llmDurationS']}s`, tools `{turn['toolDurationS']}s`, {turn['likelyBottleneck']})"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = ArgumentParser(description="Audit one OpenClaw session for reply latency, tool time, and context weight.")
    parser.add_argument("--session-key", help="OpenClaw session key, for example `agent:main:telegram:direct:8705812936`.")
    parser.add_argument("--session-jsonl", type=Path, help="Path to the session JSONL file.")
    parser.add_argument("--openclaw-home", type=Path, help="Override `~/.openclaw`.")
    parser.add_argument("--sessions-file", type=Path, help="Override the sessions.json file used for metadata lookup.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    args = parser.parse_args()

    if args.session_jsonl is None and not args.session_key:
        parser.error("pass either --session-jsonl or --session-key")

    session_key, session_metadata, _resolved_sessions_file = _load_session_metadata(
        session_key=args.session_key,
        session_jsonl=args.session_jsonl,
        openclaw_home=args.openclaw_home,
        sessions_file=args.sessions_file,
    )

    resolved_session_jsonl = args.session_jsonl
    if resolved_session_jsonl is None:
        if not session_metadata or not session_metadata.get("sessionFile"):
            parser.error("unable to resolve the session JSONL path from session metadata")
        resolved_session_jsonl = Path(str(session_metadata["sessionFile"]))

    payload = build_session_latency_audit(
        session_jsonl=resolved_session_jsonl,
        session_key=session_key,
        session_metadata=session_metadata,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
