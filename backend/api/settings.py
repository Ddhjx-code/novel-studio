"""REST endpoints for application settings (LLM config)."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import REPO_ROOT, get_settings

router = APIRouter(prefix="/settings", tags=["settings"])

_ENV_FILE = REPO_ROOT / ".env.local"

_MANAGED_KEYS = [
    "LLM_API_FORMAT",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "EMBEDDING_API_FORMAT",
    "EMBEDDING_BASE_URL",
    "EMBEDDING_MODEL",
    "EMBEDDING_API_KEY",
]


def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return "***" if key else ""
    return key[:4] + "***" + key[-4:]


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Z_]+)=(.*)", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def _write_env_file(path: Path, values: dict[str, str]) -> None:
    existing = _read_env_file(path)
    merged = {**existing, **values}
    lines: list[str] = []
    for k in sorted(merged.keys()):
        v = merged[k]
        if v:
            lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class LLMSettingsResponse(BaseModel):
    llm_api_format: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    embedding_api_format: str = ""
    embedding_base_url: str = ""
    embedding_model: str = ""
    embedding_api_key: str = ""


class UpdateSettingsBody(BaseModel):
    llm_api_format: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = None
    embedding_api_format: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str | None = None
    embedding_api_key: str | None = None


@router.get("")
async def get_settings_endpoint() -> LLMSettingsResponse:
    settings = get_settings()
    return LLMSettingsResponse(
        llm_api_format=settings.llm_api_format,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        llm_api_key=_mask_key(settings.llm_api_key),
        embedding_api_format=settings.embedding_api_format,
        embedding_base_url=settings.embedding_base_url,
        embedding_model=settings.embedding_model,
        embedding_api_key=_mask_key(settings.embedding_api_key),
    )


@router.put("")
async def update_settings_endpoint(body: UpdateSettingsBody) -> dict[str, str]:
    updates: dict[str, str] = {}
    field_map = {
        "llm_api_format": "LLM_API_FORMAT",
        "llm_base_url": "LLM_BASE_URL",
        "llm_model": "LLM_MODEL",
        "llm_api_key": "LLM_API_KEY",
        "embedding_api_format": "EMBEDDING_API_FORMAT",
        "embedding_base_url": "EMBEDDING_BASE_URL",
        "embedding_model": "EMBEDDING_MODEL",
        "embedding_api_key": "EMBEDDING_API_KEY",
    }
    for field, env_key in field_map.items():
        value = getattr(body, field)
        if value is not None and not (value.startswith("***") or value.endswith("***")):
            updates[env_key] = value

    if updates:
        _write_env_file(_ENV_FILE, updates)
        get_settings.cache_clear()

    return {"status": "saved", "updated": list(updates.keys())}
