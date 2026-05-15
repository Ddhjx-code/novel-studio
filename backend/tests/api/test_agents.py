"""Tests for the agents REST API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import api_app
from backend.runtime.agents import _load_all


def _make_agent(name: str, **kwargs) -> MagicMock:
    agent = MagicMock()
    agent.name = name
    agent.description = kwargs.get("description", f"{name} agent")
    agent.system_prompt = kwargs.get("system_prompt", f"You are {name}")
    agent.tools = kwargs.get("tools", ["Read"])
    agent.disallowed_tools = kwargs.get("disallowed_tools", [])
    agent.skills = kwargs.get("skills", [])
    agent.max_turns = kwargs.get("max_turns", 8)
    return agent


@pytest.fixture(autouse=True)
def clear_cache():
    _load_all.cache_clear()
    yield
    _load_all.cache_clear()


@pytest.fixture
def five_agents():
    return [
        _make_agent("coordinator"),
        _make_agent("planner", tools=["Read", "Write", "Edit", "Grep", "Glob"], skills=["planner-skill"]),
        _make_agent("writer", tools=["Read", "Write", "Edit"], skills=["writer-skill"]),
        _make_agent(
            "reviewer",
            tools=["Read", "Grep", "Glob"],
            disallowed_tools=["Write", "Edit", "Bash"],
            skills=["reviewer-skill"],
        ),
        _make_agent("polisher", tools=["Read", "Write", "Edit"], skills=["polisher-skill"]),
    ]


@pytest.fixture
def client(five_agents):
    with patch("backend.runtime.agents.load_agents_dir", return_value=five_agents):
        _load_all.cache_clear()
        _load_all()
        yield TestClient(api_app)


class TestAgentsListEndpoint:
    def test_returns_all_agents(self, client):
        resp = client.get("/agents")
        assert resp.status_code == 200
        data = resp.json()
        names = {a["name"] for a in data["agents"]}
        assert names == {"coordinator", "planner", "writer", "reviewer", "polisher"}

    def test_agent_has_expected_fields(self, client):
        resp = client.get("/agents")
        agents = resp.json()["agents"]
        for agent in agents:
            assert "name" in agent
            assert "description" in agent
            assert "tools" in agent
            assert "skills" in agent
            assert "max_turns" in agent


class TestAgentDetailEndpoint:
    def test_returns_agent_detail(self, client):
        resp = client.get("/agents/planner")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "planner"
        assert "system_prompt" in data
        assert data["system_prompt"] is not None

    def test_reviewer_has_disallowed_tools(self, client):
        resp = client.get("/agents/reviewer")
        data = resp.json()
        assert "Write" in data["disallowed_tools"]

    def test_nonexistent_returns_404(self, client):
        resp = client.get("/agents/nonexistent")
        assert resp.status_code == 404


class TestReloadEndpoint:
    def test_reload_returns_count(self, five_agents):
        with patch("backend.runtime.agents.load_agents_dir", return_value=five_agents):
            client = TestClient(api_app)
            resp = client.post("/agents/reload")
            assert resp.status_code == 200
            data = resp.json()
            assert data["reloaded"] == 5
            assert set(data["names"]) == {"coordinator", "planner", "writer", "reviewer", "polisher"}
