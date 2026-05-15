"""Tests for shared context helper functions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.orchestrator.context_helpers import load_bible_section, search_relevant_chunks
from backend.projects.workspace import ProjectWorkspace
from backend.vectorstore.embedding import EmbeddingConfig


@pytest.fixture
def workspace(tmp_path: Path) -> ProjectWorkspace:
    ws = ProjectWorkspace(tmp_path, "test-novel")
    ws.ensure()
    return ws


class TestLoadBibleSection:
    def test_empty_directory(self, workspace):
        result = load_bible_section(workspace, "bible/characters")
        assert result == ""

    def test_loads_single_file(self, workspace):
        workspace.write_file("bible/characters/hero.md", "名字：张三\n年龄：25")
        result = load_bible_section(workspace, "bible/characters")
        assert "## hero.md" in result
        assert "名字：张三" in result
        assert "年龄：25" in result

    def test_loads_multiple_files(self, workspace):
        workspace.write_file("bible/characters/hero.md", "主角设定")
        workspace.write_file("bible/characters/villain.md", "反派设定")
        result = load_bible_section(workspace, "bible/characters")
        assert "## hero.md" in result
        assert "## villain.md" in result
        assert "主角设定" in result
        assert "反派设定" in result

    def test_truncates_at_limit(self, workspace):
        long_content = "x" * 4000
        workspace.write_file("bible/worldbuilding/world1.md", long_content)
        workspace.write_file("bible/worldbuilding/world2.md", long_content)
        result = load_bible_section(workspace, "bible/worldbuilding")
        assert "已截断" in result
        assert len(result) <= 6200

    def test_nonexistent_directory(self, workspace):
        result = load_bible_section(workspace, "bible/nonexistent")
        assert result == ""

    def test_skips_empty_files(self, workspace):
        workspace.write_file("bible/plot/outline.md", "")
        workspace.write_file("bible/plot/notes.md", "有内容")
        result = load_bible_section(workspace, "bible/plot")
        assert "## outline.md" not in result
        assert "## notes.md" in result


class TestSearchRelevantChunks:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_vectorstore(self, workspace):
        config = EmbeddingConfig()
        result = await search_relevant_chunks(workspace, "query text", config, 1)
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_query(self, workspace):
        config = EmbeddingConfig()
        result = await search_relevant_chunks(workspace, "", config, 1)
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_empty_on_embedding_failure(self, workspace):
        store_dir = workspace.root / "vectorstore"
        store_dir.mkdir(parents=True, exist_ok=True)
        (store_dir / "metadata.jsonl").write_text("")

        config = EmbeddingConfig(base_url="http://invalid:9999", model="fake")
        result = await search_relevant_chunks(workspace, "query text", config, 1)
        assert result == ""

    @pytest.mark.asyncio
    async def test_formats_results_correctly(self, workspace):
        from backend.vectorstore.engine import Chunk, FaissEngine

        store_dir = workspace.root / "vectorstore"
        store_dir.mkdir(parents=True, exist_ok=True)

        chunks = [
            Chunk(text="第一章的内容片段", chapter_num=1, embedding=[0.1, 0.2, 0.3]),
            Chunk(text="第二章的内容片段", chapter_num=2, embedding=[0.4, 0.5, 0.6]),
        ]
        engine = FaissEngine(store_dir)
        engine.add_chunks(chunks)
        engine.save()

        fake_embedding = [0.1, 0.2, 0.3]

        with patch(
            "backend.orchestrator.context_helpers.create_embedding_adapter"
        ) as mock_adapter_factory:
            mock_adapter = AsyncMock()
            mock_adapter.embed_query.return_value = fake_embedding
            mock_adapter_factory.return_value = mock_adapter

            config = EmbeddingConfig()
            result = await search_relevant_chunks(workspace, "查询文本", config, 3)

        assert "[第1章]" in result
        assert "[第2章]" in result
        assert "第一章的内容片段" in result

    @pytest.mark.asyncio
    async def test_excludes_current_chapter(self, workspace):
        from backend.vectorstore.engine import Chunk, FaissEngine

        store_dir = workspace.root / "vectorstore"
        store_dir.mkdir(parents=True, exist_ok=True)

        chunks = [
            Chunk(text="第一章的内容", chapter_num=1, embedding=[0.1, 0.2, 0.3]),
            Chunk(text="第二章的内容", chapter_num=2, embedding=[0.1, 0.2, 0.3]),
        ]
        engine = FaissEngine(store_dir)
        engine.add_chunks(chunks)
        engine.save()

        with patch(
            "backend.orchestrator.context_helpers.create_embedding_adapter"
        ) as mock_adapter_factory:
            mock_adapter = AsyncMock()
            mock_adapter.embed_query.return_value = [0.1, 0.2, 0.3]
            mock_adapter_factory.return_value = mock_adapter

            config = EmbeddingConfig()
            result = await search_relevant_chunks(workspace, "query", config, exclude_chapter=2)

        assert "[第1章]" in result
        assert "[第2章]" not in result
