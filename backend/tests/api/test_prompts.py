"""Tests for prompts API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import api_app


@pytest.fixture
def tmp_agents_dir(tmp_path: Path):
    agents_dir = tmp_path / "agents"
    agents_dir.mkdir()
    (agents_dir / "planner.md").write_text(
        '---\nname: planner\ndescription: "规划子Agent"\ntools:\n  - Read\n---\n\n# Planner System Prompt\n',
        encoding="utf-8",
    )
    (agents_dir / "writer.md").write_text(
        '---\nname: writer\ndescription: "写作子Agent"\ntools:\n  - Read\n  - Write\n---\n\n# Writer System Prompt\n',
        encoding="utf-8",
    )
    return agents_dir


@pytest.fixture
def tmp_skills_dir(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    skill = skills_dir / "writer-skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: writer-skill\n---\n\nWriter skill content", encoding="utf-8")
    (skill / "chapter-guide.md").write_text("# Chapter Guide", encoding="utf-8")
    return skills_dir


@pytest.fixture
def client(tmp_agents_dir, tmp_skills_dir):
    with patch("backend.api.prompts.get_settings") as mock_settings:
        mock_settings.return_value.agents_dir = tmp_agents_dir
        mock_settings.return_value.skills_dir = tmp_skills_dir
        with patch("backend.api.prompts.reload_agents"):
            yield TestClient(api_app)


class TestListAgents:
    def test_lists_all_agents(self, client):
        resp = client.get("/prompts/agents")
        assert resp.status_code == 200
        agents = resp.json()["agents"]
        names = [a["name"] for a in agents]
        assert "planner" in names
        assert "writer" in names

    def test_includes_description(self, client):
        resp = client.get("/prompts/agents")
        agents = {a["name"]: a for a in resp.json()["agents"]}
        assert "规划" in agents["planner"]["description"]


class TestGetAgent:
    def test_returns_content(self, client):
        resp = client.get("/prompts/agents/planner")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "planner"
        assert "Planner System Prompt" in data["content"]

    def test_missing_agent_404(self, client):
        resp = client.get("/prompts/agents/nonexistent")
        assert resp.status_code == 404


class TestSaveAgent:
    def test_saves_content(self, client, tmp_agents_dir):
        new_content = "---\nname: planner\ndescription: updated\n---\n\nNew prompt"
        resp = client.put("/prompts/agents/planner", json={"content": new_content})
        assert resp.status_code == 200
        saved = (tmp_agents_dir / "planner.md").read_text(encoding="utf-8")
        assert "New prompt" in saved


class TestListSkills:
    def test_lists_skills(self, client):
        resp = client.get("/prompts/skills")
        assert resp.status_code == 200
        skills = resp.json()["skills"]
        assert len(skills) == 1
        assert skills[0]["name"] == "writer-skill"
        assert "SKILL.md" in skills[0]["files"]
        assert "chapter-guide.md" in skills[0]["files"]


class TestGetSkillFile:
    def test_reads_skill_file(self, client):
        resp = client.get("/prompts/skills/writer-skill/SKILL.md")
        assert resp.status_code == 200
        assert "Writer skill content" in resp.json()["content"]

    def test_missing_skill_404(self, client):
        resp = client.get("/prompts/skills/nonexistent/SKILL.md")
        assert resp.status_code == 404

    def test_missing_file_404(self, client):
        resp = client.get("/prompts/skills/writer-skill/nonexistent.md")
        assert resp.status_code == 404


class TestSaveSkillFile:
    def test_saves_file(self, client, tmp_skills_dir):
        resp = client.put(
            "/prompts/skills/writer-skill/chapter-guide.md",
            json={"content": "# Updated Guide"},
        )
        assert resp.status_code == 200
        saved = (tmp_skills_dir / "writer-skill/chapter-guide.md").read_text(encoding="utf-8")
        assert "Updated Guide" in saved
