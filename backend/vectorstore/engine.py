"""FAISS-based vector store with metadata persistence."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class Chunk:
    text: str
    chapter_num: int
    scene_id: str = ""
    role: str = ""
    embedding: list[float] = field(default_factory=list)


class FaissEngine:
    def __init__(self, store_dir: Path, dimension: int = 0) -> None:
        self._store_dir = store_dir
        self._dimension = dimension
        self._chunks: list[Chunk] = []
        self._index = None

    @property
    def size(self) -> int:
        return len(self._chunks)

    @property
    def dimension(self) -> int:
        return self._dimension

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """Add chunks with pre-computed embeddings to the index."""
        import faiss

        if not chunks:
            return

        vectors = np.array([c.embedding for c in chunks], dtype=np.float32)
        dim = vectors.shape[1]

        if self._dimension == 0:
            self._dimension = dim
            self._index = faiss.IndexFlatL2(dim)
        elif dim != self._dimension:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self._dimension}, got {dim}"
            )

        self._index.add(vectors)
        self._chunks.extend(chunks)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        chapter_filter: int | None = None,
    ) -> list[Chunk]:
        """Search for similar chunks. Optional chapter_filter excludes that chapter."""
        if self._index is None or self.size == 0:
            return []

        query = np.array([query_embedding], dtype=np.float32)
        fetch_k = top_k * 3 if chapter_filter is not None else top_k
        fetch_k = min(fetch_k, self.size)

        distances, indices = self._index.search(query, fetch_k)

        results: list[Chunk] = []
        for idx in indices[0]:
            if idx < 0 or idx >= len(self._chunks):
                continue
            chunk = self._chunks[idx]
            if chapter_filter is not None and chunk.chapter_num == chapter_filter:
                continue
            results.append(chunk)
            if len(results) >= top_k:
                break

        return results

    def delete_by_chapter(self, chapter_num: int) -> int:
        """Delete all chunks for a given chapter. Returns count deleted."""
        import faiss

        original_count = len(self._chunks)
        remaining = [c for c in self._chunks if c.chapter_num != chapter_num]
        deleted = original_count - len(remaining)

        if deleted == 0:
            return 0

        self._chunks = remaining
        if remaining:
            vectors = np.array([c.embedding for c in remaining], dtype=np.float32)
            self._index = faiss.IndexFlatL2(self._dimension)
            self._index.add(vectors)
        else:
            self._index = faiss.IndexFlatL2(self._dimension) if self._dimension > 0 else None

        return deleted

    def save(self) -> None:
        """Persist index.faiss + metadata.jsonl to store_dir."""
        import faiss

        self._store_dir.mkdir(parents=True, exist_ok=True)

        if self._index is not None:
            faiss.write_index(self._index, str(self._store_dir / "index.faiss"))

        meta_path = self._store_dir / "metadata.jsonl"
        with meta_path.open("w", encoding="utf-8") as f:
            for chunk in self._chunks:
                entry = {
                    "text": chunk.text,
                    "chapter_num": chunk.chapter_num,
                    "scene_id": chunk.scene_id,
                    "role": chunk.role,
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        dim_path = self._store_dir / "dimension.txt"
        dim_path.write_text(str(self._dimension))

    @classmethod
    def load(cls, store_dir: Path) -> FaissEngine:
        """Load existing index from disk."""
        import faiss

        dim_path = store_dir / "dimension.txt"
        dimension = int(dim_path.read_text().strip()) if dim_path.exists() else 0

        engine = cls(store_dir, dimension=dimension)

        meta_path = store_dir / "metadata.jsonl"
        if meta_path.exists():
            with meta_path.open(encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    engine._chunks.append(Chunk(
                        text=data["text"],
                        chapter_num=data["chapter_num"],
                        scene_id=data.get("scene_id", ""),
                        role=data.get("role", ""),
                    ))

        index_path = store_dir / "index.faiss"
        if index_path.exists():
            engine._index = faiss.read_index(str(index_path))
            if dimension == 0 and engine._index.d > 0:
                engine._dimension = engine._index.d
        elif dimension > 0:
            engine._index = faiss.IndexFlatL2(dimension)

        return engine
