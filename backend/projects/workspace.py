"""Project directory structure management and safe file I/O."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


_SUBDIRS = (
    "bible/characters",
    "bible/worldbuilding",
    "bible/plot",
    "plans",
    "chapters",
    "reviews",
    "vectorstore",
)

_UNSAFE_PATH = re.compile(r"(^|[\\/])\.\.($|[\\/])")


class ProjectWorkspace:
    def __init__(self, projects_dir: Path, project_name: str) -> None:
        self._root = projects_dir / project_name
        self._name = project_name

    @property
    def root(self) -> Path:
        return self._root

    @property
    def name(self) -> str:
        return self._name

    def ensure(self) -> None:
        """Create all required subdirectories if they don't exist."""
        for subdir in _SUBDIRS:
            (self._root / subdir).mkdir(parents=True, exist_ok=True)

    def _validate_path(self, relative_path: str) -> Path:
        if _UNSAFE_PATH.search(relative_path):
            raise ValueError(f"Path traversal not allowed: {relative_path}")
        target = self._root / relative_path
        if not str(target.resolve()).startswith(str(self._root.resolve())):
            raise ValueError(f"Path escapes project root: {relative_path}")
        return target

    def read_file(self, relative_path: str) -> str:
        """Read a file relative to project root. Returns empty string if not found."""
        path = self._validate_path(relative_path)
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def write_file(self, relative_path: str, content: str) -> Path:
        """Write content to file, creating parent dirs as needed."""
        path = self._validate_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def append_journal(self, event: dict) -> None:
        """Append a JSON event to journal.jsonl with timestamp."""
        journal_path = self._root / "journal.jsonl"
        entry = {**event, "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds")}
        with journal_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def list_files(self, subdir: str) -> list[str]:
        """Recursively list all files under a subdirectory, returning relative paths."""
        base = self._validate_path(subdir)
        if not base.is_dir():
            return []
        results: list[str] = []
        for p in sorted(base.rglob("*")):
            if p.is_file():
                results.append(str(p.relative_to(self._root)))
        return results

    def delete_file(self, relative_path: str) -> bool:
        """Delete a file. Returns True if file existed and was removed."""
        path = self._validate_path(relative_path)
        if not path.is_file():
            return False
        path.unlink()
        return True

    def list_chapters(self) -> list[int]:
        """Return sorted list of existing chapter numbers."""
        chapters_dir = self._root / "chapters"
        if not chapters_dir.is_dir():
            return []
        nums: list[int] = []
        for p in chapters_dir.iterdir():
            m = re.match(r"^ch(\d+)\.", p.name)
            if m:
                nums.append(int(m.group(1)))
        return sorted(nums)

    def list_planned_chapters(self) -> list[int]:
        """Return sorted list of chapter numbers that have plans but no chapter file."""
        plans_dir = self._root / "plans"
        if not plans_dir.is_dir():
            return []
        written = set(self.list_chapters())
        nums: list[int] = []
        for p in plans_dir.iterdir():
            m = re.match(r"^ch(\d+)-plan\.", p.name)
            if m:
                n = int(m.group(1))
                if n not in written:
                    nums.append(n)
        return sorted(nums)

    def chapter_path(self, chapter_num: int) -> Path:
        return self._root / "chapters" / f"ch{chapter_num:02d}.md"

    def plan_path(self, chapter_num: int) -> Path:
        return self._root / "plans" / f"ch{chapter_num:02d}-plan.md"

    def review_path(self, chapter_num: int) -> Path:
        return self._root / "reviews" / f"ch{chapter_num:02d}-review.md"


def ensure_project(projects_dir: Path, name: str) -> ProjectWorkspace:
    """Create workspace and ensure directories exist."""
    ws = ProjectWorkspace(projects_dir, name)
    ws.ensure()
    return ws


def list_projects(projects_dir: Path) -> list[str]:
    """List all project names in projects_dir."""
    if not projects_dir.is_dir():
        return []
    return sorted(
        p.name for p in projects_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    )
