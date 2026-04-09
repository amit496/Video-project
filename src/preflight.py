"""Preflight checks before running (helps 'go live' reliability)."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass
class PreflightResult:
    ok: bool
    problems: list[str]


def run_preflight() -> PreflightResult:
    problems: list[str] = []

    # FFmpeg
    if not shutil.which("ffmpeg"):
        problems.append("FFmpeg not found in PATH (install ffmpeg).")

    # Anchor
    anchor_dir = config.ANCHOR_IMAGE_DIR
    anchor_files = []
    if anchor_dir.is_dir():
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            anchor_files += list(anchor_dir.glob(ext))
    if not anchor_files:
        problems.append(f"No anchor image found in {anchor_dir} (add 1.png etc).")

    # Keys
    if not config.OPENAI_API_KEY:
        problems.append("OPENAI_API_KEY missing in .env (needed for script + SEO metadata).")

    # YouTube OAuth (only required when uploading)
    if os.getenv("REQUIRE_YOUTUBE_OAUTH", "0").strip().lower() in ("1", "true", "yes", "on"):
        if not Path(config.YOUTUBE_CLIENT_SECRETS).is_file():
            problems.append(f"YouTube OAuth client secret missing: {config.YOUTUBE_CLIENT_SECRETS}")

    return PreflightResult(ok=(len(problems) == 0), problems=problems)

