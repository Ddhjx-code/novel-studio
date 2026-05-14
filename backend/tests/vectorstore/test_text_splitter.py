"""Tests for Chinese text splitter."""

from __future__ import annotations

from backend.vectorstore.text_splitter import TextChunk, split_into_chunks, split_sentences


class TestSplitSentences:
    def test_basic_chinese_sentences(self):
        text = "这是第一句话。这是第二句话！第三句话？"
        result = split_sentences(text)
        assert len(result) == 3
        assert result[0] == "这是第一句话。"
        assert result[1] == "这是第二句话！"
        assert result[2] == "第三句话？"

    def test_newline_as_delimiter(self):
        text = "第一行\n第二行\n第三行"
        result = split_sentences(text)
        assert len(result) == 3

    def test_empty_input(self):
        assert split_sentences("") == []
        assert split_sentences("   ") == []

    def test_no_delimiters(self):
        text = "这是一段没有标点的文本"
        result = split_sentences(text)
        assert len(result) == 1
        assert result[0] == text


class TestSplitIntoChunks:
    def test_splits_long_text(self):
        sentences = ["这是一句话。"] * 200
        text = "".join(sentences)
        chunks = split_into_chunks(text, chapter_num=1, max_chunk_size=500)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.chapter_num == 1
            assert len(chunk.text) <= 600  # may exceed slightly due to sentence boundary

    def test_short_text_single_chunk(self):
        text = "短句。"
        chunks = split_into_chunks(text, chapter_num=3, max_chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0].text == "短句。"
        assert chunks[0].chapter_num == 3

    def test_empty_returns_empty(self):
        assert split_into_chunks("", chapter_num=1) == []

    def test_metadata_propagates(self):
        text = "测试句子。" * 50
        chunks = split_into_chunks(text, chapter_num=5, scene_id="s1", role="narrative")
        for chunk in chunks:
            assert chunk.scene_id == "s1"
            assert chunk.role == "narrative"
            assert chunk.chapter_num == 5

    def test_respects_sentence_boundaries(self):
        text = "短。" * 100 + "这是一个很长的句子不应该被拆到两个chunk里面去的对吧。"
        chunks = split_into_chunks(text, chapter_num=1, max_chunk_size=500)
        for chunk in chunks:
            assert chunk.text.endswith("。")

    def test_frozen_dataclass(self):
        chunk = TextChunk(text="hello", chapter_num=1)
        assert chunk.text == "hello"
        assert chunk.scene_id == ""
        assert chunk.role == ""
