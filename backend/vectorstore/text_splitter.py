"""Chinese-aware text splitting into ~500-char chunks with metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    text: str
    chapter_num: int
    scene_id: str = ""
    role: str = ""


def split_sentences(text: str) -> list[str]:
    """Split Chinese text by sentence-ending punctuation, preserving delimiters."""
    if not text:
        return []
    parts = re.split(r"(?<=[。！？\n])", text)
    return [p for p in parts if p.strip()]


def split_into_chunks(
    text: str,
    chapter_num: int,
    max_chunk_size: int = 500,
    scene_id: str = "",
    role: str = "",
) -> list[TextChunk]:
    """Accumulate sentences until threshold, then flush to a new chunk."""
    sentences = split_sentences(text)
    if not sentences:
        return []

    chunks: list[TextChunk] = []
    buffer: list[str] = []
    buffer_len = 0

    for sentence in sentences:
        if buffer and buffer_len + len(sentence) > max_chunk_size:
            chunks.append(
                TextChunk(
                    text="".join(buffer),
                    chapter_num=chapter_num,
                    scene_id=scene_id,
                    role=role,
                )
            )
            buffer = []
            buffer_len = 0
        buffer.append(sentence)
        buffer_len += len(sentence)

    if buffer:
        chunks.append(
            TextChunk(
                text="".join(buffer),
                chapter_num=chapter_num,
                scene_id=scene_id,
                role=role,
            )
        )

    return chunks
