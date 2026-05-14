"""Project-level task persistence: registry + journal."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

TaskStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
TaskKind = Literal[
    "chapter_generate", "outline_generate", "chapter_review", "chapter_polish"
]


class TaskCard(BaseModel):
    id: str
    kind: TaskKind
    status: TaskStatus = "pending"
    project_name: str
    chapter_num: int | None = None
    pipeline_id: str = ""
    steps_requested: list[str] = Field(default_factory=list)
    steps_completed: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectRegistry(BaseModel):
    version: int = 1
    project_name: str = ""
    created_at: str = ""
    updated_at: str = ""
    tasks: list[TaskCard] = Field(default_factory=list)


class JournalEntry(BaseModel):
    ts: str
    kind: str
    task_id: str | None = None
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write(path: Path, data: str) -> None:
    """Write data to path atomically via temp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        os.write(fd, data.encode("utf-8"))
        os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        os.close(fd) if not os.get_inheritable(fd) else None
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class ProjectRepository:
    """Task registry + journal persistence for a single project."""

    def __init__(self, projects_dir: Path, project_name: str) -> None:
        self._root = projects_dir / project_name
        self._project_name = project_name
        self._registry_path = self._root / "registry.json"
        self._journal_path = self._root / "journal.jsonl"

    @property
    def root(self) -> Path:
        return self._root

    def _load_registry(self) -> ProjectRegistry:
        if not self._registry_path.is_file():
            now = _now_iso()
            return ProjectRegistry(
                project_name=self._project_name,
                created_at=now,
                updated_at=now,
            )
        raw = self._registry_path.read_text(encoding="utf-8")
        return ProjectRegistry.model_validate_json(raw)

    def _save_registry(self, registry: ProjectRegistry) -> None:
        registry.updated_at = _now_iso()
        _atomic_write(self._registry_path, registry.model_dump_json(indent=2))

    def create_task(
        self,
        kind: TaskKind,
        *,
        chapter_num: int | None = None,
        pipeline_id: str = "",
        steps: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskCard:
        now = _now_iso()
        task = TaskCard(
            id=uuid4().hex[:12],
            kind=kind,
            status="pending",
            project_name=self._project_name,
            chapter_num=chapter_num,
            pipeline_id=pipeline_id,
            steps_requested=steps or [],
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        registry = self._load_registry()
        registry.tasks.append(task)
        self._save_registry(registry)

        self.append_journal(
            kind="task.created",
            summary=f"{task.kind} task created",
            task_id=task.id,
            metadata={"chapter_num": chapter_num, "pipeline_id": pipeline_id},
        )
        return task

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        *,
        error: str | None = None,
        steps_completed: list[str] | None = None,
        metadata_updates: dict[str, Any] | None = None,
    ) -> TaskCard | None:
        registry = self._load_registry()
        for task in registry.tasks:
            if task.id == task_id:
                task.status = status
                task.updated_at = _now_iso()
                if error is not None:
                    task.error = error
                if steps_completed is not None:
                    task.steps_completed = steps_completed
                if metadata_updates:
                    task.metadata.update(metadata_updates)
                self._save_registry(registry)
                self.append_journal(
                    kind=f"task.{status}",
                    summary=f"Task {task_id} → {status}",
                    task_id=task_id,
                    metadata={"error": error} if error else {},
                )
                return task
        return None

    def get_task(self, task_id: str) -> TaskCard | None:
        registry = self._load_registry()
        for task in registry.tasks:
            if task.id == task_id:
                return task
        return None

    def list_tasks(
        self,
        *,
        status: TaskStatus | None = None,
        kind: TaskKind | None = None,
        limit: int = 50,
    ) -> list[TaskCard]:
        registry = self._load_registry()
        tasks = registry.tasks
        if status:
            tasks = [t for t in tasks if t.status == status]
        if kind:
            tasks = [t for t in tasks if t.kind == kind]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)[:limit]

    def append_journal(
        self,
        kind: str,
        summary: str,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> JournalEntry:
        entry = JournalEntry(
            ts=_now_iso(),
            kind=kind,
            task_id=task_id,
            summary=summary,
            metadata=metadata or {},
        )
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._journal_path, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        return entry

    def load_journal(self, limit: int = 50) -> list[JournalEntry]:
        if not self._journal_path.is_file():
            return []
        entries: list[JournalEntry] = []
        for line in self._journal_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                entries.append(JournalEntry.model_validate(data))
            except Exception:
                log.debug("Skipping malformed journal line: %s", line[:80])
        return entries[-limit:]


def recover_interrupted_tasks(projects_dir: Path) -> int:
    """Mark tasks stuck in 'running' as 'failed' after a restart.

    Returns the number of tasks recovered.
    """
    count = 0
    if not projects_dir.is_dir():
        return count
    for project_dir in sorted(projects_dir.iterdir()):
        registry_path = project_dir / "registry.json"
        if not registry_path.is_file():
            continue
        repo = ProjectRepository(projects_dir, project_dir.name)
        registry = repo._load_registry()
        changed = False
        for task in registry.tasks:
            if task.status == "running":
                task.status = "failed"
                task.error = "Interrupted by service restart"
                task.updated_at = _now_iso()
                changed = True
                count += 1
                repo.append_journal(
                    kind="task.interrupted",
                    summary=f"Task {task.id} interrupted by restart",
                    task_id=task.id,
                )
        if changed:
            repo._save_registry(registry)
    return count
