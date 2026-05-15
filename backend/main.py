"""FastAPI entry point.

Production (single port):
  npm run build --prefix frontend
  .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8080

Development (two terminals):
  .venv/bin/uvicorn backend.main:app --reload --port 8080
  cd frontend && npm run dev
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import __version__
from backend.config import REPO_ROOT, get_settings
from backend.projects.repository import recover_interrupted_tasks
from backend.runtime.session import SessionManager

log = logging.getLogger(__name__)

STATIC_DIR = REPO_ROOT / "frontend" / "dist"


@asynccontextmanager
async def _api_lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    recovered = recover_interrupted_tasks(settings.projects_dir)
    if recovered:
        log.info("Recovered %d interrupted tasks", recovered)

    app.state.session_manager = SessionManager()
    app.state.active_pipelines = {}
    yield
    await app.state.session_manager.close_all()


def _build_api_app() -> FastAPI:
    """Create the API sub-application that handles all REST + WS routes."""
    settings = get_settings()
    api_app = FastAPI(
        title="Novel Studio API",
        version=__version__,
        lifespan=_api_lifespan,
    )

    @api_app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "version": __version__,
            "llm_configured": "yes" if settings.llm_api_key else "no",
            "llm_model": settings.llm_model or "(unset)",
        }

    from backend.api.sessions import router as sessions_router
    api_app.include_router(sessions_router)

    from backend.api.agents import router as agents_router
    api_app.include_router(agents_router)

    from backend.api.ws import router as ws_router
    api_app.include_router(ws_router)

    from backend.api.projects import router as projects_router
    api_app.include_router(projects_router)

    from backend.api.chapters import outline_router
    from backend.api.chapters import router as chapters_router
    api_app.include_router(chapters_router)
    api_app.include_router(outline_router)

    from backend.api.bible import router as bible_router
    api_app.include_router(bible_router)

    from backend.api.prompts import router as prompts_router
    api_app.include_router(prompts_router)

    from backend.api.tasks import router as tasks_router
    api_app.include_router(tasks_router)

    from backend.api.settings import router as settings_router
    api_app.include_router(settings_router)

    return api_app


def create_app() -> FastAPI:
    settings = get_settings()
    api_app = _build_api_app()

    root_app = FastAPI(title="Novel Studio", version=__version__)

    root_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    root_app.mount("/api", api_app)

    if STATIC_DIR.is_dir():
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.is_dir():
            root_app.mount(
                "/assets", StaticFiles(directory=assets_dir), name="assets"
            )

        @root_app.get("/{full_path:path}")
        async def serve_spa(full_path: str) -> FileResponse:
            file_path = (STATIC_DIR / full_path).resolve()
            static_root = STATIC_DIR.resolve()
            if (
                full_path
                and file_path.is_file()
                and str(file_path).startswith(str(static_root))
            ):
                return FileResponse(file_path)
            return FileResponse(STATIC_DIR / "index.html")

    root_app.state._api = api_app
    return root_app


app = create_app()
api_app = app.state._api
