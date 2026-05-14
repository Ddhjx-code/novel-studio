"""Tests for FAISS engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.vectorstore.engine import Chunk, FaissEngine


def _make_chunks(chapter_num: int, count: int, dim: int = 4) -> list[Chunk]:
    chunks = []
    for i in range(count):
        emb = [float(i + chapter_num * 100 + d) for d in range(dim)]
        chunks.append(Chunk(
            text=f"ch{chapter_num} chunk {i}",
            chapter_num=chapter_num,
            scene_id=f"s{i}",
            role="narrative",
            embedding=emb,
        ))
    return chunks


class TestFaissEngine:
    def test_add_chunks_increases_size(self, tmp_path: Path):
        engine = FaissEngine(tmp_path)
        assert engine.size == 0
        engine.add_chunks(_make_chunks(1, 5))
        assert engine.size == 5

    def test_search_returns_results(self, tmp_path: Path):
        engine = FaissEngine(tmp_path)
        engine.add_chunks(_make_chunks(1, 10))
        query = [0.0, 0.0, 0.0, 0.0]
        results = engine.search(query, top_k=3)
        assert len(results) == 3

    def test_search_empty_returns_empty(self, tmp_path: Path):
        engine = FaissEngine(tmp_path)
        results = engine.search([1.0, 2.0, 3.0, 4.0], top_k=5)
        assert results == []

    def test_chapter_filter_excludes(self, tmp_path: Path):
        engine = FaissEngine(tmp_path)
        engine.add_chunks(_make_chunks(1, 5))
        engine.add_chunks(_make_chunks(2, 5))
        query = [100.0, 100.0, 100.0, 100.0]
        results = engine.search(query, top_k=10, chapter_filter=1)
        assert all(c.chapter_num != 1 for c in results)

    def test_delete_by_chapter(self, tmp_path: Path):
        engine = FaissEngine(tmp_path)
        engine.add_chunks(_make_chunks(1, 3))
        engine.add_chunks(_make_chunks(2, 4))
        assert engine.size == 7
        deleted = engine.delete_by_chapter(1)
        assert deleted == 3
        assert engine.size == 4

    def test_delete_nonexistent_chapter(self, tmp_path: Path):
        engine = FaissEngine(tmp_path)
        engine.add_chunks(_make_chunks(1, 3))
        deleted = engine.delete_by_chapter(99)
        assert deleted == 0
        assert engine.size == 3

    def test_save_load_roundtrip(self, tmp_path: Path):
        engine = FaissEngine(tmp_path)
        chunks = _make_chunks(1, 5)
        engine.add_chunks(chunks)
        engine.save()

        loaded = FaissEngine.load(tmp_path)
        assert loaded.size == 5
        assert loaded.dimension == 4
        assert loaded._chunks[0].text == "ch1 chunk 0"
        assert loaded._chunks[0].chapter_num == 1

        results = loaded.search([0.0, 0.0, 0.0, 0.0], top_k=2)
        assert len(results) == 2

    def test_dimension_mismatch_raises(self, tmp_path: Path):
        engine = FaissEngine(tmp_path)
        engine.add_chunks(_make_chunks(1, 3, dim=4))
        bad_chunks = [Chunk(text="x", chapter_num=2, embedding=[1.0, 2.0])]
        with pytest.raises(ValueError, match="dimension mismatch"):
            engine.add_chunks(bad_chunks)

    def test_auto_detects_dimension(self, tmp_path: Path):
        engine = FaissEngine(tmp_path)
        assert engine.dimension == 0
        engine.add_chunks(_make_chunks(1, 2, dim=8))
        assert engine.dimension == 8
