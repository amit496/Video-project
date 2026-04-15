"""Fully local topic-driven image generation using Pillow only.

This is not a photoreal diffusion model. The purpose is:
- no paid API
- no online dependency
- one unique visual per story
- visuals that are more dynamic than plain title cards

The generator builds a broadcast-style scene from the headline/summary:
- theme colors by topic
- layered gradients and light beams
- abstract skyline / map / alert motifs
- headline-guided composition
"""

from __future__ import annotations

import json
import logging
import math
import random
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .news_fetcher import NewsItem

logger = logging.getLogger(__name__)

SIZE = (1920, 1080)
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

TOPIC_THEMES: list[tuple[tuple[str, ...], dict[str, tuple[int, int, int]]]] = [
    (("war", "missile", "strike", "attack", "army", "military", "ceasefire", "border"), {"bg1": (22, 17, 28), "bg2": (110, 36, 24), "accent": (255, 117, 64), "soft": (255, 212, 140)}),
    (("storm", "flood", "rain", "earthquake", "cyclone", "fire", "weather", "wildfire"), {"bg1": (10, 24, 42), "bg2": (18, 90, 130), "accent": (96, 212, 255), "soft": (220, 248, 255)}),
    (("market", "economy", "bank", "trade", "tariff", "stocks", "inflation", "oil"), {"bg1": (10, 30, 24), "bg2": (24, 112, 70), "accent": (112, 255, 178), "soft": (216, 255, 235)}),
    (("election", "president", "minister", "government", "parliament", "policy", "vote"), {"bg1": (18, 24, 46), "bg2": (60, 78, 160), "accent": (255, 210, 72), "soft": (244, 240, 220)}),
    (("health", "virus", "hospital", "disease", "medical"), {"bg1": (12, 30, 42), "bg2": (22, 138, 150), "accent": (122, 248, 255), "soft": (225, 255, 255)}),
]
DEFAULT_THEME = {"bg1": (18, 24, 38), "bg2": (52, 72, 122), "accent": (255, 184, 60), "soft": (230, 240, 255)}


def _load_font(candidates: list[str], size: int) -> ImageFont.ImageFont:
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _clean_text(text: str, limit: int = 220) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].strip()
    return (cut or text[:limit]).rstrip(" ,.;:") + "."


def _seed_for_item(item: NewsItem, idx: int) -> int:
    base = f"{idx}|{item.title}|{item.summary}|{item.link}"
    return sum(ord(ch) for ch in base) % 10_000_019


def _pick_theme(text: str) -> dict[str, tuple[int, int, int]]:
    t = text.lower()
    for keywords, theme in TOPIC_THEMES:
        if any(k in t for k in keywords):
            return theme
    return DEFAULT_THEME


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


def _vertical_gradient(img: Image.Image, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for y in range(h):
        t = y / max(h - 1, 1)
        color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)


def _add_light_beams(layer: Image.Image, rng: random.Random, accent: tuple[int, int, int]) -> None:
    draw = ImageDraw.Draw(layer, "RGBA")
    w, h = layer.size
    for _ in range(8):
        x = rng.randint(-200, w + 200)
        top_w = rng.randint(40, 120)
        bottom_w = rng.randint(240, 460)
        opacity = rng.randint(18, 42)
        poly = [(x, 0), (x + top_w, 0), (x + bottom_w, h), (x - bottom_w, h)]
        draw.polygon(poly, fill=(*accent, opacity))


def _add_grid(layer: Image.Image, accent: tuple[int, int, int]) -> None:
    draw = ImageDraw.Draw(layer, "RGBA")
    w, h = layer.size
    for x in range(0, w, 90):
        draw.line([(x, int(h * 0.52)), (x, h)], fill=(*accent, 18), width=1)
    for y in range(int(h * 0.52), h, 52):
        draw.line([(0, y), (w, y)], fill=(*accent, 16), width=1)


def _add_globe_arc(layer: Image.Image, accent: tuple[int, int, int]) -> None:
    draw = ImageDraw.Draw(layer, "RGBA")
    w, h = layer.size
    box = (-240, int(h * 0.25), int(w * 0.65), int(h * 1.1))
    for offset in range(0, 180, 28):
        draw.arc(box, start=18 + offset, end=118 + offset, fill=(*accent, 70), width=3)
    for offset in range(0, 4):
        draw.arc((box[0] + 80 * offset, box[1], box[2] - 80 * offset, box[3]), start=28, end=150, fill=(*accent, 45), width=2)


def _add_cityline(layer: Image.Image, rng: random.Random, soft: tuple[int, int, int]) -> None:
    draw = ImageDraw.Draw(layer, "RGBA")
    w, h = layer.size
    x = 0
    baseline = int(h * 0.74)
    while x < w:
        bw = rng.randint(46, 120)
        bh = rng.randint(120, 360)
        draw.rectangle([x, baseline - bh, x + bw, baseline], fill=(*soft, rng.randint(18, 36)))
        x += bw + rng.randint(4, 22)


