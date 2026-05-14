"""Tests for bible API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.projects.workspace import ensure_project


@pytest.fixture
def tmp_projects_dir(tmp_path: Path):
    projects = tmp_path / "projects"
    projects.mkdir()
    ws = ensure_project(projects, "test-novel")
    ws.write_file("bible/characters/主角.md", "# 主角\n性格：果断")
    ws.write_file("bible/worldbuilding/城市.md", "# 虚构城市")
    ws.write_file("bible/plot/outline.md", "# 大纲")
    ws.write_file("bible/global_summary.md", "全局摘要内容")
    return projects


@pytest.fixture
def client(tmp_projects_dir):
    with patch("backend.api.bible.get_settings") as mock_settings:
        mock_settings.return_value.projects_dir = tmp_projects_dir
        yield TestClient(app)


class TestBibleTree:
    def test_returns_all_files(self, client):
        resp = client.get("/projects/test-novel/bible/tree")
        assert resp.status_code == 200
        files = resp.json()["files"]
        assert "bible/characters/主角.md" in files
        assert "bible/worldbuilding/城市.md" in files
        assert "bible/plot/outline.md" in files
        assert "bible/global_summary.md" in files

    def test_missing_project_404(self, client):
        resp = client.get("/projects/nonexistent/bible/tree")
        assert resp.status_code == 404


class TestReadBibleFile:
    def test_reads_existing_file(self, client):
        resp = client.get("/projects/test-novel/bible/characters/主角.md")
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == "bible/characters/主角.md"
        assert "果断" in data["content"]

    def test_missing_file_404(self, client):
        resp = client.get("/projects/test-novel/bible/nonexistent.md")
        assert resp.status_code == 404


class TestSaveBibleFile:
    def test_saves_new_file(self, client, tmp_projects_dir):
        resp = client.put(
            "/projects/test-novel/bible/characters/配角.md",
            json={"content": "# 配角\n性格：温柔"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"

        from backend.projects.workspace import ProjectWorkspace

        ws = ProjectWorkspace(tmp_projects_dir, "test-novel")
        assert "温柔" in ws.read_file("bible/characters/配角.md")

    def test_overwrites_existing(self, client, tmp_projects_dir):
        client.put(
            "/projects/test-novel/bible/global_summary.md",
            json={"content": "新摘要"},
        )
        from backend.projects.workspace import ProjectWorkspace

        ws = ProjectWorkspace(tmp_projects_dir, "test-novel")
        assert ws.read_file("bible/global_summary.md") == "新摘要"


class TestDeleteBibleFile:
    def test_deletes_existing(self, client, tmp_projects_dir):
        resp = client.delete("/projects/test-novel/bible/characters/主角.md")
        assert resp.status_code == 200
        assert not (tmp_projects_dir / "test-novel/bible/characters/主角.md").exists()

    def test_missing_file_404(self, client):
        resp = client.delete("/projects/test-novel/bible/nonexistent.md")
        assert resp.status_code == 404
