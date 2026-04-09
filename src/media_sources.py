"""Collect image/video files for daily B-roll.

Naming convention for story mapping (recommended):
- 01_*.jpg / 01_*.mp4  -> story 1 visuals
- 02_*.png             -> story 2 visuals
If no leading number is present, files go to the general pool.
"""

from __future__ import annotations

import re
from pathlib import Path

_MEDIA_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".mp4", ".webm", ".mov", ".mkv"}


def list_news_media(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file() or p.name.startswith("."):
            continue
        if p.suffix.lower() in _MEDIA_EXT:
            out.append(p)
    return out


_LEADING_INDEX_RE = re.compile(r"^\s*(\d{1,2})\s*[_\-\s\.]+")


def group_news_media_by_story(folder: Path, max_stories: int) -> tuple[list[list[Path]], list[Path]]:
    """Returns (story_media, general_pool).

    story_media is a list of length max_stories; story_media[i] is visuals for story i+1.
    """
    all_media = list_news_media(folder)
    story_media: list[list[Path]] = [[] for _ in range(max_stories)]
    general: list[Path] = []

    for p in all_media:
        m = _LEADING_INDEX_RE.match(p.stem)
        if not m:
            general.append(p)
            continue
        idx = int(m.group(1))
        if 1 <= idx <= max_stories:
            story_media[idx - 1].append(p)
        else:
            general.append(p)

    return story_media, general
