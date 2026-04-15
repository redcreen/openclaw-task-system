#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

TASK_SCHEMA = "openclaw.task-system.task.v1"

STATUS_RECEIVED = "received"
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_BLOCKED = "blocked"
STATUS_PAUSED = "paused"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

TERMINAL_STATUSES = {STATUS_DONE, STATUS_FAILED, STATUS_CANCELLED}
ACTIVE_STATUSES = {STATUS_QUEUED, STATUS_RUNNING}
OBSERVED_STATUSES = {STATUS_RECEIVED}
RECOVERABLE_STATUSES = {STATUS_BLOCKED, STATUS_PAUSED}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
_INFLIGHT_CACHE_GENERATIONS: dict[str, int] = {}
_INFLIGHT_TASK_SNAPSHOTS: dict[str, tuple[int, list["TaskState"]]] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@dataclass(frozen=True)
class TaskPaths:
    root: Path
    data_dir: Path
    tasks_dir: Path
    inflight_dir: Path
    archive_dir: Path

    @classmethod
    def from_root(cls, root: Path, data_dir: Optional[Path] = None) -> "TaskPaths":
        resolved_root = root.resolve()
        resolved_data_dir = (data_dir or (resolved_root / "data")).resolve()
        tasks_dir = resolved_data_dir / "tasks"
        return cls(
            root=resolved_root,
            data_dir=resolved_data_dir,
            tasks_dir=tasks_dir,
            inflight_dir=tasks_dir / "inflight",
            archive_dir=tasks_dir / "archive",
        )

    def ensure_dirs(self) -> None:
        self.inflight_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)


def default_paths() -> TaskPaths:
    env_dir = os.environ.get("OPENCLAW_TASK_SYSTEM_DATA_DIR")
    data_dir = Path(env_dir).expanduser() if env_dir else DEFAULT_DATA_DIR
    return TaskPaths.from_root(PROJECT_ROOT, data_dir=data_dir)


