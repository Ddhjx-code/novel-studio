"""Outline generation pipeline: single planner session."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import uuid4

from backend.projects.workspace import ProjectWorkspace
from backend.runtime.session import SessionManager

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------
_RETRY_MAX = 3
_RETRY_BASE_DELAY = 2.0  # seconds: 2 -> 4 -> 8
import re as _re

def _is_rate_limited(error: Exception) -> bool:
    """Return True when the error looks like a rate-limit (429) response."""
    msg = str(error)
    return bool(_re.search(r"(429|rate.limit)", msg, _re.IGNORECASE))

async def _retry_step(fn, step_label: str) -> str:
    """Call `fn()` with up to _RETRY_MAX attempts + exponential backoff on 429."""
    import asyncio as _asyncio
    last_err: Exception | None = None
    for attempt in range(1, _RETRY_MAX + 1):
        try:
            return await fn()
        except _asyncio.CancelledError:
            raise
        except Exception as e:
            last_err = e
            if not _is_rate_limited(e) or attempt == _RETRY_MAX:
                raise
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            log.warning(
                "Retrying step %s (attempt %d/%d after %.1fs): %s",
                step_label, attempt, _RETRY_MAX, delay, str(e)[:120],
            )
            await _asyncio.sleep(delay)
    raise last_err  # type: ignore[misc]
# ---------------------------------------------------------------------------


EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class OutlineResult:
    pipeline_id: str
    status: str = "pending"
    outline_path: str = ""
    error: str | None = None


class OutlinePipeline:
    def __init__(
        self,
        session_manager: SessionManager,
        workspace: ProjectWorkspace,
        synopsis: str,
        user_guidance: str = "",
    ) -> None:
        self._session_manager = session_manager
        self._workspace = workspace
        self._synopsis = synopsis
        self._user_guidance = user_guidance
        self._pipeline_id = uuid4().hex[:12]

    @property
    def pipeline_id(self) -> str:
        return self._pipeline_id

    async def run(self, event_callback: EventCallback | None = None) -> OutlineResult:
        """Dispatch planner with synopsis -> outline."""
        result = OutlineResult(pipeline_id=self._pipeline_id, status="running")

        if event_callback:
            await event_callback({
                "type": "pipeline.step_start",
                "data": {"step": "outline", "agent": "planner"},
            })

        session = await self._session_manager.create_for_agent(
            "planner", project_cwd=str(self._workspace.root)
        )
        queue = session.subscribe()

        try:
            prompt = self._build_prompt()

            async def _run_session():
                await session.submit(prompt)
                return await self._collect_output(queue)

            output = await _retry_step(_run_session, "outline")

            self._workspace.write_file("bible/plot/outline.md", output)
            result.outline_path = "bible/plot/outline.md"
            result.status = "completed"

            if event_callback:
                await event_callback({
                    "type": "pipeline.step_complete",
                    "data": {"step": "outline", "output_length": len(output)},
                })
        except asyncio.CancelledError:
            result.status = "cancelled"
        except Exception as e:
            log.exception("Outline pipeline failed")
            result.status = "failed"
            result.error = str(e)
        finally:
            session.unsubscribe(queue)
            await self._session_manager.remove(session.session_id)

        return result

    def _build_prompt(self) -> str:
        existing_outline = self._workspace.read_file("bible/plot/outline.md")
        parts = [
            "请根据以下故事简介，生成完整的章节大纲蓝图。\n",
            f"故事简介：\n{self._synopsis}\n",
        ]
        if self._user_guidance:
            parts.append(f"\n用户指导：\n{self._user_guidance}\n")
        if existing_outline:
            parts.append(f"\n现有大纲（可参考或覆盖）：\n{existing_outline}\n")
        return "\n".join(parts)

    async def _collect_output(self, queue: asyncio.Queue[dict[str, Any]]) -> str:
        parts: list[str] = []
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300.0)
            except asyncio.TimeoutError:
                raise TimeoutError("Outline generation timed out")

            event_type = event.get("type", "")
            if event_type == "agent.text":
                text = event.get("data", {}).get("text", "")
                if text:
                    parts.append(text)
            elif event_type == "session.done":
                break
            elif event_type == "error":
                msg = event.get("data", {}).get("message", "Unknown error")
                raise RuntimeError(f"Outline agent error: {msg}")
            elif event_type == "session.cancelled":
                raise asyncio.CancelledError()

        return "".join(parts)
