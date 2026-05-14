"""Prompt template loader with caching."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Load a prompt template by name (without .md extension)."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


def format_prompt(name: str, **kwargs: str) -> str:
    """Load and format a prompt template with the given kwargs."""
    template = load_prompt(name)
    return template.format(**kwargs)
