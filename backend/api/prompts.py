"""REST endpoints for agent and skill prompt editing."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import get_settings
from backend.runtime.agents import reload_agents

router = APIRouter(prefix="/prompts", tags=["prompts"])

_UNSAFE_PATH = re.compile(r"(^|[\\/])\.\.($|[\\/])")


def _validate_path(base: Path, relative: str) -> Path:
    if _UNSAFE_PATH.search(relative):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    target = base / relative
    if not str(target.resolve()).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Path escapes base directory")
    return target


# --- Agent endpoints ---


@router.get("/agents")
async def list_prompt_agents():
    settings = get_settings()
    agents_dir = settings.agents_dir
    if not agents_dir.is_dir():
        return {"agents": []}
    agents = []
    for p in sorted(agents_dir.glob("*.md")):
        content = p.read_text(encoding="utf-8")
        name = p.stem
        description = _extract_frontmatter_field(content, "description") or ""
        agents.append({"name": name, "description": description, "path": str(p.name)})
    return {"agents": agents}


@router.get("/agents/{name}")
async def get_prompt_agent(name: str):
    settings = get_settings()
    path = _validate_path(settings.agents_dir, f"{name}.md")
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    content = path.read_text(encoding="utf-8")
    return {"name": name, "content": content}


class SaveAgentBody(BaseModel):
    content: str


@router.put("/agents/{name}")
async def save_prompt_agent(name: str, body: SaveAgentBody):
    settings = get_settings()
    path = _validate_path(settings.agents_dir, f"{name}.md")
    path.write_text(body.content, encoding="utf-8")
    reload_agents()
    return {"status": "saved", "name": name}


# --- Skill endpoints ---


@router.get("/skills")
async def list_prompt_skills():
    settings = get_settings()
    skills_dir = settings.skills_dir
    if not skills_dir.is_dir():
        return {"skills": []}
    skills = []
    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        files = sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file())
        skills.append({"name": d.name, "files": files})
    return {"skills": skills}


@router.get("/skills/{skill_name}/{file_path:path}")
async def get_prompt_skill_file(skill_name: str, file_path: str):
    settings = get_settings()
    skill_dir = _validate_path(settings.skills_dir, skill_name)
    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    target = _validate_path(skill_dir, file_path)
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    content = target.read_text(encoding="utf-8")
    return {"path": f"{skill_name}/{file_path}", "content": content}


class SaveSkillBody(BaseModel):
    content: str


@router.put("/skills/{skill_name}/{file_path:path}")
async def save_prompt_skill_file(skill_name: str, file_path: str, body: SaveSkillBody):
    settings = get_settings()
    skill_dir = _validate_path(settings.skills_dir, skill_name)
    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    target = _validate_path(skill_dir, file_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content, encoding="utf-8")
    return {"status": "saved", "path": f"{skill_name}/{file_path}"}


def _extract_frontmatter_field(content: str, field: str) -> str | None:
    """Extract a field value from YAML frontmatter."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    frontmatter = match.group(1)
    for line in frontmatter.split("\n"):
        if line.startswith(f"{field}:"):
            value = line[len(field) + 1:].strip().strip('"').strip("'")
            return value
    return None
