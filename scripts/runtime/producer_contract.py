from __future__ import annotations

from typing import Optional

PRODUCER_CONTRACT_SCHEMA = "openclaw.task-system.producer-contract.v1"
PRODUCER_CONTRACT_VERSION = 1

PRODUCER_MODE_RECEIVE_SIDE = "receive-side-producer"
PRODUCER_MODE_DISPATCH_SIDE = "dispatch-side-priority-only"

STEERING_MODE_SESSION = "same-session-steering"
QUEUEING_MODE_AGENT = "agent-scoped-task-queue"
CONTROL_PLANE_MODE_PRIORITY = "highest-priority-lane"

_KNOWN_CHANNELS = ("feishu", "telegram", "webchat")

_CHANNEL_CAPABILITIES: dict[str, dict[str, object]] = {
    "feishu": {
        "producer_mode": PRODUCER_MODE_RECEIVE_SIDE,
        "receive_side_producer": True,
        "dispatch_side_priority_only": False,
        "pre_register_snapshot_supported": True,
        "early_ack_marker_supported": True,
        "arrival_truth_supported": True,
        "queue_identity_supported": True,
        "consumer_contract_aligned": True,
        "transport_lock_scope": "conversation-or-thread",
        "summary": "Feishu can pre-register at message receive time and reuse the snapshot before dispatch.",
    },
    "telegram": {
        "producer_mode": PRODUCER_MODE_DISPATCH_SIDE,
        "receive_side_producer": False,
        "dispatch_side_priority_only": True,
        "pre_register_snapshot_supported": False,
        "early_ack_marker_supported": False,
        "arrival_truth_supported": False,
        "queue_identity_supported": True,
        "consumer_contract_aligned": True,
        "transport_lock_scope": "dispatch",
        "summary": "Telegram currently relies on dispatch-time priority handling instead of receive-time producer snapshots.",
    },
    "webchat": {
        "producer_mode": PRODUCER_MODE_DISPATCH_SIDE,
        "receive_side_producer": False,
        "dispatch_side_priority_only": True,
        "pre_register_snapshot_supported": False,
        "early_ack_marker_supported": False,
        "arrival_truth_supported": False,
        "queue_identity_supported": True,
        "consumer_contract_aligned": True,
        "transport_lock_scope": "dispatch",
        "summary": "WebChat currently relies on dispatch-time priority handling instead of receive-time producer snapshots.",
    },
}


def known_channels() -> list[str]:
    return list(_KNOWN_CHANNELS)


def normalize_channel_name(channel: Optional[str]) -> str:
    normalized = str(channel or "").strip().lower()
    return normalized or "unknown"


def infer_channel_from_session_key(session_key: Optional[str]) -> Optional[str]:
    parts = [part for part in str(session_key or "").split(":") if part]
    if len(parts) < 4 or parts[0] != "agent":
        return None
    return normalize_channel_name(parts[2])


def _fallback_capability(channel: str) -> dict[str, object]:
    return {
        "producer_mode": PRODUCER_MODE_DISPATCH_SIDE,
        "receive_side_producer": False,
        "dispatch_side_priority_only": True,
        "pre_register_snapshot_supported": False,
        "early_ack_marker_supported": False,
        "arrival_truth_supported": False,
        "queue_identity_supported": True,
        "consumer_contract_aligned": True,
        "transport_lock_scope": "dispatch",
        "summary": (
            f"{channel} does not expose a receive-side producer in the current boundary; "
            "it falls back to dispatch-time priority handling."
        ),
    }


def build_channel_producer_contract(
    channel: str,
    *,
    session_key: Optional[str] = None,
) -> dict[str, object]:
    normalized = normalize_channel_name(channel)
    capability = dict(_CHANNEL_CAPABILITIES.get(normalized) or _fallback_capability(normalized))
    producer_mode = str(capability["producer_mode"])
    return {
        "schema": PRODUCER_CONTRACT_SCHEMA,
        "version": PRODUCER_CONTRACT_VERSION,
        "channel": normalized,
        "session_key": str(session_key or "").strip() or None,
        "producer_mode": producer_mode,
        "receive_side_producer": bool(capability["receive_side_producer"]),
        "dispatch_side_priority_only": bool(capability["dispatch_side_priority_only"]),
        "pre_register_snapshot_supported": bool(capability["pre_register_snapshot_supported"]),
        "early_ack_marker_supported": bool(capability["early_ack_marker_supported"]),
        "arrival_truth_supported": bool(capability["arrival_truth_supported"]),
        "queue_identity_supported": bool(capability["queue_identity_supported"]),
        "queue_identity_contract": "channel-neutral-queue-identity-v1",
        "pre_register_snapshot_contract": (
            "pre-register-snapshot-v1"
            if capability["pre_register_snapshot_supported"]
            else None
        ),
        "consumer_contract_aligned": bool(capability["consumer_contract_aligned"]),
        "transport_lock_scope": str(capability["transport_lock_scope"]),
        "session_message_semantics": {
            "steering_mode": STEERING_MODE_SESSION,
            "steering_summary": (
                "Subsequent user messages stay inside the same session and steer follow-up handling there."
            ),
            "queueing_mode": QUEUEING_MODE_AGENT,
            "queueing_summary": (
                "Normal user messages enter the agent-scoped task queue; execution may still serialize by lane or session."
            ),
            "control_plane_mode": CONTROL_PLANE_MODE_PRIORITY,
            "control_plane_summary": (
                "[wd], follow-up, watchdog, cancel/resume, and other task-management updates use the highest-priority control-plane lane."
            ),
        },
        "summary": str(capability["summary"]),
    }


