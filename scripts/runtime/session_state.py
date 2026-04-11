#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from task_state import TaskPaths, atomic_write_json, load_json, now_iso

SESSION_STATE_SCHEMA = "openclaw.task-system.session-state.v1"
SESSION_STATE_VERSION = 1

COLLECTING_STATUS_COLLECTING = "collecting"
COLLECTING_STATUS_CLAIMED = "claimed"
COLLECTING_STATUS_MATERIALIZED = "materialized"
COLLECTING_STATUS_EXPIRED_EMPTY = "expired-empty"


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class SessionStateStore:
    def __init__(self, *, paths: TaskPaths) -> None:
        self.paths = paths
        self.dir = self.paths.data_dir / "sessions"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, session_key: str) -> Path:
        digest = hashlib.sha1(str(session_key or "").encode("utf-8")).hexdigest()
        return self.dir / f"{digest}.json"

    def load(self, session_key: str) -> Optional[dict[str, Any]]:
        path = self._path_for(session_key)
        if not path.exists():
            return None
        payload = load_json(path)
        if str(payload.get("session_key") or "").strip() != str(session_key or "").strip():
            return None
        return payload

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        path = self._path_for(str(payload.get("session_key") or ""))
        atomic_write_json(path, payload)
        return payload

    def load_collecting_state(self, *, agent_id: str, session_key: str) -> Optional[dict[str, Any]]:
        state = self.load(session_key)
        if not state or str(state.get("agent_id") or "").strip() != str(agent_id or "").strip():
            return None
        collecting = state.get("same_session_collecting")
        if not isinstance(collecting, dict):
            return None
        expires_at = _parse_iso8601(str(collecting.get("expires_at") or "").strip())
        if str(collecting.get("status") or "").strip() == COLLECTING_STATUS_COLLECTING and expires_at:
            now_dt = datetime.now(timezone.utc).astimezone()
            if expires_at <= now_dt:
                collecting["status"] = COLLECTING_STATUS_EXPIRED_EMPTY
                collecting["expired_at"] = now_dt.isoformat()
                state["same_session_collecting"] = collecting
                self.save(state)
        return state

    def activate_collecting_window(
        self,
        *,
        agent_id: str,
        session_key: str,
        channel: str,
        account_id: Optional[str],
        chat_id: str,
        user_id: Optional[str],
        window_seconds: int,
        activation_message: str,
        existing_task_id: Optional[str] = None,
    ) -> dict[str, Any]:
        now_dt = datetime.now(timezone.utc).astimezone()
        existing = self.load(session_key) or {
            "schema": SESSION_STATE_SCHEMA,
            "version": SESSION_STATE_VERSION,
            "agent_id": agent_id,
            "session_key": session_key,
            "channel": channel,
            "account_id": account_id,
            "chat_id": chat_id,
            "user_id": user_id,
        }
        collecting = existing.get("same_session_collecting") if isinstance(existing.get("same_session_collecting"), dict) else {}
        buffered_messages = collecting.get("buffered_user_messages") if isinstance(collecting.get("buffered_user_messages"), list) else []
        expires_at = (now_dt + timedelta(seconds=max(1, int(window_seconds)))).isoformat()
        existing["same_session_collecting"] = {
            "status": COLLECTING_STATUS_COLLECTING,
            "activated_at": collecting.get("activated_at") or now_dt.isoformat(),
            "last_message_at": now_dt.isoformat(),
            "expires_at": expires_at,
            "window_seconds": max(1, int(window_seconds)),
            "activation_message": str(activation_message or "").strip()[:240] or None,
            "buffered_user_messages": [str(item)[:4000] for item in buffered_messages if str(item or "").strip()],
            "buffered_message_count": len(buffered_messages),
            "existing_task_id": str(existing_task_id or "").strip() or None,
            "claimed_at": None,
            "materialized_at": None,
            "materialized_task_id": None,
            "materialization_reason": None,
            "expired_at": None,
        }
        existing["updated_at"] = now_dt.isoformat()
        return self.save(existing)

    def append_collecting_message(
        self,
        *,
        agent_id: str,
        session_key: str,
        message: str,
        refresh_window_seconds: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:
        state = self.load_collecting_state(agent_id=agent_id, session_key=session_key)
        if not state:
            return None
        collecting = state.get("same_session_collecting")
        if not isinstance(collecting, dict):
            return None
        if str(collecting.get("status") or "").strip() != COLLECTING_STATUS_COLLECTING:
            return None
        normalized = str(message or "").strip()
        if not normalized:
            return state
        now_dt = datetime.now(timezone.utc).astimezone()
        buffered = collecting.get("buffered_user_messages") if isinstance(collecting.get("buffered_user_messages"), list) else []
        buffered = [str(item)[:4000] for item in buffered if str(item or "").strip()]
        buffered.append(normalized[:4000])
        collecting["buffered_user_messages"] = buffered
        collecting["buffered_message_count"] = len(buffered)
        collecting["last_message_at"] = now_dt.isoformat()
        if refresh_window_seconds is not None:
            collecting["window_seconds"] = max(1, int(refresh_window_seconds))
            collecting["expires_at"] = (now_dt + timedelta(seconds=max(1, int(refresh_window_seconds)))).isoformat()
        state["same_session_collecting"] = collecting
        state["updated_at"] = now_dt.isoformat()
        return self.save(state)

    def claim_due_collecting_windows(self) -> list[dict[str, Any]]:
        now_dt = datetime.now(timezone.utc).astimezone()
        claimed: list[dict[str, Any]] = []
        for path in sorted(self.dir.glob("*.json")):
            payload = load_json(path)
            collecting = payload.get("same_session_collecting")
            if not isinstance(collecting, dict):
                continue
            if str(collecting.get("status") or "").strip() != COLLECTING_STATUS_COLLECTING:
                continue
            expires_at = _parse_iso8601(str(collecting.get("expires_at") or "").strip())
            if not expires_at or expires_at > now_dt:
                continue
            buffered = collecting.get("buffered_user_messages") if isinstance(collecting.get("buffered_user_messages"), list) else []
            existing_task_id = str(collecting.get("existing_task_id") or "").strip()
            if not buffered and not existing_task_id:
                collecting["status"] = COLLECTING_STATUS_EXPIRED_EMPTY
                collecting["expired_at"] = now_dt.isoformat()
                payload["same_session_collecting"] = collecting
                payload["updated_at"] = now_dt.isoformat()
                self.save(payload)
                continue
            collecting["status"] = COLLECTING_STATUS_CLAIMED
            collecting["claimed_at"] = now_dt.isoformat()
            payload["same_session_collecting"] = collecting
            payload["updated_at"] = now_dt.isoformat()
            claimed.append(self.save(payload))
        return claimed

    def complete_collecting_window(
        self,
        *,
        session_key: str,
        materialized_task_id: Optional[str],
        materialization_reason: str,
    ) -> Optional[dict[str, Any]]:
        state = self.load(session_key)
        if not state:
            return None
        collecting = state.get("same_session_collecting")
        if not isinstance(collecting, dict):
            return state
        now_dt = datetime.now(timezone.utc).astimezone()
        collecting["status"] = COLLECTING_STATUS_MATERIALIZED
        collecting["materialized_at"] = now_dt.isoformat()
        collecting["materialized_task_id"] = str(materialized_task_id or "").strip() or None
        collecting["materialization_reason"] = str(materialization_reason or "").strip() or None
        state["same_session_collecting"] = collecting
        state["updated_at"] = now_dt.isoformat()
        return self.save(state)
