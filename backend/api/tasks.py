"""REST endpoints for task management and journal."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.config import get_settings
from backend.orchestrator.chapter_pipeline import ChapterPipeline, PipelineStep
from backend.orchestrator.finalize import LLMConfig
from backend.orchestrator.outline_pipeline import OutlinePipeline
from backend.orchestrator.review_pipeline import ReviewPipeline
from backend.projects.repository import ProjectRepository, TaskCard
from backend.projects.workspace import ProjectWorkspace
from backend.vectorstore.embedding import EmbeddingConfig

router = APIRouter(tags=["tasks"])


def _get_repo(project_name: str) -> ProjectRepository:
    settings = get_settings()
    project_dir = settings.projects_dir / project_name
    if not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRepository(settings.projects_dir, project_name)


@router.get("/projects/{project_name}/tasks")
async def list_tasks(
    project_name: str,
    status: str | None = None,
    kind: str | None = None,
    limit: int = 50,
):
    repo = _get_repo(project_name)
    tasks = repo.list_tasks(status=status, kind=kind, limit=limit)  # type: ignore[arg-type]
    return {"tasks": [t.model_dump() for t in tasks]}


@router.get("/projects/{project_name}/tasks/{task_id}")
async def get_task(project_name: str, task_id: str):
    repo = _get_repo(project_name)
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.model_dump()


@router.post("/projects/{project_name}/tasks/{task_id}/retry", status_code=202)
async def retry_task(project_name: str, task_id: str, request: Request):
    repo = _get_repo(project_name)
    original = repo.get_task(task_id)
    if not original:
        raise HTTPException(status_code=404, detail="Task not found")
    if original.status == "running":
        raise HTTPException(status_code=409, detail="Task is still running")
    if original.status == "pending":
        raise HTTPException(status_code=409, detail="Task is still pending")

    settings = get_settings()
    ws = ProjectWorkspace(settings.projects_dir, project_name)
    mgr = request.app.state.session_manager
    pipelines: dict[str, Any] = request.app.state.active_pipelines

    if original.kind == "chapter_generate":
        steps = (
            [PipelineStep(s) for s in original.steps_requested]
            if original.steps_requested
            else None
        )
        pipeline = ChapterPipeline(
            session_manager=mgr,
            workspace=ws,
            chapter_num=original.chapter_num or 1,
            steps=steps,
            llm_config=_get_llm_config(),
            embedding_config=_get_embedding_config(),
        )
        new_task = repo.create_task(
            "chapter_generate",
            chapter_num=original.chapter_num,
            pipeline_id=pipeline.pipeline_id,
            steps=[s.value for s in (steps or [])],
            metadata={"retried_from": task_id},
        )
        pipelines[pipeline.pipeline_id] = pipeline
        asyncio.create_task(
            _run_pipeline_with_tracking(pipeline, pipelines, repo, new_task.id)
        )
        return {"pipeline_id": pipeline.pipeline_id, "task_id": new_task.id, "status": "started"}

    elif original.kind == "outline_generate":
        pipeline = OutlinePipeline(
            session_manager=mgr,
            workspace=ws,
            synopsis=original.metadata.get("synopsis", ""),
            user_guidance=original.metadata.get("user_guidance", ""),
        )
        new_task = repo.create_task(
            "outline_generate",
            pipeline_id=pipeline.pipeline_id,
            metadata={"retried_from": task_id, **original.metadata},
        )
        pipelines[pipeline.pipeline_id] = pipeline
        asyncio.create_task(
            _run_review_with_tracking(pipeline, pipelines, repo, new_task.id)
        )
        return {"pipeline_id": pipeline.pipeline_id, "task_id": new_task.id, "status": "started"}

    elif original.kind in ("chapter_review", "chapter_polish"):
        mode = "review" if original.kind == "chapter_review" else "polish"
        pipeline = ReviewPipeline(
            session_manager=mgr,
            workspace=ws,
            chapter_num=original.chapter_num or 1,
            mode=mode,
            embedding_config=_get_embedding_config(),
        )
        new_task = repo.create_task(
            original.kind,
            chapter_num=original.chapter_num,
            pipeline_id=pipeline.pipeline_id,
            metadata={"retried_from": task_id},
        )
        pipelines[pipeline.pipeline_id] = pipeline
        asyncio.create_task(
            _run_review_with_tracking(pipeline, pipelines, repo, new_task.id)
        )
        return {"pipeline_id": pipeline.pipeline_id, "task_id": new_task.id, "status": "started"}

    raise HTTPException(status_code=400, detail=f"Unknown task kind: {original.kind}")


@router.get("/projects/{project_name}/journal")
async def get_journal(project_name: str, limit: int = 50):
    repo = _get_repo(project_name)
    entries = repo.load_journal(limit=limit)
    return {"entries": [e.model_dump() for e in entries]}


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


async def _run_pipeline_with_tracking(
    pipeline: ChapterPipeline,
    pipelines: dict[str, Any],
    repo: ProjectRepository,
    task_id: str,
) -> None:
    try:
        repo.update_task_status(task_id, "running")

        async def on_event(event: dict[str, Any]) -> None:
            event_type = event.get("type", "")
            if event_type == "pipeline.step_complete":
                step = event["data"]["step"]
                task = repo.get_task(task_id)
                completed = list(task.steps_completed) + [step] if task else [step]
                repo.update_task_status(task_id, "running", steps_completed=completed)
            repo.append_journal(
                kind=event_type,
                summary=f"Pipeline {pipeline.pipeline_id}: {event_type}",
                task_id=task_id,
                metadata=event.get("data", {}),
            )

        result = await pipeline.run(event_callback=on_event)

        if result.status == "completed":
            repo.update_task_status(
                task_id, "completed", steps_completed=result.steps_completed
            )
        elif result.status == "failed":
            repo.update_task_status(task_id, "failed", error=result.error)
        elif result.status == "cancelled":
            repo.update_task_status(task_id, "cancelled")
    except Exception as e:
        repo.update_task_status(task_id, "failed", error=str(e))
    finally:
        pipelines.pop(pipeline.pipeline_id, None)


async def _run_review_with_tracking(
    pipeline: ReviewPipeline | OutlinePipeline,
    pipelines: dict[str, Any],
    repo: ProjectRepository,
    task_id: str,
) -> None:
    try:
        repo.update_task_status(task_id, "running")

        async def on_event(event: dict[str, Any]) -> None:
            repo.append_journal(
                kind=event.get("type", "unknown"),
                summary=f"Pipeline {pipeline.pipeline_id}: {event.get('type', '')}",
                task_id=task_id,
                metadata=event.get("data", {}),
            )

        result = await pipeline.run(event_callback=on_event)

        if result.status == "completed":
            repo.update_task_status(task_id, "completed")
        elif result.status == "failed":
            repo.update_task_status(task_id, "failed", error=result.error)
        elif result.status == "cancelled":
            repo.update_task_status(task_id, "cancelled")
    except Exception as e:
        repo.update_task_status(task_id, "failed", error=str(e))
    finally:
        pipelines.pop(pipeline.pipeline_id, None)
