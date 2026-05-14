"""Tests for review/polish pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.orchestrator.review_pipeline import ReviewPipeline
from backend.projects.workspace import ProjectWorkspace


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