@dataclass
class TaskState:
    schema: str = TASK_SCHEMA
    task_id: str = ""
    run_id: str = ""
    agent_id: str = ""
    session_key: str = ""
    channel: str = ""
    account_id: Optional[str] = None
    chat_id: str = ""
    user_id: Optional[str] = None
    task_label: str = ""
    status: str = STATUS_RECEIVED
    block_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    monitor_state: str = "normal"
    created_at: str = ""
    started_at: Optional[str] = None
    updated_at: str = ""
    last_user_visible_update_at: str = ""
    last_internal_touch_at: str = ""
    last_monitor_notify_at: Optional[str] = None
    notify_count: int = 0
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TaskStore:
    def __init__(self, paths: Optional[TaskPaths] = None) -> None:
        self.paths = paths or default_paths()
        self.paths.ensure_dirs()
        self._inflight_tasks_cache: Optional[list[TaskState]] = None
        self._inflight_tasks_cache_generation: Optional[int] = None

    def _inflight_cache_key(self) -> str:
        return str(self.paths.inflight_dir)

    def _invalidate_inflight_cache(self) -> None:
        self._inflight_tasks_cache = None
        self._inflight_tasks_cache_generation = None
        key = self._inflight_cache_key()
        _INFLIGHT_CACHE_GENERATIONS[key] = _INFLIGHT_CACHE_GENERATIONS.get(key, 0) + 1
        _INFLIGHT_TASK_SNAPSHOTS.pop(key, None)

    def new_task_id(self) -> str:
        return f"task_{uuid.uuid4().hex}"

    def inflight_path(self, task_id: str) -> Path:
        return self.paths.inflight_dir / f"{task_id}.json"

    def archive_path(self, task_id: str) -> Path:
        return self.paths.archive_dir / f"{task_id}.json"

    def load_task(self, task_id: str, *, allow_archive: bool = True) -> TaskState:
        inflight = self.inflight_path(task_id)
        if inflight.exists():
            return TaskState(**load_json(inflight))
        if allow_archive:
            archived = self.archive_path(task_id)
            if archived.exists():
                return TaskState(**load_json(archived))
        raise FileNotFoundError(task_id)

    def save_task(self, task: TaskState, *, archive: bool = False) -> TaskState:
        task.updated_at = task.updated_at or now_iso()
        path = self.archive_path(task.task_id) if archive else self.inflight_path(task.task_id)
        atomic_write_json(path, task.to_dict())
        self._invalidate_inflight_cache()
        return task

    def register_task(
        self,
        *,
        agent_id: str,
        session_key: str,
        channel: str,
        account_id: Optional[str] = None,
        chat_id: str,
        task_label: str,
        user_id: Optional[str] = None,
        run_id: Optional[str] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> TaskState:
        return self._create_task(
            agent_id=agent_id,
            session_key=session_key,
            channel=channel,
            account_id=account_id,
            chat_id=chat_id,
            task_label=task_label,
            user_id=user_id,
            run_id=run_id,
            meta=meta,
            status=STATUS_QUEUED,
        )

    def observe_task(
        self,
        *,
        agent_id: str,
        session_key: str,
        channel: str,
        account_id: Optional[str] = None,
        chat_id: str,
        task_label: str,
        user_id: Optional[str] = None,
        run_id: Optional[str] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> TaskState:
        return self._create_task(
            agent_id=agent_id,
            session_key=session_key,
            channel=channel,
            account_id=account_id,
            chat_id=chat_id,
            task_label=task_label,
            user_id=user_id,
            run_id=run_id,
            meta=meta,
            status=STATUS_RECEIVED,
        )

    def _create_task(
        self,
        *,
        agent_id: str,
        session_key: str,
        channel: str,
        account_id: Optional[str],
        chat_id: str,
        task_label: str,
        user_id: Optional[str],
        run_id: Optional[str],
        meta: Optional[dict[str, Any]],
        status: str,
    ) -> TaskState:
        ts = now_iso()
        task = TaskState(
            task_id=self.new_task_id(),
            run_id=run_id or uuid.uuid4().hex,
            agent_id=agent_id,
            session_key=session_key,
            channel=channel,
            account_id=account_id,
            chat_id=chat_id,
            user_id=user_id,
            task_label=task_label,
            status=status,
            created_at=ts,
            updated_at=ts,
            last_user_visible_update_at=ts,
            last_internal_touch_at=ts,
            meta=meta or {},
        )
        return self.save_task(task)

    def start_task(self, task_id: str, *, user_visible: bool = True) -> TaskState:
        task = self.load_task(task_id)
        ts = now_iso()
        task.status = STATUS_RUNNING
        task.started_at = task.started_at or ts
        task.updated_at = ts
        task.last_internal_touch_at = ts
        if user_visible:
            task.last_user_visible_update_at = ts
            task.monitor_state = "normal"
        return self.save_task(task)

    def find_running_tasks(self, *, agent_id: str) -> list[TaskState]:
        matches = self.find_inflight_tasks(
            agent_id=agent_id,
            statuses={STATUS_RUNNING},
        )
        return sorted(matches, key=lambda item: item.started_at or item.created_at)

    def find_queued_tasks(self, *, agent_id: str) -> list[TaskState]:
        matches = self.find_inflight_tasks(
            agent_id=agent_id,
            statuses={STATUS_QUEUED},
        )
        return sorted(matches, key=lambda item: item.created_at)

    def claim_execution_slot(
        self,
        task_id: str,
        *,
        user_visible: bool = True,
    ) -> TaskState:
        task = self.load_task(task_id)
        if task.status == STATUS_RUNNING:
            return task
        if self.find_running_tasks(agent_id=task.agent_id):
            if task.status != STATUS_QUEUED:
                ts = now_iso()
                task.status = STATUS_QUEUED
                task.updated_at = ts
                task.last_internal_touch_at = ts
                return self.save_task(task)
            return task
        return self.start_task(task_id, user_visible=user_visible)

    def promote_next_queued_task(
        self,
        *,
        agent_id: str,
        user_visible: bool = True,
        meta: Optional[dict[str, Any]] = None,
    ) -> Optional[TaskState]:
        if self.find_running_tasks(agent_id=agent_id):
            return None
        queued = self.find_queued_tasks(agent_id=agent_id)
        if not queued:
            return None
        promoted = self.start_task(queued[0].task_id, user_visible=user_visible)
        if meta:
            promoted.meta.update(meta)
            promoted = self.save_task(promoted)
        return promoted

    def touch_task(
        self,
        task_id: str,
        *,
        user_visible: bool = True,
        status: Optional[str] = None,
        meta: Optional[dict[str, Any]] = None,
    ) -> TaskState:
        task = self.load_task(task_id)
        ts = now_iso()
        if status:
            task.status = status
        if meta:
            task.meta.update(meta)
        task.updated_at = ts
        task.last_internal_touch_at = ts
        if user_visible:
            task.last_user_visible_update_at = ts
            task.monitor_state = "normal"
        return self.save_task(task)

    def block_task(self, task_id: str, reason: str) -> TaskState:
        task = self.load_task(task_id)
        ts = now_iso()
        task.status = STATUS_BLOCKED
        task.block_reason = reason
        task.updated_at = ts
        task.last_internal_touch_at = ts
        saved = self.save_task(task)
        self.promote_next_queued_task(
            agent_id=saved.agent_id,
            meta={"promoted_after": saved.task_id, "promotion_reason": "blocked"},
        )
        return saved

    def pause_task(self, task_id: str, reason: Optional[str] = None) -> TaskState:
        task = self.load_task(task_id)
        ts = now_iso()
        task.status = STATUS_PAUSED
        task.block_reason = reason
        task.updated_at = ts
        task.last_internal_touch_at = ts
        saved = self.save_task(task)
        self.promote_next_queued_task(
            agent_id=saved.agent_id,
            meta={"promoted_after": saved.task_id, "promotion_reason": "paused"},
        )
        return saved

    def schedule_continuation(
        self,
        task_id: str,
        *,
        continuation_kind: str,
        due_at: str,
        payload: dict[str, Any],
        reason: str,
    ) -> TaskState:
        task = self.load_task(task_id)
        ts = now_iso()
        task.status = STATUS_PAUSED
        task.block_reason = reason
        task.updated_at = ts
        task.last_internal_touch_at = ts
        task.meta["continuation_kind"] = continuation_kind
        task.meta["continuation_due_at"] = due_at
        task.meta["continuation_payload"] = payload
        task.meta["continuation_state"] = "scheduled"
        saved = self.save_task(task)
        self.promote_next_queued_task(
            agent_id=saved.agent_id,
            meta={"promoted_after": saved.task_id, "promotion_reason": "paused"},
        )
        return saved

    def resume_task(
        self,
        task_id: str,
        *,
        progress_note: Optional[str] = None,
        clear_block_reason: bool = True,
        user_visible: bool = True,
    ) -> TaskState:
        task = self.load_task(task_id)
        ts = now_iso()
        if self.find_running_tasks(agent_id=task.agent_id):
            task.status = STATUS_QUEUED
        else:
            task.status = STATUS_RUNNING
        if clear_block_reason:
            task.block_reason = None
        task.monitor_state = "normal"
        task.updated_at = ts
        task.last_internal_touch_at = ts
        if user_visible:
            task.last_user_visible_update_at = ts
        if progress_note:
            task.meta["last_progress_note"] = progress_note
        task.meta["resumed_at"] = ts
        task.meta["resume_target_status"] = task.status
        return self.save_task(task)

    def complete_task(
        self,
        task_id: str,
        *,
        archive: bool = True,
        meta: Optional[dict[str, Any]] = None,
        user_visible: bool = True,
    ) -> TaskState:
        task = self.load_task(task_id)
        ts = now_iso()
        task.status = STATUS_DONE
        task.updated_at = ts
        task.last_internal_touch_at = ts
        if user_visible:
            task.last_user_visible_update_at = ts
            task.monitor_state = "normal"
        if meta:
            task.meta.update(meta)
        return self._finalize_task(task, archive=archive)

    def fail_task(
        self,
        task_id: str,
        reason: str,
        *,
        archive: bool = True,
        user_visible: bool = True,
        meta: Optional[dict[str, Any]] = None,
    ) -> TaskState:
        task = self.load_task(task_id)
        ts = now_iso()
        task.status = STATUS_FAILED
        task.failure_reason = reason
        task.updated_at = ts
        task.last_internal_touch_at = ts
        if user_visible:
            task.last_user_visible_update_at = ts
            task.monitor_state = "normal"
        if meta:
            task.meta.update(meta)
        return self._finalize_task(task, archive=archive)

    def cancel_task(
        self,
        task_id: str,
        reason: str,
        *,
        archive: bool = True,
        user_visible: bool = True,
    ) -> TaskState:
        task = self.load_task(task_id)
        ts = now_iso()
        task.status = STATUS_CANCELLED
        task.failure_reason = reason
        task.updated_at = ts
        task.last_internal_touch_at = ts
        if user_visible:
            task.last_user_visible_update_at = ts
            task.monitor_state = "normal"
        task.meta["cancelled_at"] = ts
        task.meta["cancel_reason"] = reason
        return self._finalize_task(task, archive=archive)

    def archive_task(self, task_id: str, *, remove_inflight: bool = True) -> TaskState:
        task = self.load_task(task_id, allow_archive=False)
        archived = self.save_task(task, archive=True)
        if remove_inflight:
            self.inflight_path(task_id).unlink(missing_ok=True)
        self._invalidate_inflight_cache()
        return archived

    def list_inflight(self) -> list[Path]:
        self.paths.ensure_dirs()
        return sorted(self.paths.inflight_dir.glob("*.json"))

    def _cached_inflight_tasks(self) -> list[TaskState]:
        cache_key = self._inflight_cache_key()
        current_generation = _INFLIGHT_CACHE_GENERATIONS.get(cache_key, 0)
        if self._inflight_tasks_cache is None or self._inflight_tasks_cache_generation != current_generation:
            shared_snapshot = _INFLIGHT_TASK_SNAPSHOTS.get(cache_key)
            if shared_snapshot is not None and shared_snapshot[0] == current_generation:
                self._inflight_tasks_cache = shared_snapshot[1]
            else:
                self._inflight_tasks_cache = [self.load_task(path.stem, allow_archive=False) for path in self.list_inflight()]
                _INFLIGHT_TASK_SNAPSHOTS[cache_key] = (current_generation, self._inflight_tasks_cache)
            self._inflight_tasks_cache_generation = current_generation
        return self._inflight_tasks_cache

    def list_inflight_tasks(self) -> list[TaskState]:
        return list(self._cached_inflight_tasks())

    def find_inflight_tasks(
        self,
        *,
        agent_id: Optional[str] = None,
        session_key: Optional[str] = None,
        statuses: Optional[set[str]] = None,
    ) -> list[TaskState]:
        matched: list[TaskState] = []
        for task in self._cached_inflight_tasks():
            if agent_id is not None and task.agent_id != agent_id:
                continue
            if session_key is not None and task.session_key != session_key:
                continue
            if statuses is not None and task.status not in statuses:
                continue
            matched.append(task)
        return sorted(matched, key=lambda item: item.updated_at, reverse=True)

    def find_latest_active_task(
        self,
        *,
        agent_id: str,
        session_key: str,
    ) -> Optional[TaskState]:
        matches = self.find_inflight_tasks(
            agent_id=agent_id,
            session_key=session_key,
            statuses=ACTIVE_STATUSES,
        )
        return matches[0] if matches else None

    def find_latest_recoverable_task(
        self,
        *,
        agent_id: str,
        session_key: str,
    ) -> Optional[TaskState]:
        matches = self.find_inflight_tasks(
            agent_id=agent_id,
            session_key=session_key,
            statuses=RECOVERABLE_STATUSES,
        )
        return matches[0] if matches else None

    def find_latest_observed_task(
        self,
        *,
        agent_id: str,
        session_key: str,
    ) -> Optional[TaskState]:
        matches = self.find_inflight_tasks(
            agent_id=agent_id,
            session_key=session_key,
            statuses=OBSERVED_STATUSES,
        )
        return matches[0] if matches else None

    def _finalize_task(self, task: TaskState, *, archive: bool) -> TaskState:
        agent_id = task.agent_id
        saved = self.save_task(task)
        if archive:
            self.archive_task(saved.task_id)
            saved = self.load_task(saved.task_id)
        self.promote_next_queued_task(
            agent_id=agent_id,
            meta={"promoted_after": saved.task_id, "promotion_reason": saved.status},
        )
        return saved


def list_inflight(paths: Optional[TaskPaths] = None) -> list[Path]:
    return TaskStore(paths=paths).list_inflight()


if __name__ == "__main__":
    store = TaskStore()
    sample = store.register_task(
        agent_id="main",
        session_key="agent:main:feishu:direct:sample",
        channel="feishu",
        chat_id="user:sample",
        user_id="ou_sample",
        task_label="sample task",
        meta={"source": "manual-test"},
    )
    store.start_task(sample.task_id)
    print(sample.task_id)
