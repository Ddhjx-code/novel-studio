"""Tests for chapter finalization."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.orchestrator.finalize import (
    LLMConfig,
    finalize_chapter,
    ingest_chapter,
    update_character_state,
    update_global_summary,
)
from backend.projects.workspace import ProjectWorkspace
from backend.vectorstore.embedding import EmbeddingConfig


@pytest.fixture
def workspace(tmp_path: Path) -> ProjectWorkspace:
    ws = ProjectWorkspace(tmp_path, "test-novel")
    ws.ensure()
    return ws


@pytest.fixture
def llm_config() -> LLMConfig:
    return LLMConfig(base_url="http://localhost:8000", model="test-model", api_key="test-key")


@pytest.fixture
def embedding_config() -> EmbeddingConfig:
    return EmbeddingConfig(base_url="http://localhost:8000", model="embed-model", api_key="k")


class TestUpdateGlobalSummary:
    @pytest.mark.asyncio
    async def test_updates_summary_file(self, workspace, llm_config):
        with patch(
            "backend.orchestrator.finalize._llm_complete",
            new_callable=AsyncMock,
            return_value="新的摘要内容",
        ):
            result = await update_global_summary(workspace, 1, "第一章正文", llm_config)

        assert result == "新的摘要内容"
        saved = workspace.read_file("bible/global_summary.md")
        assert saved == "新的摘要内容"

    @pytest.mark.asyncio
    async def test_passes_existing_summary(self, workspace, llm_config):
        workspace.write_file("bible/global_summary.md", "旧摘要")

        with patch(
            "backend.orchestrator.finalize._llm_complete",
            new_callable=AsyncMock,
            return_value="更新后的摘要",
        ) as mock_llm:
            await update_global_summary(workspace, 2, "第二章", llm_config)

        prompt_used = mock_llm.call_args[0][0]
        assert "旧摘要" in prompt_used


class TestUpdateCharacterState:
    @pytest.mark.asyncio
    async def test_updates_state_file(self, workspace, llm_config):
        with patch(
            "backend.orchestrator.finalize._llm_complete",
            new_callable=AsyncMock,
            return_value="角色A：状态更新",
        ):
            result = await update_character_state(workspace, 1, "正文", llm_config)

        assert result == "角色A：状态更新"
        saved = workspace.read_file("bible/character_state.md")
        assert saved == "角色A：状态更新"


class TestIngestChapter:
    @pytest.mark.asyncio
    async def test_ingests_and_saves(self, workspace, embedding_config):
        chapter_text = "这是一段测试文本。" * 50

        mock_adapter = AsyncMock()
        mock_adapter.embed_documents.return_value = [[0.1, 0.2, 0.3]] * 50

        with patch(
            "backend.orchestrator.finalize.create_embedding_adapter",
            return_value=mock_adapter,
        ):
            count = await ingest_chapter(workspace, 1, chapter_text, embedding_config)

        assert count > 0
        assert (workspace.root / "vectorstore" / "index.faiss").exists()
        assert (workspace.root / "vectorstore" / "metadata.jsonl").exists()

    @pytest.mark.asyncio
    async def test_empty_text_returns_zero(self, workspace, embedding_config):
        count = await ingest_chapter(workspace, 1, "", embedding_config)
        assert count == 0


class TestFinalizeChapter:
    @pytest.mark.asyncio
    async def test_runs_all_steps(self, workspace, llm_config, embedding_config):
        mock_adapter = AsyncMock()
        mock_adapter.embed_documents.return_value = [[0.1, 0.2, 0.3]]

        with (
            patch(
                "backend.orchestrator.finalize._llm_complete",
                new_callable=AsyncMock,
                return_value="LLM结果",
            ),
            patch(
                "backend.orchestrator.finalize.create_embedding_adapter",
                return_value=mock_adapter,
            ),
        ):
            result = await finalize_chapter(
                workspace, 1, "短文本。", llm_config, embedding_config
            )

        assert result["chapter_num"] == 1
        assert result["chunk_count"] >= 1
        assert result["summary_length"] > 0

        journal = workspace.root / "journal.jsonl"
        lines = journal.read_text().strip().splitlines()
        event = json.loads(lines[-1])
        assert event["type"] == "chapter.finalized"
        assert event["chapter_num"] == 1
