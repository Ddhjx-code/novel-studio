"""Tests for chapters API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import api_app
from backend.projects.workspace import ensure_project


@pytest.fixture
def tmp_projects_dir(tmp_path: Path):
    projects = tmp_path / "projects"
    projects.mkdir()
    ws = ensure_project(projects, "test-novel")
    ws.write_file("chapters/ch01.md", "第一章正文")
    return projects


@pytest.fixture
def client(tmp_projects_dir):
    with patch("backend.api.chapters.get_settings") as mock_settings:
        mock_settings.return_value.projects_dir = tmp_projects_dir
        mock_settings.return_value.llm_api_format = "openai_compat"
        mock_settings.return_value.llm_base_url = "http://test"
        mock_settings.return_value.llm_model = "test-model"
        mock_settings.return_value.llm_api_key = "key"
        mock_settings.return_value.embedding_api_format = ""
        mock_settings.return_value.embedding_base_url = ""
        mock_settings.return_value.embedding_model = ""
        mock_settings.return_value.embedding_api_key = ""
        yield TestClient(api_app)


class TestReadChapter:
    def test_reads_existing_chapter(self, client):
        resp = client.get("/projects/test-novel/chapters/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chapter_num"] == 1
        assert data["content"] == "第一章正文"

    def test_missing_chapter_404(self, client):
        resp = client.get("/projects/test-novel/chapters/99")
        assert resp.status_code == 404

    def test_missing_project_404(self, client):
        resp = client.get("/projects/nonexistent/chapters/1")
        assert resp.status_code == 404


class TestSaveChapter:
    def test_saves_content(self, client, tmp_projects_dir):
        resp = client.put(
            "/projects/test-novel/chapters/2",
            json={"content": "新写的第二章"},
        )
        assert resp.status_code == 200

        from backend.projects.workspace import ProjectWorkspace

        ws = ProjectWorkspace(tmp_projects_dir, "test-novel")
        assert ws.read_file("chapters/ch02.md") == "新写的第二章"


class TestGenerateChapter:
    def test_returns_pipeline_id(self, client):
        api_app.state.session_manager = MagicMock()
        api_app.state.session_manager.create_for_agent = AsyncMock()
        api_app.state.active_pipelines = {}

        resp = client.post(
            "/projects/test-novel/chapters/1/generate",
            json={},
        )

        assert resp.status_code == 202
        data = resp.json()
        assert "pipeline_id" in data
        assert data["status"] == "started"

    def test_with_specific_steps(self, client):
        api_app.state.session_manager = MagicMock()
        api_app.state.session_manager.create_for_agent = AsyncMock()
        api_app.state.active_pipelines = {}

        resp = client.post(
            "/projects/test-novel/chapters/1/generate",
            json={"steps": ["C", "D"]},
        )

        assert resp.status_code == 202


class TestReviewPolish:
    def test_review_returns_pipeline_id(self, client):
        api_app.state.session_manager = MagicMock()
        api_app.state.session_manager.create_for_agent = AsyncMock()
        api_app.state.active_pipelines = {}

        resp = client.post("/projects/test-novel/chapters/1/review")

        assert resp.status_code == 202
        assert "pipeline_id" in resp.json()

    def test_polish_returns_pipeline_id(self, client):
        api_app.state.session_manager = MagicMock()
        api_app.state.session_manager.create_for_agent = AsyncMock()
        api_app.state.active_pipelines = {}

        resp = client.post("/projects/test-novel/chapters/1/polish")

        assert resp.status_code == 202
