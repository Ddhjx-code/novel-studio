"""Tests for agent definition loading."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.runtime.agents import _load_all, get_agent, list_agents, reload_agents


def _make_agent(name: str, **kwargs) -> MagicMock:
    agent = MagicMock()
    agent.name = name
    agent.description = kwargs.get("description", f"{name} description")
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
        _make_agent("planner", skills=["planner-skill", "hook-techniques"]),
        _make_agent("writer", skills=["writer-skill", "deai-rules", "hook-techniques"]),
        _make_agent("reviewer", disallowed_tools=["Write", "Edit", "Bash"], skills=["reviewer-skill", "deai-rules"]),
        _make_agent("polisher", skills=["polisher-skill", "deai-rules"]),
    ]


class TestAgentLoader:
    def test_loads_agents_from_directory(self, five_agents):
        with patch("backend.runtime.agents.load_agents_dir", return_value=five_agents):
            agents = reload_agents()
            assert len(agents) == 5
            assert set(agents.keys()) == {"coordinator", "planner", "writer", "reviewer", "polisher"}

    def test_get_agent_returns_correct_one(self, five_agents):
        with patch("backend.runtime.agents.load_agents_dir", return_value=five_agents):
            reload_agents()
            planner = get_agent("planner")
            assert planner is not None
            assert planner.name == "planner"

    def test_get_agent_returns_none_for_missing(self, five_agents):
        with patch("backend.runtime.agents.load_agents_dir", return_value=five_agents):
            reload_agents()
            assert get_agent("nonexistent") is None

    def test_list_agents_returns_all(self, five_agents):
        with patch("backend.runtime.agents.load_agents_dir", return_value=five_agents):
            reload_agents()
            agents = list_agents()
            assert len(agents) == 5

    def test_reviewer_has_disallowed_tools(self, five_agents):
        with patch("backend.runtime.agents.load_agents_dir", return_value=five_agents):
            reload_agents()
            reviewer = get_agent("reviewer")
            assert "Write" in reviewer.disallowed_tools
            assert "Edit" in reviewer.disallowed_tools
            assert "Bash" in reviewer.disallowed_tools

    def test_writer_has_correct_skills(self, five_agents):
        with patch("backend.runtime.agents.load_agents_dir", return_value=five_agents):
            reload_agents()
            writer = get_agent("writer")
            assert "writer-skill" in writer.skills
            assert "deai-rules" in writer.skills
            assert "hook-techniques" in writer.skills

    def test_cache_reused(self, five_agents):
        with patch("backend.runtime.agents.load_agents_dir", return_value=five_agents) as mock_load:
            reload_agents()
            list_agents()
            list_agents()
            mock_load.assert_called_once()

    def test_reload_clears_cache(self, five_agents):
        with patch("backend.runtime.agents.load_agents_dir", return_value=five_agents) as mock_load:
            reload_agents()
            reload_agents()
            assert mock_load.call_count == 2

    def test_missing_directory_returns_empty(self):
        with patch("backend.runtime.agents.get_settings") as mock_settings:
            mock_settings.return_value.agents_dir = Path("/nonexistent/path")
            _load_all.cache_clear()
            agents = reload_agents()
            assert agents == {}
