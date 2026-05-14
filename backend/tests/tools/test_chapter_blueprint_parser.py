"""Tests for chapter blueprint parser."""

from __future__ import annotations

from backend.tools.chapter_blueprint_parser import get_chapter_info, parse_chapter_blueprint

SAMPLE_BLUEPRINT = """\
第1章 - 紫极光下的预兆
本章定位：开篇引入
核心作用：建立世界观，引入主角
悬念密度：中等
伏笔操作：暗示古老预言
认知颠覆：低
本章简述：主角在一次异常天象中发现自己的特殊能力

第2章 - [暗流涌动]
本章定位：铺垫积累
核心作用：引入对手，深化主线冲突
悬念密度：高
伏笔操作：第一章预言的细节浮现
认知颠覆：中
本章简述：主角进入学院，遭遇第一个对手的试探

第3章 - 命运的裂缝
本章定位：转折推进
核心作用：打破安全感，推动角色成长
悬念密度：极高
伏笔操作：揭开家族秘密的一角
认知颠覆：高
本章简述：一场突发事件让主角不得不正视自己的身世之谜
"""


class TestParseChapterBlueprint:
    def test_parses_all_chapters(self):
        result = parse_chapter_blueprint(SAMPLE_BLUEPRINT)
        assert len(result) == 3

    def test_chapter_fields_correct(self):
        result = parse_chapter_blueprint(SAMPLE_BLUEPRINT)
        ch1 = result[0]
        assert ch1["chapter_number"] == 1
        assert ch1["chapter_title"] == "紫极光下的预兆"
        assert ch1["chapter_role"] == "开篇引入"
        assert ch1["chapter_purpose"] == "建立世界观，引入主角"
        assert ch1["suspense_level"] == "中等"
        assert ch1["foreshadowing"] == "暗示古老预言"
        assert ch1["plot_twist_level"] == "低"
        assert ch1["chapter_summary"] == "主角在一次异常天象中发现自己的特殊能力"

    def test_bracket_wrapped_title(self):
        result = parse_chapter_blueprint(SAMPLE_BLUEPRINT)
        ch2 = result[1]
        assert ch2["chapter_number"] == 2
        assert ch2["chapter_title"] == "暗流涌动"

    def test_sorted_by_chapter_number(self):
        result = parse_chapter_blueprint(SAMPLE_BLUEPRINT)
        numbers = [ch["chapter_number"] for ch in result]
        assert numbers == [1, 2, 3]

    def test_empty_input(self):
        assert parse_chapter_blueprint("") == []
        assert parse_chapter_blueprint("   ") == []

    def test_non_chapter_text_skipped(self):
        text = "这是一段随机文字\n没有章节格式"
        assert parse_chapter_blueprint(text) == []


class TestGetChapterInfo:
    def test_returns_correct_chapter(self):
        result = get_chapter_info(SAMPLE_BLUEPRINT, 2)
        assert result["chapter_number"] == 2
        assert result["chapter_title"] == "暗流涌动"

    def test_missing_chapter_returns_default(self):
        result = get_chapter_info(SAMPLE_BLUEPRINT, 99)
        assert result["chapter_number"] == 99
        assert result["chapter_title"] == "第99章"
        assert result["chapter_role"] == ""

    def test_empty_blueprint_returns_default(self):
        result = get_chapter_info("", 1)
        assert result["chapter_number"] == 1
