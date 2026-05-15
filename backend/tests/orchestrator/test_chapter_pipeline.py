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
    async def test_context_step_loads_bible_sections(self, workspace, mock_session_manager):
        workspace.write_file("bible/global_summary.md", "摘要")
        workspace.write_file("bible/character_state.md", "状态")
        workspace.write_file("bible/characters/hero.md", "主角：张三")
        workspace.write_file("bible/worldbuilding/setting.md", "世界观设定")
        workspace.write_file("bible/plot/outline.md", "大纲内容")

        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            steps=[PipelineStep.CONTEXT],
        )
        result = await pipeline.run()
        assert result.status == "completed"
        assert "Context loaded:" in result.outputs["A"]

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
    async def test_plan_output_read_back_from_file(self, workspace):
        """PLAN step: if agent writes the file, pipeline reads it back."""
        agent_written_content = "Agent写入的规划内容"

        async def mock_submit(prompt):
            workspace.write_file("plans/ch01-plan.md", agent_written_content)

        session = _make_mock_session([
            {"type": "agent.text", "data": {"text": "规划已完成，写入 plans/ch01-plan.md"}},
            {"type": "session.done", "data": {}},
        ])
        session.submit = AsyncMock(side_effect=mock_submit)

        mgr = MagicMock()
        mgr.create_for_agent = AsyncMock(return_value=session)
        mgr.remove = AsyncMock()

        pipeline = ChapterPipeline(
            session_manager=mgr,
            workspace=workspace,
            chapter_num=1,
            steps=[PipelineStep.PLAN],
        )
        result = await pipeline.run()
        assert result.status == "completed"
        assert result.outputs["B"] == agent_written_content

    @pytest.mark.asyncio
    async def test_plan_fallback_to_text_output(self, workspace, mock_session_manager):
        """PLAN step: if agent doesn't write file, use text output as fallback."""
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            steps=[PipelineStep.PLAN],
        )
        result = await pipeline.run()
        assert result.status == "completed"
        plan_content = workspace.read_file("plans/ch01-plan.md")
        assert plan_content == "生成的内容"

    @pytest.mark.asyncio
    async def test_write_output_read_back_from_file(self, workspace):
        """WRITE step: if agent writes the file, pipeline reads it back."""
        agent_written_content = "Agent写入的章节正文"

        async def mock_submit(prompt):
            workspace.write_file("chapters/ch02.md", agent_written_content)

        session = _make_mock_session([
            {"type": "agent.text", "data": {"text": "章节已写入"}},
            {"type": "session.done", "data": {}},
        ])
        session.submit = AsyncMock(side_effect=mock_submit)

        mgr = MagicMock()
        mgr.create_for_agent = AsyncMock(return_value=session)
        mgr.remove = AsyncMock()

        pipeline = ChapterPipeline(
            session_manager=mgr,
            workspace=workspace,
            chapter_num=2,
            steps=[PipelineStep.WRITE],
        )
        result = await pipeline.run()
        assert result.status == "completed"
        assert result.outputs["C"] == agent_written_content

    @pytest.mark.asyncio
    async def test_review_saves_text_output(self, workspace, mock_session_manager):
        """REVIEW step: pipeline saves text output to file (not read-back)."""
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            steps=[PipelineStep.REVIEW],
        )
        result = await pipeline.run()
        assert result.status == "completed"
        review_content = workspace.read_file("reviews/ch01-review.md")
        assert review_content == "生成的内容"

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


class TestBuildPrompt:
    """Test that _build_prompt includes Bible and RAG content."""

    def test_plan_prompt_includes_bible(self, workspace, mock_session_manager):
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
        )
        context = {
            "global_summary": "前文摘要",
            "character_state": "角色状态",
            "prev_chapter_tail": "",
            "bible_characters": "## hero.md\n名字：张三\n年龄：25",
            "bible_worldbuilding": "## world.md\n现代都市",
            "bible_plot": "## outline.md\n三幕结构",
            "rag_results": "[第1章] 前文片段内容",
            "existing_plan": "已有规划",
        }
        prompt = pipeline._build_prompt(PipelineStep.PLAN, context)
        assert "角色设定" in prompt
        assert "张三" in prompt
        assert "世界观" in prompt
        assert "现代都市" in prompt
        assert "剧情规划" in prompt
        assert "相关前文片段" in prompt
        assert "已有规划" in prompt

    def test_write_prompt_includes_bible(self, workspace, mock_session_manager):
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
        )
        context = {
            "global_summary": "前文摘要",
            "character_state": "角色状态",
            "plan_text": "规划内容",
            "bible_characters": "## hero.md\n主角设定",
            "bible_worldbuilding": "## world.md\n设定",
            "rag_results": "[第1章] 片段",
            "existing_plan": "",
        }
        prompt = pipeline._build_prompt(PipelineStep.WRITE, context)
        assert "角色设定" in prompt
        assert "主角设定" in prompt
        assert "世界观" in prompt
        assert "相关前文片段" in prompt

    def test_review_prompt_uses_consistency_template(self, workspace, mock_session_manager):
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
        )
        context = {
            "global_summary": "摘要内容",
            "character_state": "状态内容",
            "chapter_text": "章节正文",
            "bible_characters": "角色设定内容",
            "bible_worldbuilding": "世界观内容",
            "bible_plot": "剧情规划",
            "rag_results": "[第1章] 相关片段",
        }
        prompt = pipeline._build_prompt(PipelineStep.REVIEW, context)
        assert "一致性检查参考资料" in prompt
        assert "章节正文" in prompt
        assert "相关前文片段" in prompt

    def test_polish_prompt_unchanged(self, workspace, mock_session_manager):
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
        )
        context = {
            "chapter_text": "章节正文内容",
            "bible_characters": "不应出现",
            "rag_results": "也不应出现",
        }
        prompt = pipeline._build_prompt(PipelineStep.POLISH, context)
        assert "章节正文内容" in prompt
        assert "不应出现" not in prompt

    def test_empty_context_fields_omitted(self, workspace, mock_session_manager):
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
        )
        context = {
            "global_summary": "",
            "character_state": "",
            "prev_chapter_tail": "",
            "bible_characters": "",
            "bible_worldbuilding": "",
            "bible_plot": "",
            "rag_results": "",
            "existing_plan": "",
        }
        prompt = pipeline._build_prompt(PipelineStep.PLAN, context)
        assert "角色设定：\n" not in prompt
        assert "世界观：\n" not in prompt
        assert "相关前文片段：\n" not in prompt

    def test_write_uses_existing_plan_as_fallback(self, workspace, mock_session_manager):
        pipeline = ChapterPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
        )
        context = {
            "global_summary": "",
            "character_state": "",
            "plan_text": "",
            "bible_characters": "",
            "bible_worldbuilding": "",
            "rag_results": "",
            "existing_plan": "用户手写的规划",
        }
        prompt = pipeline._build_prompt(PipelineStep.WRITE, context)
        assert "用户手写的规划" in prompt
