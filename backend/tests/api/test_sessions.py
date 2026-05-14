from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from backend.runtime.session import NovelSession, SessionConfig, SessionManager


@pytest.fixture
def mock_session() -> NovelSession:
    s = MagicMock(spec=NovelSession)
    s.session_id = "abc123"
    s.is_busy = False
    s.is_started = True
    s.subscriber_count = 0
    s.config = SessionConfig(cwd="/tmp/test")
    s.submit = AsyncMock()
    s.cancel = AsyncMock()
    s.close = AsyncMock()
    return s


@pytest.fixture
def mock_manager(mock_session) -> SessionManager:
    mgr = MagicMock(spec=SessionManager)
    mgr.create = AsyncMock(return_value=mock_session)
    mgr.get = MagicMock(return_value=mock_session)
    mgr.list_ids = MagicMock(return_value=["abc123"])
    mgr.remove = AsyncMock()
    mgr.close_all = AsyncMock()
    return mgr


@pytest.fixture
async def client(mock_manager):
    app = create_app()
    app.state.session_manager = mock_manager
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestCreateSession:
    async def test_create_returns_session_id(self, client, mock_manager):
        resp = await client.post("/sessions", json={"cwd": "/tmp/proj"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "abc123"
        mock_manager.create.assert_called_once()


class TestListSessions:
    async def test_list_returns_ids(self, client):
        resp = await client.get("/sessions")
        assert resp.status_code == 200
        assert resp.json() == {"session_ids": ["abc123"]}


class TestSubmitPrompt:
    async def test_submit_returns_accepted(self, client, mock_session):
        resp = await client.post("/sessions/abc123/submit", json={"prompt": "hello"})
        assert resp.status_code == 202
        mock_session.submit.assert_called_once_with("hello")

    async def test_submit_not_found(self, client, mock_manager):
        mock_manager.get.return_value = None
        resp = await client.post("/sessions/unknown/submit", json={"prompt": "x"})
        assert resp.status_code == 404


class TestCancelSession:
    async def test_cancel_returns_ok(self, client, mock_session):
        resp = await client.post("/sessions/abc123/cancel")
        assert resp.status_code == 200
        mock_session.cancel.assert_called_once()


class TestDeleteSession:
    async def test_delete_returns_ok(self, client, mock_manager):
        resp = await client.delete("/sessions/abc123")
        assert resp.status_code == 200
        mock_manager.remove.assert_called_once_with("abc123")
