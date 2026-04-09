"""
Orchestrate: RSS → script (OpenAI) → Edge TTS → MoviePy video → optional YouTube upload.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .news_fetcher import collect_news, format_for_prompt
from .script_generator import generate_script
from .tts_edge import synthesize_to_file
from .media_sources import group_news_media_by_story, list_news_media
from .openai_story_images import generate_story_images
from .pexels_fetch import download_broll_for_titles
from .stage_daily_media import stage_extra_files, stage_folder
from .thumbnail_gen import build_youtube_thumbnail
from .seo_metadata import generate_seo_metadata
from .video_compose import build_video, get_anchor_image_path
from .youtube_upload import build_metadata_from_script, upload_video
from .preflight import run_preflight

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run(
    dry_run: bool = False,
    skip_upload: bool = False,
    privacy: str = "private",
    no_pexels: bool = False,
    no_seo_llm: bool = False,
    preflight_only: bool = False,
) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    temp_dir = config.TEMP_DIR / stamp
    temp_dir.mkdir(parents=True, exist_ok=True)

    pf = run_preflight()
    if not pf.ok:
        logger.error("Preflight failed:")
        for p in pf.problems:
            logger.error("- %s", p)
        sys.exit(2)
    logger.info("Preflight OK.")
    if preflight_only:
        return

    logger.info("Fetching news…")
    items = collect_news(max_total=10)
    if not items:
        logger.error("No news items — check RSS feeds / network.")
        sys.exit(1)

    blob = format_for_prompt(items)
    (temp_dir / "news_sources.txt").write_text(blob, encoding="utf-8")

    if dry_run:
        logger.info("Dry run: skipping script/TTS/video.")
        logger.info("Sample headline: %s", items[0].title)
        return

    logger.info("Generating script…")
    script = generate_script(blob)
    (temp_dir / "script.txt").write_text(script, encoding="utf-8")

    voice_path = temp_dir / "voice.mp3"
    logger.info("Synthesizing speech (edge-tts)…")
    synthesize_to_file(script, voice_path)

    titles = [i.title for i in items]
    media_paths = list_news_media(config.NEWS_MEDIA_DIR)

    # Stage media into temp so story mapping is consistent and Pexels can fill gaps.
    staged_dir = temp_dir / "staged_media"
    stage_folder(config.NEWS_MEDIA_DIR, staged_dir)

    story_n = min(10, len(titles))
    story_media, _general_pool = group_news_media_by_story(staged_dir, max_stories=story_n)
    missing = [i + 1 for i, bucket in enumerate(story_media) if not bucket]

    use_openai = config.BROLL_SOURCE == "openai"
    use_pexels = (
        config.BROLL_SOURCE == "pexels"
        and config.PEXELS_API_KEY
        and config.PEXELS_WHEN_EMPTY
        and not no_pexels
    )

    if use_openai:
        try:
            if not media_paths:
                logger.info("B-roll: generating unique images per headline (OpenAI, no Pexels)…")
                ai_paths = generate_story_images(titles, temp_dir / "ai_broll", max_stories=story_n)
                stage_extra_files(ai_paths, staged_dir)
            elif missing:
                logger.info("B-roll: filling missing stories with OpenAI images %s…", missing)
                miss_titles = [titles[i - 1] for i in missing if i - 1 < len(titles)]
                ai_paths = generate_story_images(
                    miss_titles,
                    temp_dir / "ai_broll_missing",
                    max_stories=len(missing),
                    story_indices_1based=missing,
                )
                stage_extra_files(ai_paths, staged_dir)
        except Exception as e:
            logger.warning("OpenAI story images failed (%s). Continue with local/empty media.", e)

    elif use_pexels:
        if not media_paths:
            logger.info("news_today/ empty — downloading B-roll from Pexels (headline-based)…")
            downloaded = download_broll_for_titles(titles, temp_dir / "pexels", config.PEXELS_API_KEY)
            stage_extra_files(downloaded, staged_dir)
        elif missing:
            logger.info("Some stories missing visuals (%s). Filling from Pexels…", missing)
            downloaded = download_broll_for_titles(
                [titles[i - 1] for i in missing if i - 1 < len(titles)],
                temp_dir / "pexels_missing",
                config.PEXELS_API_KEY,
                max_images=len(missing),
            )
            renamed: list[Path] = []
            for idx, src in zip(missing, downloaded):
                ext = Path(src).suffix.lower() or ".jpg"
                dest = (temp_dir / "pexels_missing") / f"{idx:02d}_pexels{ext}"
                if Path(src) != dest:
                    Path(src).replace(dest)
                renamed.append(dest)
            stage_extra_files(renamed, staged_dir)

    logger.info(
        "Anchor: %s | B-roll files: %d (folder %s)",
        config.ANCHOR_IMAGE_DIR,
        len(media_paths),
        config.NEWS_MEDIA_DIR,
    )
    out_video = config.OUTPUT_DIR / f"news_{stamp}.mp4"
    logger.info("Rendering video → %s", out_video)
    bg_music = config.pick_background_music()
    if bg_music:
        logger.info("Background music: %s", bg_music)

    build_video(
        voice_path,
        titles,
        out_video,
        news_media_dir=staged_dir,
        media_paths=None,
        music_path=bg_music,
    )

    if not no_seo_llm and config.OPENAI_API_KEY and (os.getenv("SEO_METADATA_USE_LLM", "1").strip().lower() in ("1", "true", "yes", "on")):
        try:
            seo = generate_seo_metadata(script, titles)
            meta_title, description, tags = seo.title, seo.description, seo.tags
            logger.info("SEO metadata: LLM generated title/description/tags.")
        except Exception as e:
            logger.warning("SEO LLM failed (%s). Falling back to template metadata.", e)
            meta_title, description, tags = build_metadata_from_script(script, titles)
    else:
        meta_title, description, tags = build_metadata_from_script(script, titles)

    thumb_path = temp_dir / "thumbnail.jpg"
    build_youtube_thumbnail(
        headline=meta_title,
        subline=(titles[1][:100] + "…") if len(titles) > 1 else None,
        out_path=thumb_path,
        anchor_path=get_anchor_image_path(),
    )
    logger.info("Thumbnail → %s", thumb_path)

    if skip_upload:
        logger.info("Skip upload. Video: %s | Thumbnail: %s", out_video, thumb_path)
        return

    logger.info("Uploading to YouTube (privacy=%s)…", privacy)
    vid = upload_video(
        out_video,
        title=meta_title,
        description=description,
        tags=tags,
        thumbnail_path=thumb_path,
        privacy_status=privacy,
    )
    logger.info("Done. Video ID: %s", vid)


def main() -> None:
    p = argparse.ArgumentParser(description="World news video pipeline")
    p.add_argument("--dry-run", action="store_true", help="Only fetch news, no LLM/TTS/video")
    p.add_argument("--preflight", action="store_true", help="Only run preflight checks and exit")
    p.add_argument("--skip-upload", action="store_true", help="Render video but do not upload")
    p.add_argument(
        "--privacy",
        default="private",
        choices=["private", "unlisted", "public"],
        help="YouTube visibility",
    )
    p.add_argument(
        "--no-pexels",
        action="store_true",
        help="Do not call Pexels (only if BROLL_SOURCE=pexels)",
    )
    p.add_argument(
        "--no-seo-llm",
        action="store_true",
        help="Do not use LLM for title/description/tags (use template)",
    )
    args = p.parse_args()
    run(
        dry_run=args.dry_run,
        skip_upload=args.skip_upload,
        privacy=args.privacy,
        no_pexels=args.no_pexels,
        no_seo_llm=args.no_seo_llm,
        preflight_only=args.preflight,
    )


if __name__ == "__main__":
    main()
