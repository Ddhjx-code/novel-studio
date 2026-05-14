"""Wraps OpenHarness build_runtime into a managed session with event broadcasting."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from openharness.permissions.modes import PermissionMode
from openharness.ui.runtime import RuntimeBundle, build_runtime, close_runtime

from backend.runtime.stream import serialize_event

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SessionConfig:
    cwd: str
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    api_format: str = "openai_compat"
    system_prompt: str = ""
    max_turns: int = 8
    extra_skill_dirs: tuple[str, ...] = ()
    agent_name: str = ""


class NovelSession:
    def __init__(self, session_id: str, config: SessionConfig) -> None:
        self.session_id = session_id
        self.config = config
        self._bundle: RuntimeBundle | None = None
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._current_task: asyncio.Task[None] | None = None

    @property
    def is_started(self) -> bool:
        return self._bundle is not None

    @property
    def is_busy(self) -> bool:
        return self._current_task is not None and not self._current_task.done()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def start(self) -> None:
        cfg = self.config
        self._bundle = await build_runtime(
            cwd=cfg.cwd,
            model=cfg.model or None,
            api_key=cfg.api_key or None,
            base_url=cfg.base_url or None,
            api_format=cfg.api_format or None,
            system_prompt=cfg.system_prompt or None,
            max_turns=cfg.max_turns,
            extra_skill_dirs=cfg.extra_skill_dirs or None,
            include_project_memory=False,
        )
        self._bundle.engine._permission_checker._settings.mode = PermissionMode.FULL_AUTO

    async def close(self) -> None:
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
        if self._bundle:
            await close_runtime(self._bundle)
            self._bundle = None

    async def submit(self, prompt: str) -> None:
        if self.is_busy:
            raise RuntimeError("Session is busy")
        if not self._bundle:
            raise RuntimeError("Session not started")
        self._current_task = asyncio.create_task(self._run_prompt(prompt))

    async def cancel(self) -> None:
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

    async def _run_prompt(self, prompt: str) -> None:
        assert self._bundle is not None
        await self._broadcast({"type": "session.started", "data": {"prompt": prompt}})
        try:
            async for event in self._bundle.engine.submit_message(prompt):
                msg = serialize_event(event)
                await self._broadcast(msg)
            await self._broadcast({"type": "session.done", "data": {}})
        except asyncio.CancelledError:
            await self._broadcast({"type": "session.cancelled", "data": {}})
            raise
        except Exception:
            log.exception("Prompt execution failed in session %s", self.session_id)
            await self._broadcast(
                {"type": "error", "data": {"message": "Internal error", "recoverable": False}}
            )

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(q)

    async def _broadcast(self, msg: dict[str, Any]) -> None:
        if "ts" not in msg:
            msg = {**msg, "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds")}
        for q in self._subscribers:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                log.warning("Dropping event for slow subscriber in session %s", self.session_id)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, NovelSession] = {}

    async def create(self, config: SessionConfig) -> NovelSession:
        session_id = uuid4().hex[:12]
        session = NovelSession(session_id, config)
        await session.start()
        self._sessions[session_id] = session
        return session

    async def create_for_agent(
        self,
        agent_name: str,
        project_cwd: str | None = None,
    ) -> NovelSession:
        from backend.config import get_settings
        from backend.runtime.agents import get_agent

        agent = get_agent(agent_name)
        if agent is None:
            raise ValueError(f"Agent not found: {agent_name}")

        settings = get_settings()
        config = SessionConfig(
            cwd=project_cwd or str(settings.projects_dir),
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            api_format=settings.llm_api_format,
            system_prompt=agent.system_prompt or "",
            max_turns=agent.max_turns or 16,
            extra_skill_dirs=(str(settings.skills_dir),),
            agent_name=agent_name,
        )
        return await self.create(config)

    def get(self, session_id: str) -> NovelSession | None:
        return self._sessions.get(session_id)

    def list_ids(self) -> list[str]:
        return list(self._sessions.keys())

    async def remove(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            await session.close()

    async def close_all(self) -> None:
        for session in list(self._sessions.values()):
            await session.close()
        self._sessions.clear()
