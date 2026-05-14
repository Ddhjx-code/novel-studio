"""Post-chapter finalization: summary, character state, FAISS ingestion."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from backend.prompts import format_prompt
from backend.projects.workspace import ProjectWorkspace
from backend.vectorstore.embedding import EmbeddingConfig, create_embedding_adapter
from backend.vectorstore.engine import Chunk, FaissEngine
from backend.vectorstore.text_splitter import split_into_chunks

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMConfig:
    """Minimal LLM config for direct API calls (non-agent)."""

    api_format: str = "openai_compat"
    base_url: str = ""
    model: str = ""
    api_key: str = ""


async def _llm_complete(prompt: str, config: LLMConfig) -> str:
    """Make a single completion request via httpx to OpenAI-compatible API."""
    base_url = config.base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def update_global_summary(
    workspace: ProjectWorkspace,
    chapter_num: int,
    chapter_text: str,
    llm_config: LLMConfig,
) -> str:
    """Call LLM with summary_prompt to update global_summary.md."""
    old_summary = workspace.read_file("bible/global_summary.md")
    prompt = format_prompt("summary_prompt", chapter_text=chapter_text, global_summary=old_summary)
    new_summary = await _llm_complete(prompt, llm_config)
    workspace.write_file("bible/global_summary.md", new_summary)
    return new_summary


async def update_character_state(
    workspace: ProjectWorkspace,
    chapter_num: int,
    chapter_text: str,
    llm_config: LLMConfig,
) -> str:
    """Call LLM with update_character_state_prompt."""
    old_state = workspace.read_file("bible/character_state.md")
    prompt = format_prompt(
        "update_character_state_prompt", chapter_text=chapter_text, old_state=old_state
    )
    new_state = await _llm_complete(prompt, llm_config)
    workspace.write_file("bible/character_state.md", new_state)
    return new_state


async def ingest_chapter(
    workspace: ProjectWorkspace,
    chapter_num: int,
    chapter_text: str,
    embedding_config: EmbeddingConfig,
) -> int:
    """Split chapter text, embed, add to FAISS. Returns chunk count."""
    text_chunks = split_into_chunks(chapter_text, chapter_num=chapter_num)
    if not text_chunks:
        return 0

    adapter = create_embedding_adapter(embedding_config)
    texts = [tc.text for tc in text_chunks]
    embeddings = await adapter.embed_documents(texts)

    store_dir = workspace.root / "vectorstore"
    engine = FaissEngine.load(store_dir) if (store_dir / "metadata.jsonl").exists() else FaissEngine(store_dir)

    engine.delete_by_chapter(chapter_num)

    chunks = [
        Chunk(
            text=tc.text,
            chapter_num=tc.chapter_num,
            scene_id=tc.scene_id,
            role=tc.role,
            embedding=emb,
        )
        for tc, emb in zip(text_chunks, embeddings)
    ]
    engine.add_chunks(chunks)
    engine.save()

    return len(chunks)


async def finalize_chapter(
    workspace: ProjectWorkspace,
    chapter_num: int,
    chapter_text: str,
    llm_config: LLMConfig,
    embedding_config: EmbeddingConfig,
) -> dict:
    """Run all three finalization steps. Write journal event. Returns status dict."""
    summary = await update_global_summary(workspace, chapter_num, chapter_text, llm_config)
    state = await update_character_state(workspace, chapter_num, chapter_text, llm_config)
    chunk_count = await ingest_chapter(workspace, chapter_num, chapter_text, embedding_config)

    workspace.append_journal({
        "type": "chapter.finalized",
        "chapter_num": chapter_num,
        "chunk_count": chunk_count,
    })

    return {
        "chapter_num": chapter_num,
        "summary_length": len(summary),
        "state_length": len(state),
        "chunk_count": chunk_count,
    }
