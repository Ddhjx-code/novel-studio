"""Tests for prompt loader."""

from __future__ import annotations

import pytest

from backend.prompts import format_prompt, load_prompt


EXPECTED_PROMPTS = [
    "summary_prompt",
    "update_character_state_prompt",
    "knowledge_search_prompt",
    "knowledge_filter_prompt",
    "consistency_check_prompt",
]


class TestLoadPrompt:
    @pytest.mark.parametrize("name", EXPECTED_PROMPTS)
    def test_all_prompts_loadable(self, name):
        content = load_prompt(name)
        assert len(content) > 0

    def test_unknown_prompt_raises(self):
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_prompt")


class TestFormatPrompt:
    def test_substitutes_placeholders(self):
        result = format_prompt(
            "summary_prompt",
            chapter_text="本章内容",
            global_summary="之前的摘要",
        )
        assert "本章内容" in result
        assert "之前的摘要" in result

    def test_missing_placeholder_raises(self):
        with pytest.raises(KeyError):
            format_prompt("summary_prompt")
