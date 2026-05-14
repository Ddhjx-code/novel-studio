"""Standalone review/polish pipeline for existing chapter text."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import uuid4

from backend.projects.workspace import ProjectWorkspace
from backend.runtime.session import SessionManager

log = logging.getLogger(__name__)

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass
class ReviewResult:
    pipeline_id: str
    status: str = "pending"
    output_path: str = ""
    error: str | None = None


class ReviewPipeline:
    def __init__(
        self,
        session_manager: SessionManager,
        workspace: ProjectWorkspace,
        chapter_num: int,
        mode: str = "review",
    ) -> None:
        self._session_manager = session_manager
        self._workspace = workspace
        self._chapter_num = chapter_num
        self._mode = mode
        self._pipeline_id = uuid4().hex[:12]

    @property
    def pipeline_id(self) -> str:
        return self._pipeline_id

    async def run(self, event_callback: EventCallback | None = None) -> ReviewResult:
        """Run standalone review or polish on existing chapter text."""
        result = ReviewResult(pipeline_id=self._pipeline_id, status="running")

        chapter_text = self._workspace.read_file(
            f"chapters/ch{self._chapter_num:02d}.md"
        )
        if not chapter_text:
            result.status = "failed"
            result.error = f"Chapter {self._chapter_num} not found"
            return result

        agent_name = "reviewer" if self._mode == "review" else "polisher"

        if event_callback:
            await event_callback({
                "type": "pipeline.step_start",
                "data": {"step": self._mode, "agent": agent_name},
            })

        session = await self._session_manager.create_for_agent(
            agent_name, project_cwd=str(self._workspace.root)
        )
        queue = session.subscribe()

        try:
            prompt = self._build_prompt(chapter_text)
            await session.submit(prompt)
            output = await self._collect_output(queue)

            output_path = self._save_output(output)
            result.output_path = output_path
            result.status = "completed"

            if event_callback:
                await event_callback({
                    "type": "pipeline.step_complete",
                    "data": {"step": self._mode, "output_length": len(output)},
                })
        except asyncio.CancelledError:
            result.status = "cancelled"
        except Exception as e:
            log.exception("Review pipeline failed")
            result.status = "failed"
            result.error = str(e)
        finally:
            session.unsubscribe(queue)
            await self._session_manager.remove(session.session_id)

        return result

    def _build_prompt(self, chapter_text: str) -> str:
        n = self._chapter_num
        if self._mode == "review":
            return (
                f"请审查第{n}章正文，给出十维度评审报告。\n\n"
                f"章节正文：\n{chapter_text}\n"
            )
        return (
            f"请润色第{n}章正文，优化文笔但保持原意。\n\n"
            f"章节正文：\n{chapter_text}\n"
        )

    def _save_output(self, output: str) -> str:
        n = self._chapter_num
        if self._mode == "review":
            path = f"reviews/ch{n:02d}-review.md"
        else:
            path = f"chapters/ch{n:02d}.md"
        self._workspace.write_file(path, output)
        return path

    async def _collect_output(self, queue: asyncio.Queue[dict[str, Any]]) -> str:
        parts: list[str] = []
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300.0)
            except asyncio.TimeoutError:
                raise TimeoutError(f"{self._mode} timed out")

            event_type = event.get("type", "")
            if event_type == "agent.text":
                text = event.get("data", {}).get("text", "")
                if text:
                    parts.append(text)
            elif event_type == "session.done":
                break
            elif event_type == "error":
                msg = event.get("data", {}).get("message", "Unknown error")
                raise RuntimeError(f"{self._mode} agent error: {msg}")
            elif event_type == "session.cancelled":
                raise asyncio.CancelledError()

        return "".join(parts)
