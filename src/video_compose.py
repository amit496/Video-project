"""
News-style video: intro card → B-roll slideshow/clips (daily folder) + optional anchor picture-in-corner.
If news_today/ is empty, falls back to full-screen anchor (or placeholder).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

from . import config
from .media_sources import group_news_media_by_story, list_news_media
from .lipsync_anchor import generate_talking_anchor

logger = logging.getLogger(__name__)


def _first_anchor_image(folder: Path) -> Path | None:
    for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
        for p in sorted(folder.glob(ext)):
            if p.name.startswith("."):
                continue
            return p
    return None


def _title_card(text: str, duration: float, size: tuple[int, int]):
    w, h = size
    bg = ColorClip(size=size, color=(15, 18, 35)).set_duration(duration)
    try:
        txt = (
            TextClip(
                text[:220],
                fontsize=42,
                color="white",
                font="Arial-Bold",
                method="caption",
                size=(w - 100, None),
            )
            .set_duration(duration)
            .set_position("center")
        )
        return CompositeVideoClip([bg, txt])
    except Exception as e:
        logger.warning("TextClip unavailable (%s). Install ImageMagick for title cards.", e)
        return bg


def _cover_fill(clip, w: int, h: int):
    clip = clip.resize(height=h)
    if clip.w < w:
        clip = clip.resize(width=w)
    return clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=w, height=h)


def _broll_from_image(path: Path, seg_dur: float, w: int, h: int):
    ic = ImageClip(str(path)).set_duration(seg_dur)
    return _cover_fill(ic, w, h)


def _broll_from_video(path: Path, seg_dur: float, w: int, h: int):
    from moviepy.video.fx.all import loop

    v = VideoFileClip(str(path)).without_audio()
    if v.duration >= seg_dur:
        clip = v.subclip(0, seg_dur)
    else:
        clip = v.fx(loop, duration=seg_dur)
    return _cover_fill(clip, w, h)


def _broll_segment(path: Path, seg_dur: float, w: int, h: int):
    ext = path.suffix.lower()
    if ext in (".mp4", ".webm", ".mov", ".mkv"):
        return _broll_from_video(path, seg_dur, w, h)
    return _broll_from_image(path, seg_dur, w, h)


def _with_anchor_corner(broll: CompositeVideoClip | ImageClip, anchor_path: Path, w: int, h: int):
    d = float(broll.duration)
    scale = float(os.getenv("ANCHOR_CORNER_SCALE", "0.26"))
    pad = int(os.getenv("ANCHOR_CORNER_MARGIN", "20"))
    a = ImageClip(str(anchor_path)).set_duration(d)
    a = a.resize(height=int(h * scale))
    a = a.set_position((w - a.w - pad, h - a.h - pad))
    return CompositeVideoClip([broll, a])


def _with_talking_anchor_corner(broll, anchor_video_path: Path, w: int, h: int):
    d = float(broll.duration)
    scale = float(os.getenv("ANCHOR_CORNER_SCALE", "0.30"))
    pad = int(os.getenv("ANCHOR_CORNER_MARGIN", "20"))
    av_src = VideoFileClip(str(anchor_video_path))
    av = av_src.subclip(0, min(d, float(av_src.duration)))
    av = av.resize(height=int(h * scale)).set_duration(d)
    av = av.set_position((w - av.w - pad, h - av.h - pad))
    return CompositeVideoClip([broll, av])


def _main_from_broll(
    paths: list[Path],
    main_dur: float,
    size: tuple[int, int],
    anchor_path: Path | None,
) -> CompositeVideoClip:
    w, h = size
    n = len(paths)
    base_seg = max(main_dur / n, 0.04)
    segments: list = []
    used = 0.0
    for i, p in enumerate(paths):
        if i == n - 1:
            seg = max(main_dur - used, 0.04)
        else:
            seg = base_seg
            used += seg
        br = _broll_segment(p, seg, w, h)
        if anchor_path:
            br = _with_anchor_corner(br, anchor_path, w, h)
        segments.append(br)
    return concatenate_videoclips(segments, method="compose")


def _main_from_story_media(
    story_titles: list[str],
    story_media: list[list[Path]],
    general_pool: list[Path],
    main_dur: float,
    size: tuple[int, int],
    anchor_path: Path | None,
    anchor_video_path: Path | None = None,
) -> CompositeVideoClip:
    w, h = size
    n = max(len(story_titles), 1)
    base_story_dur = max(main_dur / n, 0.04)
    used = 0.0
    story_clips: list = []

    for i, title in enumerate(story_titles):
        story_dur = max(main_dur - used, 0.04) if i == n - 1 else base_story_dur
        if i != n - 1:
            used += story_dur

        pool = list(story_media[i]) if i < len(story_media) else []
        if not pool:
            pool = list(general_pool)
        if not pool:
            # If absolutely no media, use a title card as segment
            seg = _title_card(title, story_dur, size)
            story_clips.append(seg)
            continue

        # Within a story segment, rotate through its pool
        m = len(pool)
        seg_each = max(story_dur / m, 0.04)
        seg_used = 0.0
        segments: list = []
        for j, p in enumerate(pool):
            d = max(story_dur - seg_used, 0.04) if j == m - 1 else seg_each
            if j != m - 1:
                seg_used += d
            br = _broll_segment(p, d, w, h)
            if anchor_video_path and Path(anchor_video_path).is_file():
                br = _with_talking_anchor_corner(br, anchor_video_path, w, h)
            elif anchor_path:
                br = _with_anchor_corner(br, anchor_path, w, h)
            segments.append(br)
        story_clip = concatenate_videoclips(segments, method="compose")
        story_clips.append(story_clip)

    return concatenate_videoclips(story_clips, method="compose")


def _main_anchor_only(anchor_path: Path | None, main_dur: float, size: tuple[int, int], anchor_dir: Path):
    w, h = size
    if anchor_path:
        img = ImageClip(str(anchor_path)).set_duration(main_dur)
        img = img.resize(height=int(h * 0.88))
        img = img.set_position("center")
        bg = ColorClip(size=size, color=(12, 14, 24)).set_duration(main_dur)
        return CompositeVideoClip([bg, img])
    logger.warning("No anchor image in %s — placeholder.", anchor_dir)
    return ColorClip(size=size, color=(28, 28, 38)).set_duration(main_dur)


def build_video(
    voice_audio: Path,
    news_titles: list[str],
    out_path: Path,
    anchor_dir: Path | None = None,
    news_media_dir: Path | None = None,
    media_paths: list[Path] | None = None,
    story_mode: bool = True,
    music_path: Path | None = None,
    size: tuple[int, int] = (1920, 1080),
    fps: int = 24,
) -> Path:
    voice_audio = Path(voice_audio)
    out_path = Path(out_path)
    anchor_dir = anchor_dir or config.ANCHOR_IMAGE_DIR
    w, h = size

    if media_paths is not None:
        paths = list(media_paths)
    else:
        folder = news_media_dir or config.NEWS_MEDIA_DIR
        paths = list_news_media(folder)

    voice = AudioFileClip(str(voice_audio))
    total_dur = float(voice.duration)

    intro_sec = min(6.0, total_dur * 0.08)
    main_dur = max(total_dur - intro_sec, 0.01)

    headline = "World News Today"
    if news_titles:
        headline = news_titles[0][:200]

    intro = _title_card(headline, intro_sec, size)
    anchor_path = _first_anchor_image(anchor_dir)
    talking_anchor = None
    if anchor_path:
        talking_anchor = generate_talking_anchor(anchor_path, voice_audio, config.TEMP_DIR / "talking_anchor")

    if paths:
        folder = news_media_dir or config.NEWS_MEDIA_DIR
        if story_mode:
            story_media, general_pool = group_news_media_by_story(folder, max_stories=min(10, len(news_titles) or 10))
            logger.info(
                "B-roll story-map: %d story buckets + %d general file(s).",
                len(story_media),
                len(general_pool),
            )
            main = _main_from_story_media(
                story_titles=(news_titles[: len(story_media)] if news_titles else ["World News"] * len(story_media)),
                story_media=story_media,
                general_pool=general_pool,
                main_dur=main_dur,
                size=size,
                anchor_path=anchor_path,
                anchor_video_path=talking_anchor,
            )
        else:
            logger.info("B-roll: %d file(s) from news media folder.", len(paths))
            main = _main_from_broll(paths, main_dur, size, anchor_path)
    else:
        logger.info("No files in news media folder — full-screen anchor mode.")
        main = _main_anchor_only(anchor_path, main_dur, size, anchor_dir)

    final = concatenate_videoclips([intro, main], method="compose")
    final = final.set_audio(voice)

    music_env = os.getenv("BACKGROUND_MUSIC", "").strip()
    music_file = music_path or (Path(music_env) if music_env else None)
    if music_file and Path(music_file).is_file():
        try:
            from moviepy.audio.fx.all import audio_loop

            vol = float(os.getenv("BACKGROUND_MUSIC_VOLUME", "0.12"))
            bg_music = AudioFileClip(str(music_file)).volumex(vol)
            if bg_music.duration < total_dur:
                bg_music = audio_loop(bg_music, duration=total_dur)
            else:
                bg_music = bg_music.subclip(0, total_dur)
            final = final.set_audio(CompositeAudioClip([final.audio, bg_music]))
        except Exception as e:
            logger.warning("Background music skipped: %s", e)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(out_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
    )
    final.close()
    voice.close()
    return out_path


def get_anchor_image_path(anchor_dir: Path | None = None) -> Path | None:
    return _first_anchor_image(anchor_dir or config.ANCHOR_IMAGE_DIR)
