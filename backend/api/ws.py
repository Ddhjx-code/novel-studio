"""WebSocket endpoint for streaming session events to the browser."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.runtime.session import SessionManager

log = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/sessions/{session_id}")
async def session_events(websocket: WebSocket, session_id: str):
    manager: SessionManager = websocket.app.state.session_manager
    session = manager.get(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    queue = session.subscribe()
    try:
        while True:
            msg = await queue.get()
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        log.debug("WebSocket client disconnected from session %s", session_id)
    except Exception:
        log.exception("WebSocket error in session %s", session_id)
    finally:
        session.unsubscribe(queue)
