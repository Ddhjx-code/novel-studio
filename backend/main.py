"""FastAPI 入口。

启动：
  .venv/bin/uvicorn backend.main:app --reload --port 8080
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__
from backend.config import get_settings
from backend.projects.repository import recover_interrupted_tasks
from backend.runtime.session import SessionManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    recovered = recover_interrupted_tasks(settings.projects_dir)
    if recovered:
        import logging
        logging.getLogger(__name__).info("Recovered %d interrupted tasks", recovered)

    app.state.session_manager = SessionManager()
    app.state.active_pipelines = {}
    yield
    await app.state.session_manager.close_all()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Novel Studio",
        version=__version__,
        description="AI 小说创作辅助工具",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "version": __version__,
            "llm_configured": "yes" if settings.llm_api_key else "no",
            "llm_model": settings.llm_model or "(unset)",
        }

    from backend.api.sessions import router as sessions_router
    app.include_router(sessions_router)

    from backend.api.agents import router as agents_router
    app.include_router(agents_router)

    from backend.api.ws import router as ws_router
    app.include_router(ws_router)

    from backend.api.projects import router as projects_router
    app.include_router(projects_router)

    from backend.api.chapters import router as chapters_router
    from backend.api.chapters import outline_router
    app.include_router(chapters_router)
    app.include_router(outline_router)

    from backend.api.bible import router as bible_router
    app.include_router(bible_router)

    from backend.api.prompts import router as prompts_router
    app.include_router(prompts_router)

    from backend.api.tasks import router as tasks_router
    app.include_router(tasks_router)

    from backend.api.settings import router as settings_router
    app.include_router(settings_router)

    return app


app = create_app()
