"""1280×720 YouTube thumbnail: headline + optional anchor inset (Pillow only)."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

SIZE = (1280, 720)
_FONT_CANDIDATES_TITLE = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]
_FONT_CANDIDATES_SUB = [
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


def _wrap_lines(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw, max_lines: int) -> list[str]:
    words = (text or "World News").replace("\n", " ").split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        test = " ".join(cur + [w])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
            if len(lines) >= max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(" ".join(cur))
    if not lines:
        lines = [text[:60]]
    return lines[:max_lines]


def build_youtube_thumbnail(
    headline: str,
    out_path: Path,
    anchor_path: Path | None = None,
    subline: str | None = None,
) -> Path:
    w, h = SIZE
    base = Image.new("RGB", SIZE, (18, 20, 35))
    draw = ImageDraw.Draw(base)
    for y in range(h):
        t = y / h
        r = int(18 + t * 40)
        g = int(20 + t * 35)
        b = int(35 + t * 50)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    font_title = _load_font(_FONT_CANDIDATES_TITLE, 52)
    font_sub = _load_font(_FONT_CANDIDATES_SUB, 30)
    margin = 48
    text_w = w - 2 * margin
    if anchor_path and Path(anchor_path).is_file():
        text_w = int(w * 0.58)

    title_lines = _wrap_lines(headline[:200], font_title, text_w, draw, max_lines=3)
    y0 = 80
    for line in title_lines:
        draw.text((margin, y0), line, fill=(255, 255, 255), font=font_title)
        bbox = draw.textbbox((0, 0), line, font=font_title)
        y0 += bbox[3] - bbox[1] + 12

    if subline:
        y0 += 8
        for line in _wrap_lines(subline[:120], font_sub, text_w, draw, max_lines=2):
            draw.text((margin, y0), line, fill=(200, 210, 230), font=font_sub)
            bbox = draw.textbbox((0, 0), line, font=font_sub)
            y0 += bbox[3] - bbox[1] + 6

    draw.text((margin, h - 56), "WORLD NEWS", fill=(255, 180, 60), font=font_sub)

    if anchor_path and Path(anchor_path).is_file():
        try:
            ac = Image.open(anchor_path).convert("RGB")
            ah = min(500, int(h * 0.7))
            aw = max(1, int(ac.width * (ah / ac.height)))
            ac = ac.resize((aw, ah), Image.Resampling.LANCZOS)
            ax, ay = w - aw - 40, (h - ah) // 2
            draw.rectangle([ax - 4, ay - 4, ax + aw + 3, ay + ah + 3], outline=(255, 190, 70), width=4)
            base.paste(ac, (ax, ay))
        except Exception as e:
            logger.warning("Anchor inset skipped: %s", e)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    base.save(out_path, "JPEG", quality=92, optimize=True)
    return out_path
