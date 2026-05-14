"""Load novel-studio agent definitions from backend/agents/ directory."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from openharness.coordinator.agent_definitions import AgentDefinition, load_agents_dir

from backend.config import get_settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _load_all() -> dict[str, AgentDefinition]:
    agents_dir = get_settings().agents_dir
    if not agents_dir.is_dir():
        log.warning("Agents directory not found: %s", agents_dir)
        return {}
    agents = load_agents_dir(agents_dir)
    return {agent.name: agent for agent in agents}


def get_agent(name: str) -> AgentDefinition | None:
    return _load_all().get(name)


def list_agents() -> list[AgentDefinition]:
    return list(_load_all().values())


def reload_agents() -> dict[str, AgentDefinition]:
    _load_all.cache_clear()
    return _load_all()
