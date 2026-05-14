"""REST endpoints for session lifecycle and prompt submission."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.config import get_settings
from backend.runtime.session import SessionConfig, SessionManager

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _manager(request: Request) -> SessionManager:
    return request.app.state.session_manager


class CreateSessionBody(BaseModel):
    cwd: str = ""
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    api_format: str = ""
    system_prompt: str = ""
    max_turns: int = 8
    agent_name: str = ""


class SubmitBody(BaseModel):
    prompt: str


@router.post("")
async def create_session(body: CreateSessionBody, request: Request):
    mgr = _manager(request)
    if body.agent_name:
        session = await mgr.create_for_agent(
            body.agent_name,
            project_cwd=body.cwd or None,
        )
        return {"session_id": session.session_id, "agent_name": body.agent_name}

    settings = get_settings()
    config = SessionConfig(
        cwd=body.cwd or str(settings.projects_dir),
        model=body.model or settings.llm_model,
        api_key=body.api_key or settings.llm_api_key,
        base_url=body.base_url or settings.llm_base_url,
        api_format=body.api_format or settings.llm_api_format,
        system_prompt=body.system_prompt,
        max_turns=body.max_turns,
    )
    session = await mgr.create(config)
    return {"session_id": session.session_id}


@router.get("")
async def list_sessions(request: Request):
    return {"session_ids": _manager(request).list_ids()}


@router.post("/{session_id}/submit", status_code=202)
async def submit_prompt(session_id: str, body: SubmitBody, request: Request):
    session = _manager(request).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await session.submit(body.prompt)
    return {"status": "accepted"}


@router.post("/{session_id}/cancel")
async def cancel_session(session_id: str, request: Request):
    session = _manager(request).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await session.cancel()
    return {"status": "cancelled"}


@router.delete("/{session_id}")
async def delete_session(session_id: str, request: Request):
    mgr = _manager(request)
    if not mgr.get(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    await mgr.remove(session_id)
    return {"status": "deleted"}
