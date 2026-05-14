"""REST endpoints for bible file management."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import get_settings
from backend.projects.workspace import ProjectWorkspace

router = APIRouter(prefix="/projects/{project_name}/bible", tags=["bible"])


def _get_workspace(project_name: str) -> ProjectWorkspace:
    settings = get_settings()
    project_dir = settings.projects_dir / project_name
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectWorkspace(settings.projects_dir, project_name)


def _validate_bible_path(path: str) -> str:
    """Ensure the path stays within bible/ prefix."""
    normalized = path.strip("/")
    if not normalized.startswith("bible/") and normalized != "bible":
        raise HTTPException(status_code=400, detail="Path must be within bible/ directory")
    return normalized


@router.get("/tree")
async def get_bible_tree(project_name: str):
    ws = _get_workspace(project_name)
    files = ws.list_files("bible")
    return {"files": files}


@router.get("/{file_path:path}")
async def read_bible_file(project_name: str, file_path: str):
    ws = _get_workspace(project_name)
    full_path = _validate_bible_path(f"bible/{file_path}")
    content = ws.read_file(full_path)
    if not content and not (ws.root / full_path).is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": full_path, "content": content}


class SaveBibleBody(BaseModel):
    content: str


@router.put("/{file_path:path}")
async def save_bible_file(project_name: str, file_path: str, body: SaveBibleBody):
    ws = _get_workspace(project_name)
    full_path = _validate_bible_path(f"bible/{file_path}")
    ws.write_file(full_path, body.content)
    return {"status": "saved", "path": full_path}


@router.delete("/{file_path:path}")
async def delete_bible_file(project_name: str, file_path: str):
    ws = _get_workspace(project_name)
    full_path = _validate_bible_path(f"bible/{file_path}")
    deleted = ws.delete_file(full_path)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return {"status": "deleted", "path": full_path}
