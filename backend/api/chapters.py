"""REST endpoints for chapter generation and management."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.api.tasks import (
    _run_pipeline_with_tracking,
    _run_review_with_tracking,
)
from backend.config import get_settings
from backend.orchestrator.chapter_pipeline import ChapterPipeline, PipelineStep
from backend.orchestrator.finalize import LLMConfig
from backend.orchestrator.outline_pipeline import OutlinePipeline
from backend.orchestrator.review_pipeline import ReviewPipeline
from backend.projects.repository import ProjectRepository
from backend.projects.workspace import ProjectWorkspace
from backend.vectorstore.embedding import EmbeddingConfig

router = APIRouter(prefix="/projects/{project_name}/chapters", tags=["chapters"])


def _get_workspace(project_name: str) -> ProjectWorkspace:
    settings = get_settings()
    project_dir = settings.projects_dir / project_name
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectWorkspace(settings.projects_dir, project_name)


def _get_repository(project_name: str) -> ProjectRepository:
    settings = get_settings()
    return ProjectRepository(settings.projects_dir, project_name)


def _get_llm_config() -> LLMConfig:
    settings = get_settings()
    return LLMConfig(
        api_format=settings.llm_api_format,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
    )


def _get_embedding_config() -> EmbeddingConfig:
    settings = get_settings()
    return EmbeddingConfig(
        api_format=settings.embedding_api_format or settings.llm_api_format,
        base_url=settings.embedding_base_url or settings.llm_base_url,
        model=settings.embedding_model or "text-embedding-3-small",
        api_key=settings.embedding_api_key or settings.llm_api_key,
    )


class GenerateBody(BaseModel):
    steps: list[str] | None = None


class OutlineBody(BaseModel):
    synopsis: str
    user_guidance: str = ""


class ChapterContentBody(BaseModel):
    content: str


@router.post("/{n}/generate", status_code=202)
async def generate_chapter(project_name: str, n: int, body: GenerateBody, request: Request):
    ws = _get_workspace(project_name)
    repo = _get_repository(project_name)
    mgr = request.app.state.session_manager

    steps = None
    if body.steps:
        steps = [PipelineStep(s) for s in body.steps]

    pipeline = ChapterPipeline(
        session_manager=mgr,
        workspace=ws,
        chapter_num=n,
        steps=steps,
        llm_config=_get_llm_config(),
        embedding_config=_get_embedding_config(),
    )

    step_values = [s.value for s in (steps or pipeline._steps)]
    task = repo.create_task(
        "chapter_generate",
        chapter_num=n,
        pipeline_id=pipeline.pipeline_id,
        steps=step_values,
    )

    pipelines: dict[str, Any] = request.app.state.active_pipelines
    pipelines[pipeline.pipeline_id] = pipeline
    asyncio.create_task(
        _run_pipeline_with_tracking(pipeline, pipelines, repo, task.id)
    )

    return {"pipeline_id": pipeline.pipeline_id, "task_id": task.id, "status": "started"}


@router.get("/{n}")
async def read_chapter(project_name: str, n: int):
    ws = _get_workspace(project_name)
    content = ws.read_file(f"chapters/ch{n:02d}.md")
    if not content:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"chapter_num": n, "content": content}


@router.get("/{n}/plan")
async def read_plan(project_name: str, n: int):
    ws = _get_workspace(project_name)
    content = ws.read_file(f"plans/ch{n:02d}-plan.md")
    return {"chapter_num": n, "content": content, "exists": bool(content)}


@router.get("/{n}/review")
async def read_review(project_name: str, n: int):
    ws = _get_workspace(project_name)
    content = ws.read_file(f"reviews/ch{n:02d}-review.md")
    return {"chapter_num": n, "content": content, "exists": bool(content)}


@router.put("/{n}")
async def save_chapter(project_name: str, n: int, body: ChapterContentBody):
    ws = _get_workspace(project_name)
    ws.write_file(f"chapters/ch{n:02d}.md", body.content)
    return {"status": "saved", "chapter_num": n}


@router.post("/{n}/review", status_code=202)
async def review_chapter(project_name: str, n: int, request: Request):
    ws = _get_workspace(project_name)
    repo = _get_repository(project_name)
    mgr = request.app.state.session_manager

    pipeline = ReviewPipeline(
        session_manager=mgr, workspace=ws, chapter_num=n, mode="review",
        embedding_config=_get_embedding_config(),
    )
    task = repo.create_task(
        "chapter_review",
        chapter_num=n,
        pipeline_id=pipeline.pipeline_id,
    )

    pipelines: dict[str, Any] = request.app.state.active_pipelines
    pipelines[pipeline.pipeline_id] = pipeline
    asyncio.create_task(
        _run_review_with_tracking(pipeline, pipelines, repo, task.id)
    )

    return {"pipeline_id": pipeline.pipeline_id, "task_id": task.id, "status": "started"}


@router.post("/{n}/polish", status_code=202)
async def polish_chapter(project_name: str, n: int, request: Request):
    ws = _get_workspace(project_name)
    repo = _get_repository(project_name)
    mgr = request.app.state.session_manager

    pipeline = ReviewPipeline(
        session_manager=mgr, workspace=ws, chapter_num=n, mode="polish",
        embedding_config=_get_embedding_config(),
    )
    task = repo.create_task(
        "chapter_polish",
        chapter_num=n,
        pipeline_id=pipeline.pipeline_id,
    )

    pipelines: dict[str, Any] = request.app.state.active_pipelines
    pipelines[pipeline.pipeline_id] = pipeline
    asyncio.create_task(
        _run_review_with_tracking(pipeline, pipelines, repo, task.id)
    )

    return {"pipeline_id": pipeline.pipeline_id, "task_id": task.id, "status": "started"}


outline_router = APIRouter(prefix="/projects/{project_name}/outline", tags=["outline"])


@outline_router.post("/generate", status_code=202)
async def generate_outline(project_name: str, body: OutlineBody, request: Request):
    ws = _get_workspace(project_name)
    repo = _get_repository(project_name)
    mgr = request.app.state.session_manager

    pipeline = OutlinePipeline(
        session_manager=mgr,
        workspace=ws,
        synopsis=body.synopsis,
        user_guidance=body.user_guidance,
    )
    task = repo.create_task(
        "outline_generate",
        pipeline_id=pipeline.pipeline_id,
        metadata={"synopsis": body.synopsis, "user_guidance": body.user_guidance},
    )

    pipelines: dict[str, Any] = request.app.state.active_pipelines
    pipelines[pipeline.pipeline_id] = pipeline
    asyncio.create_task(
        _run_review_with_tracking(pipeline, pipelines, repo, task.id)
    )

    return {"pipeline_id": pipeline.pipeline_id, "task_id": task.id, "status": "started"}
