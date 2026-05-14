"""Tests for project repository persistence layer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.projects.repository import (
    JournalEntry,
    ProjectRepository,
    recover_interrupted_tasks,
)


@pytest.fixture
def repo(tmp_path: Path) -> ProjectRepository:
    project_dir = tmp_path / "test-novel"
    project_dir.mkdir()
    return ProjectRepository(tmp_path, "test-novel")


class TestCreateTask:
    def test_creates_and_persists(self, repo: ProjectRepository):
        task = repo.create_task(
            "chapter_generate",
            chapter_num=1,
            pipeline_id="abc123",
            steps=["A", "B", "C"],
        )
        assert task.kind == "chapter_generate"
        assert task.status == "pending"
        assert task.chapter_num == 1
        assert task.pipeline_id == "abc123"
        assert task.steps_requested == ["A", "B", "C"]
        assert len(task.id) == 12

        reloaded = repo.get_task(task.id)
        assert reloaded is not None
        assert reloaded.id == task.id
        assert reloaded.status == "pending"

    def test_creates_with_metadata(self, repo: ProjectRepository):
        task = repo.create_task(
            "outline_generate",
            metadata={"synopsis": "A story about...", "guidance": "make it epic"},
        )
        assert task.metadata["synopsis"] == "A story about..."

    def test_writes_journal_entry(self, repo: ProjectRepository):
        repo.create_task("chapter_review", chapter_num=3)
        entries = repo.load_journal()
        assert len(entries) == 1
        assert entries[0].kind == "task.created"
        assert entries[0].task_id is not None


class TestUpdateTaskStatus:
    def test_pending_to_running(self, repo: ProjectRepository):
        task = repo.create_task("chapter_generate", chapter_num=1)
        updated = repo.update_task_status(task.id, "running")
        assert updated is not None
        assert updated.status == "running"

        reloaded = repo.get_task(task.id)
        assert reloaded is not None
        assert reloaded.status == "running"

    def test_running_to_completed(self, repo: ProjectRepository):
        task = repo.create_task("chapter_generate", chapter_num=1, steps=["A", "B"])
        repo.update_task_status(task.id, "running")
        updated = repo.update_task_status(
            task.id, "completed", steps_completed=["A", "B"]
        )
        assert updated is not None
        assert updated.status == "completed"
        assert updated.steps_completed == ["A", "B"]

    def test_running_to_failed_with_error(self, repo: ProjectRepository):
        task = repo.create_task("chapter_generate", chapter_num=1)
        repo.update_task_status(task.id, "running")
        updated = repo.update_task_status(
            task.id, "failed", error="LLM timeout"
        )
        assert updated is not None
        assert updated.status == "failed"
        assert updated.error == "LLM timeout"

    def test_nonexistent_task_returns_none(self, repo: ProjectRepository):
        result = repo.update_task_status("nonexistent", "running")
        assert result is None

    def test_writes_journal_entries(self, repo: ProjectRepository):
        task = repo.create_task("chapter_generate", chapter_num=1)
        repo.update_task_status(task.id, "running")
        repo.update_task_status(task.id, "completed")
        entries = repo.load_journal()
        kinds = [e.kind for e in entries]
        assert "task.created" in kinds
        assert "task.running" in kinds
        assert "task.completed" in kinds


class TestGetTask:
    def test_returns_none_for_nonexistent(self, repo: ProjectRepository):
        assert repo.get_task("nonexistent") is None

    def test_returns_task(self, repo: ProjectRepository):
        task = repo.create_task("chapter_polish", chapter_num=2)
        found = repo.get_task(task.id)
        assert found is not None
        assert found.kind == "chapter_polish"


class TestListTasks:
    def test_empty_registry(self, repo: ProjectRepository):
        assert repo.list_tasks() == []

    def test_returns_all_tasks(self, repo: ProjectRepository):
        repo.create_task("chapter_generate", chapter_num=1)
        repo.create_task("chapter_review", chapter_num=1)
        repo.create_task("outline_generate")
        tasks = repo.list_tasks()
        assert len(tasks) == 3

    def test_filter_by_status(self, repo: ProjectRepository):
        t1 = repo.create_task("chapter_generate", chapter_num=1)
        repo.create_task("chapter_review", chapter_num=1)
        repo.update_task_status(t1.id, "running")
        running = repo.list_tasks(status="running")
        assert len(running) == 1
        assert running[0].id == t1.id

    def test_filter_by_kind(self, repo: ProjectRepository):
        repo.create_task("chapter_generate", chapter_num=1)
        repo.create_task("outline_generate")
        outlines = repo.list_tasks(kind="outline_generate")
        assert len(outlines) == 1
        assert outlines[0].kind == "outline_generate"

    def test_limit(self, repo: ProjectRepository):
        for i in range(10):
            repo.create_task("chapter_generate", chapter_num=i + 1)
        tasks = repo.list_tasks(limit=3)
        assert len(tasks) == 3

    def test_sorted_by_created_at_descending(self, repo: ProjectRepository):
        repo.create_task("chapter_generate", chapter_num=1)
        repo.create_task("chapter_generate", chapter_num=2)
        repo.create_task("chapter_generate", chapter_num=3)
        tasks = repo.list_tasks()
        assert tasks[0].chapter_num == 3
        assert tasks[2].chapter_num == 1


class TestJournal:
    def test_append_and_load(self, repo: ProjectRepository):
        repo.append_journal("test.event", "Something happened")
        repo.append_journal("test.event2", "Another thing", task_id="abc")
        entries = repo.load_journal()
        assert len(entries) == 2
        assert entries[0].kind == "test.event"
        assert entries[1].task_id == "abc"

    def test_load_with_limit(self, repo: ProjectRepository):
        for i in range(20):
            repo.append_journal("event", f"Event {i}")
        entries = repo.load_journal(limit=5)
        assert len(entries) == 5
        assert entries[-1].summary == "Event 19"

    def test_load_empty_file(self, repo: ProjectRepository):
        assert repo.load_journal() == []

    def test_tolerates_old_format(self, repo: ProjectRepository):
        journal_path = repo._journal_path
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(journal_path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "chapter.finalized", "ts": "2025-01-01T00:00:00", "chapter_num": 1}) + "\n")
            f.write(json.dumps({"ts": "2025-01-02", "kind": "task.created", "summary": "new"}) + "\n")
        entries = repo.load_journal()
        assert len(entries) >= 1
        valid = [e for e in entries if e.kind == "task.created"]
        assert len(valid) == 1

    def test_tolerates_malformed_lines(self, repo: ProjectRepository):
        journal_path = repo._journal_path
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        with open(journal_path, "w", encoding="utf-8") as f:
            f.write("not json at all\n")
            f.write(json.dumps({"ts": "2025-01-01", "kind": "ok", "summary": "fine"}) + "\n")
        entries = repo.load_journal()
        assert len(entries) == 1
        assert entries[0].kind == "ok"


class TestAtomicWrite:
    def test_registry_survives_reload(self, tmp_path: Path):
        project_dir = tmp_path / "novel"
        project_dir.mkdir()
        repo1 = ProjectRepository(tmp_path, "novel")
        repo1.create_task("chapter_generate", chapter_num=1)

        repo2 = ProjectRepository(tmp_path, "novel")
        tasks = repo2.list_tasks()
        assert len(tasks) == 1

    def test_registry_json_is_valid(self, repo: ProjectRepository):
        repo.create_task("chapter_generate", chapter_num=1)
        raw = repo._registry_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["version"] == 1
        assert len(data["tasks"]) == 1


class TestRecoverInterruptedTasks:
    def test_marks_running_as_failed(self, tmp_path: Path):
        project_dir = tmp_path / "novel"
        project_dir.mkdir()
        repo = ProjectRepository(tmp_path, "novel")
        t1 = repo.create_task("chapter_generate", chapter_num=1)
        repo.update_task_status(t1.id, "running")
        t2 = repo.create_task("chapter_review", chapter_num=1)
        repo.update_task_status(t2.id, "completed")

        count = recover_interrupted_tasks(tmp_path)
        assert count == 1

        recovered = repo.get_task(t1.id)
        assert recovered is not None
        assert recovered.status == "failed"
        assert recovered.error == "Interrupted by service restart"

        unchanged = repo.get_task(t2.id)
        assert unchanged is not None
        assert unchanged.status == "completed"

    def test_no_projects(self, tmp_path: Path):
        assert recover_interrupted_tasks(tmp_path) == 0

    def test_no_registry(self, tmp_path: Path):
        (tmp_path / "novel").mkdir()
        assert recover_interrupted_tasks(tmp_path) == 0

    def test_multiple_projects(self, tmp_path: Path):
        for name in ["novel-a", "novel-b"]:
            (tmp_path / name).mkdir()
            repo = ProjectRepository(tmp_path, name)
            task = repo.create_task("chapter_generate", chapter_num=1)
            repo.update_task_status(task.id, "running")

        count = recover_interrupted_tasks(tmp_path)
        assert count == 2
