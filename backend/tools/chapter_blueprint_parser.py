"""Parse the 7-field chapter blueprint format from planner output."""

from __future__ import annotations

import re


_CHAPTER_HEADER = re.compile(r"^第\s*(\d+)\s*章\s*-\s*\[?(.*?)\]?$")
_ROLE = re.compile(r"^本章定位：\s*\[?(.*)\]?$")
_PURPOSE = re.compile(r"^核心作用：\s*\[?(.*)\]?$")
_SUSPENSE = re.compile(r"^悬念密度：\s*\[?(.*)\]?$")
_FORESHADOW = re.compile(r"^伏笔操作：\s*\[?(.*)\]?$")
_TWIST = re.compile(r"^认知颠覆：\s*\[?(.*)\]?$")
_SUMMARY = re.compile(r"^本章简述：\s*\[?(.*)\]?$")


def _default_chapter(chapter_num: int) -> dict[str, object]:
    return {
        "chapter_number": chapter_num,
        "chapter_title": f"第{chapter_num}章",
        "chapter_role": "",
        "chapter_purpose": "",
        "suspense_level": "",
        "foreshadowing": "",
        "plot_twist_level": "",
        "chapter_summary": "",
    }


def parse_chapter_blueprint(text: str) -> list[dict[str, object]]:
    """Parse full blueprint text into list of chapter dicts."""
    if not text or not text.strip():
        return []

    chunks = re.split(r"\n\s*\n", text.strip())
    results: list[dict[str, object]] = []

    for chunk in chunks:
        lines = chunk.strip().splitlines()
        if not lines:
            continue

        header_match = _CHAPTER_HEADER.match(lines[0].strip())
        if not header_match:
            continue

        chapter_number = int(header_match.group(1))
        chapter_title = header_match.group(2).strip()

        chapter_role = ""
        chapter_purpose = ""
        suspense_level = ""
        foreshadowing = ""
        plot_twist_level = ""
        chapter_summary = ""

        for line in lines[1:]:
            stripped = line.strip()
            if not stripped:
                continue

            if m := _ROLE.match(stripped):
                chapter_role = m.group(1).strip()
            elif m := _PURPOSE.match(stripped):
                chapter_purpose = m.group(1).strip()
            elif m := _SUSPENSE.match(stripped):
                suspense_level = m.group(1).strip()
            elif m := _FORESHADOW.match(stripped):
                foreshadowing = m.group(1).strip()
            elif m := _TWIST.match(stripped):
                plot_twist_level = m.group(1).strip()
            elif m := _SUMMARY.match(stripped):
                chapter_summary = m.group(1).strip()

        results.append({
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "chapter_role": chapter_role,
            "chapter_purpose": chapter_purpose,
            "suspense_level": suspense_level,
            "foreshadowing": foreshadowing,
            "plot_twist_level": plot_twist_level,
            "chapter_summary": chapter_summary,
        })

    results.sort(key=lambda x: x["chapter_number"])  # type: ignore[arg-type]
    return results


def get_chapter_info(text: str, chapter_num: int) -> dict[str, object]:
    """Get single chapter info by number; returns default if not found."""
    all_chapters = parse_chapter_blueprint(text)
    for ch in all_chapters:
        if ch["chapter_number"] == chapter_num:
            return ch
    return _default_chapter(chapter_num)
