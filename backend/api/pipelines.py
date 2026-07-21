"""Pipeline management endpoints: list and cancel running pipelines."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/projects/{project_name}/pipelines", tags=["pipelines"])


class PipelineStatus(BaseModel):
    pipeline_id: str
    status: str
    chapter_num: int | None = None


@router.get("")
async def list_pipelines(project_name: str, request: Request) -> list[PipelineStatus]:
    """Return all currently active pipelines for a project."""
    pipelines: dict[str, Any] = request.app.state.active_pipelines
    result: list[PipelineStatus] = []
    for pid, p in pipelines.items():
        ch = getattr(p, "_chapter_num", None)
        status = "running"
        if getattr(p, "_cancelled", False):
            status = "cancelling"
        result.append(PipelineStatus(pipeline_id=pid, status=status, chapter_num=ch))
    return result


@router.post("/{pipeline_id}/cancel")
async def cancel_pipeline(project_name: str, pipeline_id: str, request: Request):
    """Cancel a running pipeline by id.

    Returns 404 if the pipeline is not found or already finished.
    """
    pipelines: dict[str, Any] = request.app.state.active_pipelines
    pipeline = pipelines.get(pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found or already finished")

    pipeline.cancel()
    return {"pipeline_id": pipeline_id, "status": "cancelled"}
