"""REST endpoints for chapter generation and management."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.config import get_settings
from backend.orchestrator.chapter_pipeline import ChapterPipeline, PipelineStep
from backend.orchestrator.finalize import LLMConfig
from backend.orchestrator.outline_pipeline import OutlinePipeline
from backend.orchestrator.review_pipeline import ReviewPipeline
from backend.projects.workspace import ProjectWorkspace
from backend.vectorstore.embedding import EmbeddingConfig

router = APIRouter(prefix="/projects/{project_name}/chapters", tags=["chapters"])


def _get_workspace(project_name: str) -> ProjectWorkspace:
    settings = get_settings()
    project_dir = settings.projects_dir / project_name
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectWorkspace(settings.projects_dir, project_name)


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

    pipelines: dict[str, Any] = request.app.state.active_pipelines
    pipelines[pipeline.pipeline_id] = pipeline
    asyncio.create_task(_run_pipeline(pipeline, pipelines))

    return {"pipeline_id": pipeline.pipeline_id, "status": "started"}


@router.get("/{n}")
async def read_chapter(project_name: str, n: int):
    ws = _get_workspace(project_name)
    content = ws.read_file(f"chapters/ch{n:02d}.md")
    if not content:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"chapter_num": n, "content": content}


@router.put("/{n}")
async def save_chapter(project_name: str, n: int, body: ChapterContentBody):
    ws = _get_workspace(project_name)
    ws.write_file(f"chapters/ch{n:02d}.md", body.content)
    return {"status": "saved", "chapter_num": n}


@router.post("/{n}/review", status_code=202)
async def review_chapter(project_name: str, n: int, request: Request):
    ws = _get_workspace(project_name)
    mgr = request.app.state.session_manager

    pipeline = ReviewPipeline(
        session_manager=mgr, workspace=ws, chapter_num=n, mode="review"
    )
    pipelines: dict[str, Any] = request.app.state.active_pipelines
    pipelines[pipeline.pipeline_id] = pipeline
    asyncio.create_task(_run_review(pipeline, pipelines))

    return {"pipeline_id": pipeline.pipeline_id, "status": "started"}


@router.post("/{n}/polish", status_code=202)
async def polish_chapter(project_name: str, n: int, request: Request):
    ws = _get_workspace(project_name)
    mgr = request.app.state.session_manager

    pipeline = ReviewPipeline(
        session_manager=mgr, workspace=ws, chapter_num=n, mode="polish"
    )
    pipelines: dict[str, Any] = request.app.state.active_pipelines
    pipelines[pipeline.pipeline_id] = pipeline
    asyncio.create_task(_run_review(pipeline, pipelines))

    return {"pipeline_id": pipeline.pipeline_id, "status": "started"}


outline_router = APIRouter(prefix="/projects/{project_name}/outline", tags=["outline"])


@outline_router.post("/generate", status_code=202)
async def generate_outline(project_name: str, body: OutlineBody, request: Request):
    ws = _get_workspace(project_name)
    mgr = request.app.state.session_manager

    pipeline = OutlinePipeline(
        session_manager=mgr,
        workspace=ws,
        synopsis=body.synopsis,
        user_guidance=body.user_guidance,
    )
    pipelines: dict[str, Any] = request.app.state.active_pipelines
    pipelines[pipeline.pipeline_id] = pipeline
    asyncio.create_task(_run_outline(pipeline, pipelines))

    return {"pipeline_id": pipeline.pipeline_id, "status": "started"}


async def _run_pipeline(pipeline: ChapterPipeline, pipelines: dict[str, Any]) -> None:
    try:
        await pipeline.run()
    finally:
        pipelines.pop(pipeline.pipeline_id, None)


async def _run_review(pipeline: ReviewPipeline, pipelines: dict[str, Any]) -> None:
    try:
        await pipeline.run()
    finally:
        pipelines.pop(pipeline.pipeline_id, None)


async def _run_outline(pipeline: OutlinePipeline, pipelines: dict[str, Any]) -> None:
    try:
        await pipeline.run()
    finally:
        pipelines.pop(pipeline.pipeline_id, None)
