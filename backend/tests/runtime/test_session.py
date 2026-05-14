from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from backend.runtime.session import NovelSession, SessionConfig, SessionManager


@pytest.fixture
def config() -> SessionConfig:
    return SessionConfig(
        cwd="/tmp/test-project",
        model="test-model",
        api_key="sk-test",
        base_url="http://localhost:1234/v1",
    )


class TestNovelSession:
    async def test_start_calls_build_runtime(self, config, mock_build_runtime, mock_close_runtime):
        build, bundle = mock_build_runtime
        with (
            patch("backend.runtime.session.build_runtime", build),
            patch("backend.runtime.session.close_runtime", mock_close_runtime),
        ):
            session = NovelSession("s1", config)
            await session.start()
            build.assert_called_once()
            assert session.is_started

    async def test_start_sets_full_auto_permission(self, config, mock_build_runtime, mock_close_runtime):
        build, bundle = mock_build_runtime
        with (
            patch("backend.runtime.session.build_runtime", build),
            patch("backend.runtime.session.close_runtime", mock_close_runtime),
        ):
            session = NovelSession("s1", config)
            await session.start()
            from openharness.permissions.modes import PermissionMode
            assert bundle.engine._permission_checker._settings.mode == PermissionMode.FULL_AUTO

    async def test_submit_broadcasts_events(self, config, mock_build_runtime, mock_close_runtime):
        build, bundle = mock_build_runtime
        with (
            patch("backend.runtime.session.build_runtime", build),
            patch("backend.runtime.session.close_runtime", mock_close_runtime),
        ):
            session = NovelSession("s1", config)
            await session.start()
            queue = session.subscribe()
            await session.submit("write something")
            await asyncio.sleep(0.1)
            received = []
            while not queue.empty():
                received.append(queue.get_nowait())
            types = [m["type"] for m in received]
            assert types[0] == "session.started"
            assert types[-1] == "session.done"
            assert "agent.text" in types

    async def test_close_calls_close_runtime(self, config, mock_build_runtime, mock_close_runtime):
        build, bundle = mock_build_runtime
        with (
            patch("backend.runtime.session.build_runtime", build),
            patch("backend.runtime.session.close_runtime", mock_close_runtime),
        ):
            session = NovelSession("s1", config)
            await session.start()
            await session.close()
            mock_close_runtime.assert_called_once_with(bundle)

    async def test_subscribe_unsubscribe(self, config, mock_build_runtime, mock_close_runtime):
        build, _ = mock_build_runtime
        with (
            patch("backend.runtime.session.build_runtime", build),
            patch("backend.runtime.session.close_runtime", mock_close_runtime),
        ):
            session = NovelSession("s1", config)
            await session.start()
            q = session.subscribe()
            assert session.subscriber_count == 1
            session.unsubscribe(q)
            assert session.subscriber_count == 0


class TestSessionManager:
    async def test_create_and_get(self, config, mock_build_runtime, mock_close_runtime):
        build, _ = mock_build_runtime
        with (
            patch("backend.runtime.session.build_runtime", build),
            patch("backend.runtime.session.close_runtime", mock_close_runtime),
        ):
            mgr = SessionManager()
            session = await mgr.create(config)
            assert mgr.get(session.session_id) is session

    async def test_remove_closes_session(self, config, mock_build_runtime, mock_close_runtime):
        build, _ = mock_build_runtime
        with (
            patch("backend.runtime.session.build_runtime", build),
            patch("backend.runtime.session.close_runtime", mock_close_runtime),
        ):
            mgr = SessionManager()
            session = await mgr.create(config)
            sid = session.session_id
            await mgr.remove(sid)
            assert mgr.get(sid) is None
            mock_close_runtime.assert_called_once()

    async def test_list_sessions(self, config, mock_build_runtime, mock_close_runtime):
        build, _ = mock_build_runtime
        with (
            patch("backend.runtime.session.build_runtime", build),
            patch("backend.runtime.session.close_runtime", mock_close_runtime),
        ):
            mgr = SessionManager()
            s1 = await mgr.create(config)
            s2 = await mgr.create(config)
            ids = mgr.list_ids()
            assert s1.session_id in ids
            assert s2.session_id in ids

    async def test_close_all(self, config, mock_build_runtime, mock_close_runtime):
        build, _ = mock_build_runtime
        with (
            patch("backend.runtime.session.build_runtime", build),
            patch("backend.runtime.session.close_runtime", mock_close_runtime),
        ):
            mgr = SessionManager()
            await mgr.create(config)
            await mgr.create(config)
            await mgr.close_all()
            assert mgr.list_ids() == []
