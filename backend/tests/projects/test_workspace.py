"""Tests for project workspace."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.projects.workspace import ProjectWorkspace, ensure_project, list_projects


@pytest.fixture
def workspace(tmp_path: Path) -> ProjectWorkspace:
    ws = ProjectWorkspace(tmp_path, "test-novel")
    ws.ensure()
    return ws


class TestEnsure:
    def test_creates_all_directories(self, workspace: ProjectWorkspace):
        root = workspace.root
        assert (root / "bible" / "characters").is_dir()
        assert (root / "bible" / "worldbuilding").is_dir()
        assert (root / "bible" / "plot").is_dir()
        assert (root / "plans").is_dir()
        assert (root / "chapters").is_dir()
        assert (root / "reviews").is_dir()
        assert (root / "vectorstore").is_dir()

    def test_idempotent(self, workspace: ProjectWorkspace):
        workspace.ensure()
        workspace.ensure()
        assert workspace.root.is_dir()


class TestFileIO:
    def test_read_nonexistent_returns_empty(self, workspace: ProjectWorkspace):
        assert workspace.read_file("missing.md") == ""

    def test_write_and_read(self, workspace: ProjectWorkspace):
        workspace.write_file("chapters/ch01.md", "第一章内容")
        content = workspace.read_file("chapters/ch01.md")
        assert content == "第一章内容"

    def test_write_creates_parent_dirs(self, workspace: ProjectWorkspace):
        workspace.write_file("deep/nested/file.txt", "content")
        assert workspace.read_file("deep/nested/file.txt") == "content"

    def test_path_traversal_rejected(self, workspace: ProjectWorkspace):
        with pytest.raises(ValueError, match="traversal"):
            workspace.read_file("../escape.txt")

    def test_path_traversal_write_rejected(self, workspace: ProjectWorkspace):
        with pytest.raises(ValueError, match="traversal"):
            workspace.write_file("../../etc/passwd", "hacked")


class TestJournal:
    def test_append_writes_jsonl(self, workspace: ProjectWorkspace):
        workspace.append_journal({"type": "test", "data": "hello"})
        workspace.append_journal({"type": "test2", "data": "world"})
        journal = workspace.root / "journal.jsonl"
        lines = journal.read_text().strip().splitlines()
        assert len(lines) == 2
        first = json.loads(lines[0])
        assert first["type"] == "test"
        assert "ts" in first


class TestListChapters:
    def test_empty_initially(self, workspace: ProjectWorkspace):
        assert workspace.list_chapters() == []

    def test_discovers_chapters(self, workspace: ProjectWorkspace):
        workspace.write_file("chapters/ch01.md", "one")
        workspace.write_file("chapters/ch03.md", "three")
        workspace.write_file("chapters/ch02.md", "two")
        assert workspace.list_chapters() == [1, 2, 3]


class TestPaths:
    def test_chapter_path(self, workspace: ProjectWorkspace):
        assert workspace.chapter_path(1).name == "ch01.md"
        assert workspace.chapter_path(12).name == "ch12.md"

    def test_plan_path(self, workspace: ProjectWorkspace):
        assert workspace.plan_path(5).name == "ch05-plan.md"

    def test_review_path(self, workspace: ProjectWorkspace):
        assert workspace.review_path(7).name == "ch07-review.md"


class TestEnsureProject:
    def test_creates_and_returns_workspace(self, tmp_path: Path):
        ws = ensure_project(tmp_path, "my-novel")
        assert ws.root.is_dir()
        assert (ws.root / "chapters").is_dir()


class TestListProjects:
    def test_lists_directories(self, tmp_path: Path):
        (tmp_path / "novel-a").mkdir()
        (tmp_path / "novel-b").mkdir()
        (tmp_path / ".hidden").mkdir()
        result = list_projects(tmp_path)
        assert result == ["novel-a", "novel-b"]

    def test_empty_dir(self, tmp_path: Path):
        assert list_projects(tmp_path) == []

    def test_nonexistent_dir(self):
        assert list_projects(Path("/nonexistent/path")) == []