def _add_topic_symbol(layer: Image.Image, item: NewsItem, theme: dict[str, tuple[int, int, int]]) -> None:
    draw = ImageDraw.Draw(layer, "RGBA")
    w, h = layer.size
    title = item.title.lower()
    accent = theme["accent"]
    soft = theme["soft"]

    if any(k in title for k in ("war", "missile", "strike", "attack", "army", "military")):
        draw.polygon([(w - 520, 250), (w - 380, 330), (w - 540, 410)], fill=(*accent, 110))
        draw.rectangle([w - 720, 430, w - 400, 455], fill=(*soft, 95))
    elif any(k in title for k in ("storm", "flood", "rain", "cyclone", "weather")):
        for i in range(5):
            x = w - 520 + i * 52
            draw.ellipse([x, 250, x + 120, 330], fill=(*soft, 70))
        for i in range(9):
            x = w - 520 + i * 32
            draw.line([(x, 350), (x - 24, 430)], fill=(*accent, 120), width=5)
    elif any(k in title for k in ("market", "economy", "bank", "trade", "stocks", "inflation")):
        pts = [(w - 740, 620), (w - 660, 580), (w - 590, 600), (w - 510, 510), (w - 430, 470), (w - 340, 380)]
        draw.line(pts, fill=(*accent, 150), width=10)
        for px, py in pts:
            draw.ellipse([px - 10, py - 10, px + 10, py + 10], fill=(*soft, 180))
    else:
        draw.ellipse([w - 640, 180, w - 240, 580], outline=(*soft, 120), width=8)
        draw.arc([w - 620, 210, w - 260, 560], start=20, end=160, fill=(*accent, 140), width=8)
        draw.arc([w - 580, 250, w - 300, 520], start=210, end=340, fill=(*accent, 100), width=6)


def _add_noise(layer: Image.Image, rng: random.Random) -> None:
    draw = ImageDraw.Draw(layer, "RGBA")
    w, h = layer.size
    for _ in range(1800):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        alpha = rng.randint(8, 18)
        shade = rng.randint(160, 255)
        draw.point((x, y), fill=(shade, shade, shade, alpha))


def _render_local_ai_image(item: NewsItem, out_path: Path, idx: int) -> Path:
    rng = random.Random(_seed_for_item(item, idx))
    theme = _pick_theme(f"{item.title} {item.summary}")

    base = Image.new("RGB", SIZE, theme["bg1"])
    _vertical_gradient(base, theme["bg1"], theme["bg2"])

    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    _add_light_beams(overlay, rng, theme["accent"])
    _add_grid(overlay, theme["soft"])
    _add_globe_arc(overlay, theme["accent"])
    _add_cityline(overlay, rng, theme["soft"])
    _add_topic_symbol(overlay, item, theme)
    _add_noise(overlay, rng)

    glow = overlay.filter(ImageFilter.GaussianBlur(16))
    base = Image.alpha_composite(base.convert("RGBA"), glow)
    base = Image.alpha_composite(base, overlay)

    panel = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(panel, "RGBA")
    draw.rounded_rectangle((110, 120, 1120, 860), radius=42, fill=(6, 10, 18, 154), outline=(*theme["accent"], 90), width=3)
    draw.rounded_rectangle((110, 890, 740, 980), radius=26, fill=(0, 0, 0, 140))
    base = Image.alpha_composite(base, panel)

    draw = ImageDraw.Draw(base)
    kicker_font = _load_font(_FONT_CANDIDATES_BOLD, 34)
    title_font = _load_font(_FONT_CANDIDATES_BOLD, 64)
    body_font = _load_font(_FONT_CANDIDATES_REG, 32)
    small_font = _load_font(_FONT_CANDIDATES_REG, 28)

    draw.text((150, 160), f"AI NEWS VISUAL {idx:02d}", fill=theme["accent"], font=kicker_font)
    draw.text((150, 210), "GLOBAL UPDATE", fill=theme["soft"], font=small_font)

    y = 300
    max_w = 900
    for line in _wrap_lines(item.title[:220], title_font, max_w, draw, max_lines=3):
        draw.text((150, y), line, fill=(255, 255, 255), font=title_font)
        bbox = draw.textbbox((0, 0), line, font=title_font)
        y += bbox[3] - bbox[1] + 14

    y += 28
    summary = _clean_text(item.summary, limit=260)
    for line in _wrap_lines(summary, body_font, max_w, draw, max_lines=5):
        draw.text((150, y), line, fill=(220, 230, 240), font=body_font)
        bbox = draw.textbbox((0, 0), line, font=body_font)
        y += bbox[3] - bbox[1] + 12

    if item.published:
        draw.text((150, 915), item.published[:80], fill=(235, 235, 235), font=small_font)
    draw.text((150, 955), "AUTO LOCAL IMAGE GENERATION", fill=theme["accent"], font=small_font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(out_path, "PNG")
    return out_path


def generate_local_ai_story_images(
    items: list[NewsItem],
    out_dir: Path,
    story_indices_1based: list[int] | None = None,
) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "local_ai_images_manifest.jsonl"
    produced: list[Path] = []

    for pos, item in enumerate(items, 1):
        idx = story_indices_1based[pos - 1] if story_indices_1based and pos - 1 < len(story_indices_1based) else pos
        image_path = out_dir / f"{idx:02d}_local_ai.png"
        _render_local_ai_image(item, image_path, idx)
        produced.append(image_path)
        with manifest.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "story_index": idx,
                        "title": item.title,
                        "summary_excerpt": _clean_text(item.summary, 120),
                        "image_file": image_path.name,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    return produced
