"""REST endpoints for agent and skill management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.runtime.agents import get_agent, list_agents, reload_agents

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_all_agents():
    agents = list_agents()
    return {
        "agents": [
            {
                "name": a.name,
                "description": a.description,
                "tools": a.tools,
                "disallowed_tools": a.disallowed_tools,
                "skills": a.skills,
                "max_turns": a.max_turns,
            }
            for a in agents
        ]
    }


@router.get("/{agent_name}")
async def get_agent_detail(agent_name: str):
    agent = get_agent(agent_name)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return {
        "name": agent.name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "tools": agent.tools,
        "disallowed_tools": agent.disallowed_tools,
        "skills": agent.skills,
        "max_turns": agent.max_turns,
    }


@router.post("/reload")
async def reload_all_agents():
    agents = reload_agents()
    return {"reloaded": len(agents), "names": list(agents.keys())}
