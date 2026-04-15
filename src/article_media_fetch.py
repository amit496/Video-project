"""Fetch story-related images from article pages and convert them to short clips.

This avoids paid media APIs by trying to reuse the article's preview image:
- og:image
- twitter:image
- link rel="image_src"

If a valid image is found, we download it and create a short mp4 clip from it.
"""

from __future__ import annotations

import json
import logging
import re
from html import unescape
from pathlib import Path
from urllib.parse import urljoin

import requests
from moviepy.editor import ImageClip

from .news_fetcher import NewsItem

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)
_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _fetch_html(url: str, timeout: int = 25) -> str:
    r = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    return r.text


def _extract_meta_image(html: str, base_url: str) -> str | None:
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, html, flags=re.IGNORECASE)
        if not m:
            continue
        raw = unescape(m.group(1)).strip()
        if not raw:
            continue
        return urljoin(base_url, raw)
    return None


def _guess_ext(url: str, content_type: str) -> str:
    lower = url.lower()
    for ext in _IMG_EXTS:
        if ext in lower:
            return ext
    ctype = (content_type or "").lower()
    if "png" in ctype:
        return ".png"
    if "webp" in ctype:
        return ".webp"
    return ".jpg"


def _download_image(url: str, dest: Path, timeout: int = 45) -> Path:
    r = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT}, stream=True)
    r.raise_for_status()
    ext = _guess_ext(url, r.headers.get("Content-Type", ""))
    final_dest = dest.with_suffix(ext)
    final_dest.parent.mkdir(parents=True, exist_ok=True)
    final_dest.write_bytes(r.content)
    return final_dest


def _render_clip(image_path: Path, out_path: Path, duration: float = 4.0, fps: int = 24) -> Path:
    clip = ImageClip(str(image_path)).resize(height=1080).set_duration(duration)
    if clip.w < 1920:
        clip = clip.resize(width=1920)
    clip = clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=1920, height=1080)
    clip = clip.fx(lambda c: c.resize(lambda t: 1 + 0.03 * min(t / max(duration, 0.1), 1.0)))
    clip.write_videofile(
        str(out_path),
        fps=fps,
        codec="libx264",
        audio=False,
        preset="medium",
        threads=2,
        logger=None,
    )
    clip.close()
    return out_path


def fetch_story_article_media(
    items: list[NewsItem],
    out_dir: Path,
    clip_duration: float = 4.0,
    story_indices_1based: list[int] | None = None,
) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "article_media_manifest.jsonl"
    produced: list[Path] = []

    for pos, item in enumerate(items, 1):
        idx = story_indices_1based[pos - 1] if story_indices_1based and pos - 1 < len(story_indices_1based) else pos
        if not item.link:
            continue
        try:
            html = _fetch_html(item.link)
            image_url = _extract_meta_image(html, item.link)
            if not image_url:
                logger.info("No article image found for story %s", idx)
                continue
            image_path = _download_image(image_url, out_dir / f"{idx:02d}_article_image")
            produced.append(image_path)

            clip_path = out_dir / f"{idx:02d}_article_clip.mp4"
            try:
                _render_clip(image_path, clip_path, duration=clip_duration)
                produced.append(clip_path)
            except Exception as e:
                logger.warning("Article clip render failed for story %s: %s", idx, e)

            with manifest.open("a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "story_index": idx,
                            "title": item.title,
                            "article_url": item.link,
                            "image_url": image_url,
                            "image_file": image_path.name,
                            "clip_file": clip_path.name if clip_path.exists() else None,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception as e:
            logger.warning("Article media fetch failed for story %s (%s): %s", idx, item.link, e)

    return produced
