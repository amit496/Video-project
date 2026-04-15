"""Generate story-wise fallback visuals and short clips without external APIs.

This module creates:
- one prompt text file per story for future AI/local generators
- one headline/summary image per story
- one short mp4 clip per story from that image

The output naming follows the existing story mapping convention:
- 01_story_card.png
- 01_story_clip.mp4
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from moviepy.editor import ImageClip
from PIL import Image, ImageDraw, ImageFont

from .news_fetcher import NewsItem

logger = logging.getLogger(__name__)

CANVAS = (1920, 1080)
_FONT_CANDIDATES_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
_FONT_CANDIDATES_REG = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _load_font(candidates: list[str], size: int) -> ImageFont.ImageFont:
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _clean_text(text: str, limit: int = 260) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    short = text[:limit].rsplit(" ", 1)[0].strip()
    return (short or text[:limit]).rstrip(" ,.;:") + "."


def _wrap_lines(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw, max_lines: int) -> list[str]:
    words = (text or "").replace("\n", " ").split()
    lines: list[str] = []
    cur: list[str] = []
    for word in words:
        test = " ".join(cur + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            cur.append(word)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [word]
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(" ".join(cur))
    return lines[:max_lines] or [text[:80]]


def build_story_visual_prompt(item: NewsItem) -> str:
    summary = _clean_text(item.summary, limit=220)
    return (
        "Create a cinematic world-news visual for broadcast use. "
        f"Headline: {item.title}. "
        f"Context: {summary}. "
        "Style: realistic newsroom b-roll, dramatic lighting, global news mood, "
        "no channel logos, no watermark, no readable text, 16:9 frame. "
        "Avoid exact likeness of real politicians or celebrities unless licensed."
    )


def _render_story_card(item: NewsItem, out_path: Path, story_index: int) -> Path:
    w, h = CANVAS
    img = Image.new("RGB", CANVAS, (10, 16, 28))
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / max(h - 1, 1)
        draw.line(
            [(0, y), (w, y)],
            fill=(int(10 + 30 * t), int(16 + 24 * t), int(28 + 60 * t)),
        )

    draw.rounded_rectangle((90, 80, w - 90, h - 80), radius=40, outline=(255, 190, 60), width=4)
    draw.rounded_rectangle((120, 120, w - 120, h - 120), radius=30, fill=(12, 20, 36))

    font_kicker = _load_font(_FONT_CANDIDATES_BOLD, 34)
    font_title = _load_font(_FONT_CANDIDATES_BOLD, 62)
    font_body = _load_font(_FONT_CANDIDATES_REG, 34)
    font_small = _load_font(_FONT_CANDIDATES_REG, 28)

    draw.text((170, 165), f"TOP STORY {story_index:02d}", fill=(255, 184, 62), font=font_kicker)
    draw.text((170, 220), "WORLD NEWS UPDATE", fill=(180, 205, 235), font=font_small)

    y = 300
    title_max_w = w - 340
    for line in _wrap_lines(item.title[:220], font_title, title_max_w, draw, max_lines=3):
        draw.text((170, y), line, fill=(255, 255, 255), font=font_title)
        bbox = draw.textbbox((0, 0), line, font=font_title)
        y += bbox[3] - bbox[1] + 16

    y += 30
    for line in _wrap_lines(_clean_text(item.summary), font_body, title_max_w, draw, max_lines=6):
        draw.text((170, y), line, fill=(208, 220, 235), font=font_body)
        bbox = draw.textbbox((0, 0), line, font=font_body)
        y += bbox[3] - bbox[1] + 12

    footer = item.published or "Latest available update"
    draw.text((170, h - 180), f"Context: {footer}", fill=(160, 180, 200), font=font_small)
    draw.text((170, h - 130), "AUTO-GENERATED STORY VISUAL", fill=(255, 184, 62), font=font_small)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def _render_story_clip(image_path: Path, out_path: Path, duration: float = 4.0, fps: int = 24) -> Path:
    clip = ImageClip(str(image_path)).set_duration(duration)
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


def generate_story_media(
    items: list[NewsItem],
    out_dir: Path,
    clip_duration: float = 4.0,
    story_indices_1based: list[int] | None = None,
) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "story_media_manifest.jsonl"
    produced: list[Path] = []

    for pos, item in enumerate(items, 1):
        idx = story_indices_1based[pos - 1] if story_indices_1based and pos - 1 < len(story_indices_1based) else pos
        prompt = build_story_visual_prompt(item)
        prompt_path = out_dir / f"{idx:02d}_story_prompt.txt"
        image_path = out_dir / f"{idx:02d}_story_card.png"
        clip_path = out_dir / f"{idx:02d}_story_clip.mp4"

        prompt_path.write_text(prompt, encoding="utf-8")
        _render_story_card(item, image_path, idx)
        produced.append(image_path)

        try:
            _render_story_clip(image_path, clip_path, duration=clip_duration)
            produced.append(clip_path)
        except Exception as e:
            logger.warning("Story clip render failed for story %s: %s", idx, e)

        entry = {
            "story_index": idx,
            "title": item.title,
            "prompt_file": prompt_path.name,
            "image_file": image_path.name,
            "clip_file": clip_path.name if clip_path.exists() else None,
            "source_link": item.link,
            "published": item.published,
        }
        with manifest_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return produced
