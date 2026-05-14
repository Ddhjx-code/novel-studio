"""应用全局配置，从 .env.local 加载，失败则用默认值。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    """启动时尝试加载 .env.local（不存在不报错，让默认值兜底）。"""
    env_local = REPO_ROOT / ".env.local"
    if env_local.exists():
        load_dotenv(env_local, override=False)


_load_env()


class Settings(BaseSettings):
    """全局设置 — 从环境变量读取（已通过 .env.local 注入）。"""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    # --- 服务 ---
    host: str = Field(default="127.0.0.1", alias="NOVEL_STUDIO_HOST")
    port: int = Field(default=8080, alias="NOVEL_STUDIO_PORT")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        alias="NOVEL_STUDIO_CORS_ORIGINS",
    )

    # --- LLM ---
    llm_api_format: str = Field(default="openai_compat", alias="LLM_API_FORMAT")
    llm_base_url: str = Field(default="", alias="LLM_BASE_URL")
    llm_model: str = Field(default="", alias="LLM_MODEL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")

    # --- Embedding ---
    embedding_api_format: str = Field(default="", alias="EMBEDDING_API_FORMAT")
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_model: str = Field(default="", alias="EMBEDDING_MODEL")
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")

    # --- 项目数据根目录 ---
    projects_dir: Path = Field(
        default_factory=lambda: REPO_ROOT / "projects",
        alias="NOVEL_STUDIO_PROJECTS_DIR",
    )

    # --- Agent / Skill 目录 ---
    agents_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "agents",
        alias="NOVEL_STUDIO_AGENTS_DIR",
    )
    skills_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "skills",
        alias="NOVEL_STUDIO_SKILLS_DIR",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
