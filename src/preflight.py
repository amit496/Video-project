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

    if config.BROLL_SOURCE not in config.VALID_BROLL_SOURCES:
        problems.append(
            f"Unsupported BROLL_SOURCE={config.BROLL_SOURCE!r}. Choose one of: {', '.join(sorted(config.VALID_BROLL_SOURCES))}."
        )
    if config.SCRIPT_PROVIDER not in config.VALID_SCRIPT_PROVIDERS:
        problems.append(
            f"Unsupported SCRIPT_PROVIDER={config.SCRIPT_PROVIDER!r}. Choose one of: {', '.join(sorted(config.VALID_SCRIPT_PROVIDERS))}."
        )
    if config.SEO_PROVIDER not in config.VALID_SEO_PROVIDERS:
        problems.append(
            f"Unsupported SEO_PROVIDER={config.SEO_PROVIDER!r}. Choose one of: {', '.join(sorted(config.VALID_SEO_PROVIDERS))}."
        )

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
    if config.SCRIPT_PROVIDER == "openai" and not config.OPENAI_API_KEY:
        problems.append("OPENAI_API_KEY missing in .env (needed because SCRIPT_PROVIDER=openai).")
    if config.SCRIPT_PROVIDER == "gemini" and not config.GEMINI_API_KEY:
        problems.append("GEMINI_API_KEY missing in .env (needed because SCRIPT_PROVIDER=gemini).")
    if config.BROLL_SOURCE == "runway" and not config.RUNWAY_API_KEY:
        problems.append("RUNWAY_API_KEY missing in .env (needed because BROLL_SOURCE=runway).")
    if (
        config.seo_llm_enabled()
        and config.SEO_PROVIDER == "openai"
        and not config.OPENAI_API_KEY
    ):
        problems.append("OPENAI_API_KEY missing in .env (needed because SEO LLM is enabled with SEO_PROVIDER=openai).")
    if (
        config.seo_llm_enabled()
        and config.SEO_PROVIDER == "gemini"
        and not config.GEMINI_API_KEY
    ):
        problems.append("GEMINI_API_KEY missing in .env (needed because SEO LLM is enabled with SEO_PROVIDER=gemini).")

    # YouTube OAuth (only required when uploading)
    if os.getenv("REQUIRE_YOUTUBE_OAUTH", "0").strip().lower() in ("1", "true", "yes", "on"):
        if not Path(config.YOUTUBE_CLIENT_SECRETS).is_file():
            problems.append(f"YouTube OAuth client secret missing: {config.YOUTUBE_CLIENT_SECRETS}")

    return PreflightResult(ok=(len(problems) == 0), problems=problems)

