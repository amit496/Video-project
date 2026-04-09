"""Per-headline illustrative images via OpenAI Images API (no Pexels). Safe prompts: no real-person likeness."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import base64

import requests
from openai import OpenAI

from . import config

logger = logging.getLogger(__name__)

LOG_NAME = "ai_image_license_log.jsonl"


def _prompt_for_headline(headline: str) -> str:
    h = (headline or "world news")[:300]
    return (
        "Create a single cinematic news-style illustration for a TV broadcast. "
        "Topic context (do not render readable newspaper text): "
        f"{h}. "
        "Style: photorealistic broadcast B-roll, no logos, no watermarks, no text overlays. "
        "Do not depict any specific real politician or celebrity by likeness; use generic figures or places only."
    )


def generate_story_images(
    titles: list[str],
    out_dir: Path,
    max_stories: int = 10,
    story_indices_1based: list[int] | None = None,
) -> list[Path]:
    """Returns paths like 01_ai_news.png ... staged for story mapping.

    If story_indices_1based is set, must match len(titles); files use those indices (e.g. 3 -> 03_ai_news.png).
    """
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY required for AI story images")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    model = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
    size = os.getenv("OPENAI_IMAGE_SIZE", "1792x1024")

    saved: list[Path] = []
    log_path = out_dir / LOG_NAME

    pairs: list[tuple[int, str]] = []
    for j, title in enumerate(titles[:max_stories]):
        if story_indices_1based is not None:
            if j >= len(story_indices_1based):
                break
            idx = story_indices_1based[j]
        else:
            idx = j + 1
        pairs.append((idx, title))

    for i, title in pairs:
        prompt = _prompt_for_headline(title)
        try:
            resp = client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                quality=os.getenv("OPENAI_IMAGE_QUALITY", "standard"),
                n=1,
                response_format="b64_json",
            )
            b64 = resp.data[0].b64_json
            if b64:
                raw = base64.b64decode(b64)
            else:
                raise RuntimeError("empty b64")
        except Exception:
            try:
                resp = client.images.generate(
                    model=model,
                    prompt=prompt,
                    size=size,
                    quality=os.getenv("OPENAI_IMAGE_QUALITY", "standard"),
                    n=1,
                )
                url = getattr(resp.data[0], "url", None)
                if not url:
                    raise RuntimeError("no image url")
                raw = requests.get(url, timeout=120).content
            except Exception as e:
                logger.warning("OpenAI image failed for story %s: %s", i, e)
                continue

        dest = out_dir / f"{i:02d}_ai_news.png"
        dest.write_bytes(raw)
        saved.append(dest)
        entry = {
            "provider": "openai_images",
            "model": model,
            "size": size,
            "story_index": i,
            "headline": title[:200],
            "prompt_excerpt": prompt[:400],
            "file": dest.name,
            "license_note": "Subject to OpenAI terms and your commercial use policy.",
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("AI story image %s", dest.name)

    return saved
