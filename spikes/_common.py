"""Spike 通用工具：加载 .env.local 配置，避免依赖系统环境变量。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_env() -> None:
    """加载仓库根目录的 .env.local（不存在则尝试 .env.example 兜底，仅供报错提示）。"""
    env_local = REPO_ROOT / ".env.local"
    if env_local.exists():
        load_dotenv(env_local, override=False)
    else:
        raise SystemExit(
            f"[FAIL] 未找到 {env_local}。请复制 .env.example 为 .env.local 并填入真实配置。"
        )


@dataclass(frozen=True)
class LLMConfig:
    api_format: str
    base_url: str
    model: str
    api_key: str

    @classmethod
    def from_env(cls) -> "LLMConfig":
        api_key = os.environ.get("LLM_API_KEY", "").strip()
        base_url = os.environ.get("LLM_BASE_URL", "").strip()
        model = os.environ.get("LLM_MODEL", "").strip()
        api_format = os.environ.get("LLM_API_FORMAT", "openai_compat").strip()
        missing = [
            name
            for name, val in [
                ("LLM_API_KEY", api_key),
                ("LLM_BASE_URL", base_url),
                ("LLM_MODEL", model),
            ]
            if not val
        ]
        if missing:
            raise SystemExit(f"[FAIL] .env.local 缺字段: {missing}")
        if api_format not in {"openai_compat", "anthropic", "copilot"}:
            raise SystemExit(f"[FAIL] LLM_API_FORMAT 必须是 openai_compat/anthropic/copilot，当前: {api_format!r}")
        return cls(api_format=api_format, base_url=base_url, model=model, api_key=api_key)

    def banner(self) -> str:
        masked = self.api_key[:8] + "…" + self.api_key[-4:] if len(self.api_key) > 16 else "***"
        return (
            f"[INFO] api_format={self.api_format}\n"
            f"[INFO] base_url={self.base_url}\n"
            f"[INFO] model={self.model}\n"
            f"[INFO] api_key={masked}"
        )
