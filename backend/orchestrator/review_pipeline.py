"""Standalone review/polish pipeline for existing chapter text."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import uuid4

from backend.orchestrator.context_helpers import load_bible_section, load_template, search_relevant_chunks
from backend.prompts import format_prompt
from backend.projects.workspace import ProjectWorkspace
from backend.runtime.session import SessionManager
from backend.vectorstore.embedding import EmbeddingConfig

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------
_RETRY_MAX = 3
_RETRY_BASE_DELAY = 2.0  # seconds: 2 -> 4 -> 8
import re as _re

def _is_rate_limited(error: Exception) -> bool:
    msg = str(error)
    return bool(_re.search(r"(429|rate.limit)", msg, _re.IGNORECASE))

async def _retry_step(fn, step_label: str) -> str:
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
        embedding_config: EmbeddingConfig | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._workspace = workspace
        self._chapter_num = chapter_num
        self._mode = mode
        self._embedding_config = embedding_config or EmbeddingConfig()
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
            prompt = await self._build_prompt(chapter_text)
            async def _run_session():
                await session.submit(prompt)
                return await self._collect_output(queue)

            output = await _retry_step(_run_session, self._step.value if hasattr(self, '_step') else "review")

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

    async def _build_prompt(self, chapter_text: str) -> str:
        n = self._chapter_num
        if self._mode == "review":
            return await self._build_review_prompt(n, chapter_text)
        return (
            f"请润色第{n}章正文，优化文笔但保持原意。\n\n"
            f"章节正文：\n{chapter_text}\n"
        )

    async def _build_review_prompt(self, chapter_num: int, chapter_text: str) -> str:
        ws = self._workspace
        summary = ws.read_file("bible/global_summary.md")
        char_state = ws.read_file("bible/character_state.md")
        bible_characters = load_bible_section(ws, "bible/characters")
        bible_worldbuilding = load_bible_section(ws, "bible/worldbuilding")
        bible_plot = load_bible_section(ws, "bible/plot")

        rag_query = chapter_text[:500] if chapter_text else summary
        rag_results = await search_relevant_chunks(
            ws, rag_query, self._embedding_config, chapter_num
        )

        sections = [f"请审查第{chapter_num}章正文，给出十维度评审报告。\n"]
        sections.append(f"章节正文：\n{chapter_text}\n")

        novel_setting = "\n".join(filter(None, [bible_characters, bible_worldbuilding]))
        if novel_setting or char_state or summary or bible_plot:
            consistency_section = format_prompt(
                "consistency_check_prompt",
                novel_setting=novel_setting,
                character_state=char_state,
                global_summary=summary,
                plot_arcs=bible_plot,
                chapter_text=chapter_text,
            )
            sections.append(f"--- 一致性检查参考资料 ---\n{consistency_section}\n")

        if rag_results:
            sections.append(f"相关前文片段：\n{rag_results}\n")

        template = load_template("reviewer-skill", "review-report-template.md")
        if template:
            sections.append(f"--- 输出模板 ---\n请按以下模板格式输出：\n{template}\n")

        return "\n".join(sections)

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
                event = await asyncio.wait_for(queue.get(), timeout=600.0)
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
