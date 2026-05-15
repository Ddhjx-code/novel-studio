"""Tests for projects API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import api_app


@pytest.fixture
def tmp_projects_dir(tmp_path: Path):
    projects = tmp_path / "projects"
    projects.mkdir()
    return projects


@pytest.fixture
def client(tmp_projects_dir):
    with patch("backend.api.projects.get_settings") as mock_settings:
        mock_settings.return_value.projects_dir = tmp_projects_dir
        yield TestClient(api_app)


class TestCreateProject:
    def test_creates_project(self, client, tmp_projects_dir):
        resp = client.post("/projects", json={"name": "my-novel"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "my-novel"
        assert (tmp_projects_dir / "my-novel" / "chapters").is_dir()

    def test_duplicate_returns_409(self, client, tmp_projects_dir):
        (tmp_projects_dir / "existing").mkdir()
        resp = client.post("/projects", json={"name": "existing"})
        assert resp.status_code == 409


class TestListProjects:
    def test_lists_projects(self, client, tmp_projects_dir):
        (tmp_projects_dir / "novel-a").mkdir()
        (tmp_projects_dir / "novel-b").mkdir()
        resp = client.get("/projects")
        assert resp.status_code == 200
        assert set(resp.json()["projects"]) == {"novel-a", "novel-b"}

    def test_empty_list(self, client):
        resp = client.get("/projects")
        assert resp.json()["projects"] == []


class TestGetProject:
    def test_returns_project_detail(self, client, tmp_projects_dir):
        from backend.projects.workspace import ensure_project

        ws = ensure_project(tmp_projects_dir, "test-novel")
        ws.write_file("chapters/ch01.md", "content")
        ws.write_file("bible/global_summary.md", "summary")

        with patch("backend.api.projects.get_settings") as mock_settings:
            mock_settings.return_value.projects_dir = tmp_projects_dir
            resp = client.get("/projects/test-novel")

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-novel"
        assert 1 in data["chapters"]
        assert data["global_summary_length"] > 0

    def test_nonexistent_returns_404(self, client):
        resp = client.get("/projects/nonexistent")
        assert resp.status_code == 404
