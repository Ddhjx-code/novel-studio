"""Core orchestration: multi-step chapter generation pipeline."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable
from uuid import uuid4

from backend.orchestrator.finalize import LLMConfig, finalize_chapter
from backend.projects.workspace import ProjectWorkspace
from backend.runtime.session import SessionManager
from backend.vectorstore.embedding import EmbeddingConfig

log = logging.getLogger(__name__)

EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


class PipelineStep(str, Enum):
    CONTEXT = "A"
    PLAN = "B"
    PLAN_REVIEW = "B5"
    WRITE = "C"
    REVIEW = "D"
    POLISH = "E"
    FINALIZE = "F"


ALL_STEPS = [
    PipelineStep.CONTEXT,
    PipelineStep.PLAN,
    PipelineStep.WRITE,
    PipelineStep.REVIEW,
    PipelineStep.POLISH,
    PipelineStep.FINALIZE,
]


@dataclass
class PipelineResult:
    pipeline_id: str
    project_name: str
    chapter_num: int
    status: str = "pending"
    steps_completed: list[str] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)
    error: str | None = None


_STEP_AGENT_MAP: dict[PipelineStep, str] = {
    PipelineStep.PLAN: "planner",
    PipelineStep.PLAN_REVIEW: "reviewer",
    PipelineStep.WRITE: "writer",
    PipelineStep.REVIEW: "reviewer",
    PipelineStep.POLISH: "polisher",
}


class ChapterPipeline:
    def __init__(
        self,
        session_manager: SessionManager,
        workspace: ProjectWorkspace,
        chapter_num: int,
        steps: list[PipelineStep] | None = None,
        llm_config: LLMConfig | None = None,
        embedding_config: EmbeddingConfig | None = None,
    ) -> None:
        self._session_manager = session_manager
        self._workspace = workspace
        self._chapter_num = chapter_num
        self._steps = steps or ALL_STEPS
        self._llm_config = llm_config or LLMConfig()
        self._embedding_config = embedding_config or EmbeddingConfig()
        self._pipeline_id = uuid4().hex[:12]
        self._cancelled = False
        self._current_task: asyncio.Task[None] | None = None

    @property
    def pipeline_id(self) -> str:
        return self._pipeline_id

    async def run(self, event_callback: EventCallback | None = None) -> PipelineResult:
        """Execute pipeline steps in order."""
        result = PipelineResult(
            pipeline_id=self._pipeline_id,
            project_name=self._workspace.name,
            chapter_num=self._chapter_num,
            status="running",
        )

        context_bundle: dict[str, str] = {}

        for step in self._steps:
            if self._cancelled:
                result.status = "cancelled"
                return result

            if event_callback:
                await event_callback({
                    "type": "pipeline.step_start",
                    "data": {"step": step.value, "agent": _STEP_AGENT_MAP.get(step, "")},
                })

            try:
                output = await self._execute_step(step, context_bundle, event_callback)
                result.outputs[step.value] = output
                result.steps_completed.append(step.value)

                if event_callback:
                    await event_callback({
                        "type": "pipeline.step_complete",
                        "data": {"step": step.value, "output_length": len(output)},
                    })
            except asyncio.CancelledError:
                result.status = "cancelled"
                return result
            except Exception as e:
                log.exception("Pipeline step %s failed", step.value)
                result.status = "failed"
                result.error = str(e)
                if event_callback:
                    await event_callback({
                        "type": "pipeline.step_failed",
                        "data": {"step": step.value, "error": str(e)},
                    })
                return result

        result.status = "completed"
        if event_callback:
            await event_callback({"type": "pipeline.done", "data": {"pipeline_id": self._pipeline_id}})
        return result

    async def cancel(self) -> None:
        self._cancelled = True
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()

    async def _execute_step(
        self,
        step: PipelineStep,
        context_bundle: dict[str, str],
        event_callback: EventCallback | None,
    ) -> str:
        if step == PipelineStep.CONTEXT:
            return await self._step_context(context_bundle)
        elif step == PipelineStep.FINALIZE:
            return await self._step_finalize()
        else:
            return await self._step_agent(step, context_bundle, event_callback)

    async def _step_context(self, context_bundle: dict[str, str]) -> str:
        """Load bible files, previous chapter tail, etc."""
        ws = self._workspace
        context_bundle["global_summary"] = ws.read_file("bible/global_summary.md")
        context_bundle["character_state"] = ws.read_file("bible/character_state.md")

        prev_num = self._chapter_num - 1
        if prev_num > 0:
            prev_text = ws.read_file(f"chapters/ch{prev_num:02d}.md")
            context_bundle["prev_chapter_tail"] = prev_text[-2000:] if prev_text else ""
        else:
            context_bundle["prev_chapter_tail"] = ""

        plan_text = ws.read_file(f"plans/ch{self._chapter_num:02d}-plan.md")
        context_bundle["existing_plan"] = plan_text

        return f"Context loaded: {len(context_bundle)} keys"

    async def _step_agent(
        self,
        step: PipelineStep,
        context_bundle: dict[str, str],
        event_callback: EventCallback | None,
    ) -> str:
        agent_name = _STEP_AGENT_MAP[step]
        prompt = self._build_prompt(step, context_bundle)

        session = await self._session_manager.create_for_agent(
            agent_name, project_cwd=str(self._workspace.root)
        )
        session_id = session.session_id
        queue = session.subscribe()

        try:
            await session.submit(prompt)
            output_text = await self._collect_output(queue, event_callback, step)

            self._save_step_output(step, output_text)

            if step == PipelineStep.WRITE:
                context_bundle["chapter_text"] = output_text
            elif step == PipelineStep.PLAN:
                context_bundle["plan_text"] = output_text

            return output_text
        finally:
            session.unsubscribe(queue)
            await self._session_manager.remove(session_id)

    async def _collect_output(
        self,
        queue: asyncio.Queue[dict[str, Any]],
        event_callback: EventCallback | None,
        step: PipelineStep,
    ) -> str:
        """Collect events from session until done, extract final text."""
        output_parts: list[str] = []

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300.0)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Step {step.value} timed out waiting for agent response")

            event_type = event.get("type", "")

            if event_callback:
                await event_callback({
                    "type": "pipeline.step_progress",
                    "data": {"step": step.value, "event": event},
                })

            if event_type == "agent.text":
                text = event.get("data", {}).get("text", "")
                if text:
                    output_parts.append(text)
            elif event_type == "session.done":
                break
            elif event_type == "error":
                msg = event.get("data", {}).get("message", "Unknown error")
                raise RuntimeError(f"Agent error in step {step.value}: {msg}")
            elif event_type == "session.cancelled":
                raise asyncio.CancelledError()

        return "".join(output_parts)

    def _build_prompt(self, step: PipelineStep, context_bundle: dict[str, str]) -> str:
        chapter_num = self._chapter_num
        summary = context_bundle.get("global_summary", "")
        char_state = context_bundle.get("character_state", "")
        prev_tail = context_bundle.get("prev_chapter_tail", "")

        if step == PipelineStep.PLAN:
            return (
                f"请为第{chapter_num}章创建详细的场景规划。\n\n"
                f"前文摘要：\n{summary}\n\n"
                f"角色状态：\n{char_state}\n\n"
                f"上一章结尾：\n{prev_tail}\n"
            )
        elif step == PipelineStep.WRITE:
            plan = context_bundle.get("plan_text", "")
            return (
                f"请根据以下规划撰写第{chapter_num}章正文。\n\n"
                f"章节规划：\n{plan}\n\n"
                f"前文摘要：\n{summary}\n\n"
                f"角色状态：\n{char_state}\n"
            )
        elif step == PipelineStep.REVIEW:
            chapter_text = context_bundle.get("chapter_text", "")
            return (
                f"请审查第{chapter_num}章正文，给出十维度评审报告。\n\n"
                f"章节正文：\n{chapter_text}\n"
            )
        elif step == PipelineStep.POLISH:
            chapter_text = context_bundle.get("chapter_text", "")
            return (
                f"请润色第{chapter_num}章正文，优化文笔但保持原意。\n\n"
                f"章节正文：\n{chapter_text}\n"
            )
        elif step == PipelineStep.PLAN_REVIEW:
            plan = context_bundle.get("plan_text", "")
            return (
                f"请快速审查第{chapter_num}章的规划，检查结构和因果链。\n\n"
                f"规划内容：\n{plan}\n"
            )
        return f"第{chapter_num}章相关任务"

    def _save_step_output(self, step: PipelineStep, output: str) -> None:
        ws = self._workspace
        n = self._chapter_num
        if step == PipelineStep.PLAN:
            ws.write_file(f"plans/ch{n:02d}-plan.md", output)
        elif step == PipelineStep.WRITE:
            ws.write_file(f"chapters/ch{n:02d}.md", output)
        elif step == PipelineStep.REVIEW:
            ws.write_file(f"reviews/ch{n:02d}-review.md", output)
        elif step == PipelineStep.POLISH:
            ws.write_file(f"chapters/ch{n:02d}.md", output)

    async def _step_finalize(self) -> str:
        chapter_text = self._workspace.read_file(
            f"chapters/ch{self._chapter_num:02d}.md"
        )
        if not chapter_text:
            return "No chapter text to finalize"

        result = await finalize_chapter(
            self._workspace,
            self._chapter_num,
            chapter_text,
            self._llm_config,
            self._embedding_config,
        )
        return f"Finalized: {result['chunk_count']} chunks indexed"
