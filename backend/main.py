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
from backend.runtime.session import SessionManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.session_manager = SessionManager()
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

    return app


app = create_app()
