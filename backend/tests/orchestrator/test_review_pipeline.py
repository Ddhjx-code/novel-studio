"""Tests for review/polish pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.orchestrator.review_pipeline import ReviewPipeline
from backend.projects.workspace import ProjectWorkspace
from backend.vectorstore.embedding import EmbeddingConfig


def _make_mock_session(output_text: str = "审查报告"):
    session = MagicMock()
    session.session_id = "review-session"
    queue: asyncio.Queue = asyncio.Queue()
    queue.put_nowait({"type": "agent.text", "data": {"text": output_text}})
    queue.put_nowait({"type": "session.done", "data": {}})
    session.subscribe.return_value = queue
    session.unsubscribe = MagicMock()
    session.submit = AsyncMock()
    return session


@pytest.fixture
def workspace(tmp_path: Path) -> ProjectWorkspace:
    ws = ProjectWorkspace(tmp_path, "test-novel")
    ws.ensure()
    ws.write_file("chapters/ch01.md", "第一章正文内容")
    return ws


@pytest.fixture
def mock_session_manager():
    mgr = MagicMock()
    mgr.create_for_agent = AsyncMock(side_effect=lambda *a, **kw: _make_mock_session())
    mgr.remove = AsyncMock()
    return mgr


class TestReviewPipeline:
    @pytest.mark.asyncio
    async def test_review_mode(self, workspace, mock_session_manager):
        pipeline = ReviewPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            mode="review",
        )
        result = await pipeline.run()
        assert result.status == "completed"
        assert result.output_path == "reviews/ch01-review.md"

        content = workspace.read_file("reviews/ch01-review.md")
        assert content == "审查报告"

    @pytest.mark.asyncio
    async def test_polish_mode(self, workspace, mock_session_manager):
        pipeline = ReviewPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            mode="polish",
        )
        result = await pipeline.run()
        assert result.status == "completed"
        assert result.output_path == "chapters/ch01.md"

    @pytest.mark.asyncio
    async def test_uses_correct_agent(self, workspace, mock_session_manager):
        pipeline = ReviewPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            mode="review",
        )
        await pipeline.run()
        mock_session_manager.create_for_agent.assert_called_with(
            "reviewer", project_cwd=str(workspace.root)
        )

    @pytest.mark.asyncio
    async def test_polish_uses_polisher(self, workspace, mock_session_manager):
        pipeline = ReviewPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            mode="polish",
        )
        await pipeline.run()
        mock_session_manager.create_for_agent.assert_called_with(
            "polisher", project_cwd=str(workspace.root)
        )

    @pytest.mark.asyncio
    async def test_missing_chapter_fails(self, workspace, mock_session_manager):
        pipeline = ReviewPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=99,
            mode="review",
        )
        result = await pipeline.run()
        assert result.status == "failed"
        assert "not found" in (result.error or "")

    @pytest.mark.asyncio
    async def test_review_prompt_includes_bible(self, workspace, mock_session_manager):
        """Review mode should load Bible content into prompt."""
        workspace.write_file("bible/characters/hero.md", "名字：张三\n年龄：25")
        workspace.write_file("bible/worldbuilding/setting.md", "现代都市")
        workspace.write_file("bible/global_summary.md", "全局摘要")
        workspace.write_file("bible/character_state.md", "角色状态")

        submitted_prompts: list[str] = []

        async def capture_submit(prompt):
            submitted_prompts.append(prompt)

        session = _make_mock_session()
        session.submit = AsyncMock(side_effect=capture_submit)
        mgr = MagicMock()
        mgr.create_for_agent = AsyncMock(return_value=session)
        mgr.remove = AsyncMock()

        pipeline = ReviewPipeline(
            session_manager=mgr,
            workspace=workspace,
            chapter_num=1,
            mode="review",
        )
        await pipeline.run()

        assert len(submitted_prompts) == 1
        prompt = submitted_prompts[0]
        assert "张三" in prompt
        assert "现代都市" in prompt
        assert "一致性检查参考资料" in prompt

    @pytest.mark.asyncio
    async def test_polish_prompt_unchanged(self, workspace, mock_session_manager):
        """Polish mode should NOT load Bible content."""
        workspace.write_file("bible/characters/hero.md", "名字：张三")

        submitted_prompts: list[str] = []

        async def capture_submit(prompt):
            submitted_prompts.append(prompt)

        session = _make_mock_session()
        session.submit = AsyncMock(side_effect=capture_submit)
        mgr = MagicMock()
        mgr.create_for_agent = AsyncMock(return_value=session)
        mgr.remove = AsyncMock()

        pipeline = ReviewPipeline(
            session_manager=mgr,
            workspace=workspace,
            chapter_num=1,
            mode="polish",
        )
        await pipeline.run()

        assert len(submitted_prompts) == 1
        prompt = submitted_prompts[0]
        assert "张三" not in prompt
        assert "润色" in prompt

    @pytest.mark.asyncio
    async def test_embedding_config_passed(self, workspace, mock_session_manager):
        """Embedding config should be accepted by constructor."""
        config = EmbeddingConfig(
            api_format="openai_compat",
            base_url="http://test:8080",
            model="test-embed",
            api_key="test-key",
        )
        pipeline = ReviewPipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            chapter_num=1,
            mode="review",
            embedding_config=config,
        )
        assert pipeline._embedding_config == config
