"""Stage daily media into a temp folder for consistent story mapping.

Goal: create files like 01_*.jpg, 02_*.mp4 in one folder (existing + downloaded).
We copy files (not symlink) for portability across Colab/Drive.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .media_sources import list_news_media


def stage_folder(src_folder: Path, dest_folder: Path) -> list[Path]:
    src_folder = Path(src_folder)
    dest_folder = Path(dest_folder)
    dest_folder.mkdir(parents=True, exist_ok=True)

    staged: list[Path] = []
    for p in list_news_media(src_folder):
        dest = dest_folder / p.name
        shutil.copy2(p, dest)
        staged.append(dest)
    return staged


def stage_extra_files(extra_files: list[Path], dest_folder: Path) -> list[Path]:
    dest_folder = Path(dest_folder)
    dest_folder.mkdir(parents=True, exist_ok=True)
    staged: list[Path] = []
    for p in extra_files:
        p = Path(p)
        dest = dest_folder / p.name
        shutil.copy2(p, dest)
        staged.append(dest)
    return staged

