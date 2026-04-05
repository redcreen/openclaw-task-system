from __future__ import annotations

from typing import Optional

from producer_contract import (
    build_channel_producer_contract,
    infer_channel_from_session_key,
    known_channels,
    normalize_channel_name,
)

CHANNEL_ACCEPTANCE_SCHEMA = "openclaw.task-system.channel-acceptance.v1"
CHANNEL_ACCEPTANCE_VERSION = 1

ROLLOUT_STATUS_VALIDATED = "validated"
ROLLOUT_STATUS_ACCEPTED_WITH_BOUNDARY = "accepted-with-boundary"

ACCEPTANCE_SCOPE_RECEIVE_SIDE = "receive-side-contract"
ACCEPTANCE_SCOPE_DISPATCH_SIDE = "dispatch-side-contract"


def build_channel_acceptance_entry(
    channel: str,
    *,
    session_key: Optional[str] = None,
) -> dict[str, object]:
    contract = build_channel_producer_contract(channel, session_key=session_key)
    normalized_channel = str(contract["channel"])
    receive_side = bool(contract["receive_side_producer"])
    rollout_status = ROLLOUT_STATUS_VALIDATED if receive_side else ROLLOUT_STATUS_ACCEPTED_WITH_BOUNDARY
    acceptance_scope = ACCEPTANCE_SCOPE_RECEIVE_SIDE if receive_side else ACCEPTANCE_SCOPE_DISPATCH_SIDE
    receive_time_gap = not receive_side
    limitation_summary = (
        "This channel does not expose a receive-side producer inside the current integration boundary; "
        "Phase 5 accepts the dispatch-side first-priority contract as the shipped behavior."
        if receive_time_gap
        else "This channel satisfies the current receive-side producer contract."
    )
    summary = (
        f"{normalized_channel} is validated against the receive-side producer contract."
        if receive_side
        else f"{normalized_channel} is accepted with a dispatch-side priority boundary under the current contract."
    )
    return {
        "schema": CHANNEL_ACCEPTANCE_SCHEMA,
        "version": CHANNEL_ACCEPTANCE_VERSION,
        "channel": normalized_channel,
        "session_key": str(session_key or "").strip() or None,
        "producer_mode": contract["producer_mode"],
        "rollout_status": rollout_status,
        "acceptance_scope": acceptance_scope,
        "control_plane_layered": True,
        "meets_current_contract": True,
        "receive_time_gap": receive_time_gap,
        "limitation_summary": limitation_summary,
        "summary": summary,
        "contract": contract,
    }


def build_channel_acceptance_summary(
    *,
    channel: Optional[str] = None,
    session_key: Optional[str] = None,
    observed_channels: Optional[list[str]] = None,
) -> dict[str, object]:
    normalized_session_key = str(session_key or "").strip() or None
    focus_channel = normalize_channel_name(channel or infer_channel_from_session_key(normalized_session_key))
    observed = [normalize_channel_name(item) for item in observed_channels or [] if str(item or "").strip()]
    if normalized_session_key and focus_channel == "unknown":
        channels = observed or known_channels()
    elif observed:
        channels = sorted({*known_channels(), *observed})
    else:
        channels = known_channels()
    if focus_channel != "unknown":
        channels = [focus_channel]
    channels = [item for index, item in enumerate(channels) if item and item not in channels[:index]]
    entries = [
        build_channel_acceptance_entry(
            item,
            session_key=normalized_session_key if item == focus_channel and focus_channel != "unknown" else None,
        )
        for item in channels
    ]
    validated_channels = [entry["channel"] for entry in entries if entry["rollout_status"] == ROLLOUT_STATUS_VALIDATED]
    bounded_channels = [
        entry["channel"] for entry in entries if entry["rollout_status"] == ROLLOUT_STATUS_ACCEPTED_WITH_BOUNDARY
    ]
    focus_entry = entries[0] if len(entries) == 1 else None
    return {
        "schema": CHANNEL_ACCEPTANCE_SCHEMA,
        "version": CHANNEL_ACCEPTANCE_VERSION,
        "session_key": normalized_session_key,
        "focus_channel": focus_entry["channel"] if focus_entry else None,
        "phase_status": "complete",
        "phase_complete": True,
        "channel_count": len(entries),
        "validated_channel_count": len(validated_channels),
        "bounded_channel_count": len(bounded_channels),
        "validated_channels": validated_channels,
        "bounded_channels": bounded_channels,
        "control_plane_layered_channels": [entry["channel"] for entry in entries if entry["control_plane_layered"]],
        "channels_meet_current_contract": all(bool(entry["meets_current_contract"]) for entry in entries),
        "receive_time_gap_channels": [entry["channel"] for entry in entries if entry["receive_time_gap"]],
        "entries": entries,
        "focus_rollout_status": focus_entry["rollout_status"] if focus_entry else None,
        "focus_producer_mode": focus_entry["producer_mode"] if focus_entry else None,
        "primary_action_kind": "phase-5-complete",
        "primary_action_command": None,
        "runbook_status": "ok",
        "requires_action": False,
        "summary": (
            focus_entry["summary"]
            if focus_entry
            else "Phase 5 is complete: each supported channel is landed against the current producer contract and acceptance boundary."
        ),
    }


def render_channel_acceptance_summary(summary: dict[str, object]) -> str:
    lines = [
        "# Channel Acceptance",
        "",
        f"- session_key: {summary.get('session_key') or 'all'}",
        f"- focus_channel: {summary.get('focus_channel') or 'all'}",
        f"- phase_status: {summary.get('phase_status')}",
        f"- phase_complete: {summary.get('phase_complete')}",
        f"- channel_count: {summary.get('channel_count')}",
        f"- validated_channel_count: {summary.get('validated_channel_count')}",
        f"- bounded_channel_count: {summary.get('bounded_channel_count')}",
        f"- validated_channels: {', '.join(summary.get('validated_channels', [])) or 'none'}",
        f"- bounded_channels: {', '.join(summary.get('bounded_channels', [])) or 'none'}",
        f"- receive_time_gap_channels: {', '.join(summary.get('receive_time_gap_channels', [])) or 'none'}",
    ]
    entries = summary.get("entries", [])
    if isinstance(entries, list) and entries:
        lines.extend(["", "## Channels", ""])
        for entry in entries:
            lines.append(
                "- "
                + " | ".join(
                    [
                        str(entry.get("channel") or "unknown"),
                        str(entry.get("rollout_status") or "unknown"),
                        str(entry.get("producer_mode") or "unknown"),
                        str(entry.get("acceptance_scope") or "unknown"),
                    ]
                )
            )
            lines.append(f"  summary: {entry.get('summary')}")
            lines.append(f"  limitation: {entry.get('limitation_summary')}")
    return "\n".join(lines) + "\n"
