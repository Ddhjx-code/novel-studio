"""Shared context-loading helpers for pipeline orchestrators."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.projects.workspace import ProjectWorkspace
from backend.vectorstore.embedding import EmbeddingConfig, create_embedding_adapter
from backend.vectorstore.engine import FaissEngine

log = logging.getLogger(__name__)


_BIBLE_SECTION_MAX_CHARS = 6000


def load_template(skill_name: str, template_file: str) -> str:
    """Load a template file from the skills directory."""
    from backend.config import get_settings
    path = get_settings().skills_dir / skill_name / "templates" / template_file
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return ""


def load_bible_section(ws: ProjectWorkspace, subdir: str) -> str:
    """Load all files in a Bible subdirectory, concatenated with headers.

    Returns empty string if the subdirectory is empty or missing.
    Truncates at _BIBLE_SECTION_MAX_CHARS to avoid prompt overflow.
    """
    files = ws.list_files(subdir)
    if not files:
        return ""

    parts: list[str] = []
    total_len = 0

    for rel_path in files:
        content = ws.read_file(rel_path)
        if not content:
            continue
        filename = Path(rel_path).name
        section = f"## {filename}\n{content}\n"
        total_len += len(section)
        if total_len > _BIBLE_SECTION_MAX_CHARS:
            remaining = _BIBLE_SECTION_MAX_CHARS - (total_len - len(section))
            if remaining > 0:
                parts.append(section[:remaining] + "\n...（已截断）")
            break
        parts.append(section)

    return "\n".join(parts)


async def search_relevant_chunks(
    ws: ProjectWorkspace,
    query_text: str,
    embedding_config: EmbeddingConfig,
    exclude_chapter: int,
    top_k: int = 8,
) -> str:
    """Search FAISS for chunks relevant to query_text.

    Returns formatted results or empty string on any failure (non-blocking).
    """
    if not query_text:
        return ""

    store_dir = ws.root / "vectorstore"
    meta_path = store_dir / "metadata.jsonl"
    if not meta_path.exists():
        return ""

    try:
        adapter = create_embedding_adapter(embedding_config)
        query_trimmed = query_text[:500]
        embedding = await adapter.embed_query(query_trimmed)

        engine = FaissEngine.load(store_dir)
        chunks = engine.search(embedding, top_k=top_k, chapter_filter=exclude_chapter)

        if not chunks:
            return ""

        lines = [f"[第{c.chapter_num}章] {c.text}" for c in chunks]
        return "\n\n".join(lines)
    except Exception:
        log.debug("RAG search failed (non-critical), skipping", exc_info=True)
        return ""
