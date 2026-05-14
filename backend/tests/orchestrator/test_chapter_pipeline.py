"""Tests for chapter pipeline orchestration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.orchestrator.chapter_pipeline import (
    ALL_STEPS,
    ChapterPipeline,
    PipelineStep,
)
from backend.orchestrator.finalize import LLMConfig
from backend.projects.workspace import ProjectWorkspace
from backend.vectorstore.embedding import EmbeddingConfig


def _make_mock_session(output_events: list[dict] | None = None):
    """Create a mock session that yields events from a queue."""
    session = MagicMock()
    session.session_id = "test-session-123"
    queue: asyncio.Queue = asyncio.Queue()

    if output_events is None:
        output_events = [
            {"type": "agent.text", "data": {"text": "生成的内容"}},
            {"type": "session.done", "data": {}},
        ]

    for ev in output_events:
        queue.put_nowait(ev)

    session.subscribe.return_value = queue
    session.unsubscribe = MagicMock()
    session.submit = AsyncMock()
    return session


@pytest.fixture
def workspace(tmp_path: Path) -> ProjectWorkspace:
    ws = ProjectWorkspace(tmp_path, "test-novel")
    ws.ensure()
    return ws


@pytest.fixture
def mock_session_manager():
    mgr = MagicMock()
    mgr.create_for_agent = AsyncMock(side_effect=lambda *a, **kw: _make_mock_session())
    mgr.remove = AsyncMock()
    return mgr


class TestChapterPipeline:
    @pytest.mark.asyncio
    async def test_context_step_loads_files(self, workspace, mock_session_manager):
        workspace.write_file("bible/global_summary.md", "旧摘要")
        workspace.write_file("bible/character_state.md", "角色状态")

        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            steps=[PipelineStep.CONTEXT],
        )
        result = await pipeline.run()
        assert result.status == "completed"
        assert "A" in result.steps_completed

    @pytest.mark.asyncio
    async def test_agent_steps_create_and_destroy_sessions(self, workspace, mock_session_manager):
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            steps=[PipelineStep.PLAN],
        )
        result = await pipeline.run()
        assert result.status == "completed"
        mock_session_manager.create_for_agent.assert_called_once_with(
            "planner", project_cwd=str(workspace.root)
        )
        mock_session_manager.remove.assert_called_once()

    @pytest.mark.asyncio
    async def test_partial_steps(self, workspace, mock_session_manager):
        workspace.write_file("chapters/ch01.md", "已有正文")

        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            steps=[PipelineStep.REVIEW, PipelineStep.POLISH],
        )
        result = await pipeline.run()
        assert result.status == "completed"
        assert len(result.steps_completed) == 2
        assert mock_session_manager.create_for_agent.call_count == 2

    @pytest.mark.asyncio
    async def test_event_callback_receives_events(self, workspace, mock_session_manager):
        events_received: list[dict] = []

        async def callback(event):
            events_received.append(event)

        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            steps=[PipelineStep.CONTEXT, PipelineStep.PLAN],
        )
        await pipeline.run(event_callback=callback)

        event_types = [e["type"] for e in events_received]
        assert "pipeline.step_start" in event_types
        assert "pipeline.step_complete" in event_types

    @pytest.mark.asyncio
    async def test_cancellation(self, workspace, mock_session_manager):
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            steps=[PipelineStep.CONTEXT, PipelineStep.PLAN, PipelineStep.WRITE],
        )
        await pipeline.cancel()
        result = await pipeline.run()
        assert result.status == "cancelled"

    @pytest.mark.asyncio
    async def test_plan_output_saved(self, workspace, mock_session_manager):
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            steps=[PipelineStep.PLAN],
        )
        await pipeline.run()
        plan_content = workspace.read_file("plans/ch01-plan.md")
        assert plan_content == "生成的内容"

    @pytest.mark.asyncio
    async def test_write_output_saved(self, workspace, mock_session_manager):
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=2,
            steps=[PipelineStep.WRITE],
        )
        await pipeline.run()
        chapter_content = workspace.read_file("chapters/ch02.md")
        assert chapter_content == "生成的内容"

    @pytest.mark.asyncio
    async def test_finalize_step(self, workspace, mock_session_manager):
        workspace.write_file("chapters/ch01.md", "测试正文。" * 10)

        with (
            patch(
                "backend.orchestrator.chapter_pipeline.finalize_chapter",
                new_callable=AsyncMock,
                return_value={"chunk_count": 5, "summary_length": 100, "state_length": 50, "chapter_num": 1},
            ),
        ):
            pipeline = ChapterPipeline(
                session_manager=mock_session_manager,
                workspace=workspace,
                chapter_num=1,
                steps=[PipelineStep.FINALIZE],
            )
            result = await pipeline.run()

        assert result.status == "completed"
        assert "F" in result.steps_completed

    @pytest.mark.asyncio
    async def test_agent_error_fails_pipeline(self, workspace):
        error_session = _make_mock_session([
            {"type": "error", "data": {"message": "LLM failure"}},
        ])
        mgr = MagicMock()
        mgr.create_for_agent = AsyncMock(return_value=error_session)
        mgr.remove = AsyncMock()

        pipeline = ChapterPipeline(
            session_manager=mgr,
            workspace=workspace,
            chapter_num=1,
            steps=[PipelineStep.PLAN],
        )
        result = await pipeline.run()
        assert result.status == "failed"
        assert "LLM failure" in (result.error or "")