def build_producer_contract_summary(
    *,
    channel: Optional[str] = None,
    session_key: Optional[str] = None,
    observed_channels: Optional[list[str]] = None,
) -> dict[str, object]:
    focus_channel = normalize_channel_name(channel or infer_channel_from_session_key(session_key))
    observed = [normalize_channel_name(item) for item in observed_channels or [] if str(item or "").strip()]
    if session_key and focus_channel == "unknown":
        channels = observed or known_channels()
    elif observed:
        channels = sorted({*known_channels(), *observed})
    else:
        channels = known_channels()
    if focus_channel != "unknown":
        channels = [focus_channel]
    channels = [item for index, item in enumerate(channels) if item and item not in channels[:index]]
    contracts = [
        build_channel_producer_contract(
            item,
            session_key=session_key if item == focus_channel and focus_channel != "unknown" else None,
        )
        for item in channels
    ]
    receive_side_channels = [item["channel"] for item in contracts if item["receive_side_producer"]]
    dispatch_only_channels = [item["channel"] for item in contracts if item["dispatch_side_priority_only"]]
    producer_mode_counts: dict[str, int] = {}
    for contract in contracts:
        mode = str(contract["producer_mode"])
        producer_mode_counts[mode] = producer_mode_counts.get(mode, 0) + 1
    focus_contract = contracts[0] if len(contracts) == 1 else None
    return {
        "schema": PRODUCER_CONTRACT_SCHEMA,
        "version": PRODUCER_CONTRACT_VERSION,
        "session_key": str(session_key or "").strip() or None,
        "focus_channel": focus_contract["channel"] if focus_contract else None,
        "producer_mode": focus_contract["producer_mode"] if focus_contract else None,
        "channel_count": len(contracts),
        "producer_mode_counts": producer_mode_counts,
        "receive_side_producer_channels": receive_side_channels,
        "dispatch_side_priority_only_channels": dispatch_only_channels,
        "session_message_semantics": (
            focus_contract["session_message_semantics"]
            if focus_contract
            else {
                "steering_mode": STEERING_MODE_SESSION,
                "queueing_mode": QUEUEING_MODE_AGENT,
                "control_plane_mode": CONTROL_PLANE_MODE_PRIORITY,
            }
        ),
        "contracts": contracts,
        "primary_action_kind": "phase-5-rollout",
        "primary_action_command": None,
        "runbook_status": "ok",
        "requires_action": False,
        "summary": (
            focus_contract["summary"]
            if focus_contract
            else "Producer contract is formalized; channel rollout now depends on each channel's boundary."
        ),
    }


def render_producer_contract_summary(summary: dict[str, object]) -> str:
    lines = [
        "# Producer Contract",
        "",
        f"- session_key: {summary.get('session_key') or 'all'}",
        f"- focus_channel: {summary.get('focus_channel') or 'all'}",
        f"- producer_mode: {summary.get('producer_mode') or 'mixed'}",
        f"- channel_count: {summary.get('channel_count')}",
        f"- receive_side_producer_channels: {', '.join(summary.get('receive_side_producer_channels', [])) or 'none'}",
        f"- dispatch_side_priority_only_channels: {', '.join(summary.get('dispatch_side_priority_only_channels', [])) or 'none'}",
    ]
    session_semantics = summary.get("session_message_semantics", {})
    if isinstance(session_semantics, dict):
        lines.extend(
            [
                f"- steering_mode: {session_semantics.get('steering_mode') or 'unknown'}",
                f"- queueing_mode: {session_semantics.get('queueing_mode') or 'unknown'}",
                f"- control_plane_mode: {session_semantics.get('control_plane_mode') or 'unknown'}",
            ]
        )
    contracts = summary.get("contracts", [])
    if isinstance(contracts, list) and contracts:
        lines.extend(["", "## Channels", ""])
        for contract in contracts:
            if not isinstance(contract, dict):
                continue
            lines.append(
                f"- {contract.get('channel')} | mode={contract.get('producer_mode')} | receive_side={contract.get('receive_side_producer')} | pre_register={contract.get('pre_register_snapshot_supported')} | early_ack={contract.get('early_ack_marker_supported')}"
            )
            if contract.get("summary"):
                lines.append(f"  {contract['summary']}")
    return "\n".join(lines) + "\n"
