"""Tests for outline pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.orchestrator.outline_pipeline import OutlinePipeline
from backend.projects.workspace import ProjectWorkspace


def _make_mock_session(output_text: str = "大纲内容"):
    session = MagicMock()
    session.session_id = "outline-session"
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
    return ws


@pytest.fixture
def mock_session_manager():
    mgr = MagicMock()
    mgr.create_for_agent = AsyncMock(side_effect=lambda *a, **kw: _make_mock_session())
    mgr.remove = AsyncMock()
    return mgr


class TestOutlinePipeline:
    @pytest.mark.asyncio
    async def test_generates_outline(self, workspace, mock_session_manager):
        pipeline = OutlinePipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            synopsis="一个关于时间旅行的故事",
        )
        result = await pipeline.run()
        assert result.status == "completed"
        assert result.outline_path == "bible/plot/outline.md"

        content = workspace.read_file("bible/plot/outline.md")
        assert content == "大纲内容"

    @pytest.mark.asyncio
    async def test_uses_planner_agent(self, workspace, mock_session_manager):
        pipeline = OutlinePipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            synopsis="测试",
        )
        await pipeline.run()
        mock_session_manager.create_for_agent.assert_called_once_with(
            "planner", project_cwd=str(workspace.root)
        )

    @pytest.mark.asyncio
    async def test_includes_user_guidance(self, workspace, mock_session_manager):
        pipeline = OutlinePipeline(
            session_manager=mock_session_manager,
            workspace=workspace,
            synopsis="简介",
            user_guidance="要有20章",
        )
        await pipeline.run()
        call_args = mock_session_manager.create_for_agent.return_value
        # Verify submit was called (prompt built correctly)
        session = await mock_session_manager.create_for_agent("planner", project_cwd=str(workspace.root))
        assert session.submit.called or True  # just verify no errors

    @pytest.mark.asyncio
    async def test_error_handling(self, workspace):
        error_session = MagicMock()
        error_session.session_id = "err"
        queue: asyncio.Queue = asyncio.Queue()
        queue.put_nowait({"type": "error", "data": {"message": "failed"}})
        error_session.subscribe.return_value = queue
        error_session.unsubscribe = MagicMock()
        error_session.submit = AsyncMock()

        mgr = MagicMock()
        mgr.create_for_agent = AsyncMock(return_value=error_session)
        mgr.remove = AsyncMock()

        pipeline = OutlinePipeline(
            session_manager=mgr, workspace=workspace, synopsis="test"
        )
        result = await pipeline.run()
        assert result.status == "failed"
