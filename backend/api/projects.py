"""REST endpoints for project management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.config import get_settings
from backend.projects.workspace import ensure_project, list_projects

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectBody(BaseModel):
    name: str


@router.post("", status_code=201)
async def create_project(body: CreateProjectBody):
    settings = get_settings()
    project_dir = settings.projects_dir / body.name
    if project_dir.exists():
        raise HTTPException(status_code=409, detail="Project already exists")
    ws = ensure_project(settings.projects_dir, body.name)
    return {"name": ws.name, "path": str(ws.root)}


@router.get("")
async def list_all_projects():
    settings = get_settings()
    names = list_projects(settings.projects_dir)
    return {"projects": names}


@router.get("/{name}")
async def get_project(name: str):
    settings = get_settings()
    project_dir = settings.projects_dir / name
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")

    from backend.projects.workspace import ProjectWorkspace

    ws = ProjectWorkspace(settings.projects_dir, name)
    chapters = ws.list_chapters()
    global_summary = ws.read_file("bible/global_summary.md")
    character_state = ws.read_file("bible/character_state.md")

    return {
        "name": name,
        "chapters": chapters,
        "planned_chapters": ws.list_planned_chapters(),
        "has_outline": bool(ws.read_file("bible/plot/outline.md")),
        "global_summary_length": len(global_summary),
        "character_state_length": len(character_state),
    }
