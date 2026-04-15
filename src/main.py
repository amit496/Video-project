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
from .article_media_fetch import fetch_story_article_media
from .local_ai_image_gen import generate_local_ai_story_images
from .openai_story_images import generate_story_images
from .runway_media_gen import generate_story_media_with_runway
from .story_media_gen import generate_story_media
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

    # Stage media into temp so story mapping is consistent across generated sources.
    staged_dir = temp_dir / "staged_media"
    stage_folder(config.NEWS_MEDIA_DIR, staged_dir)

    story_n = min(10, len(titles))
    story_media, _general_pool = group_news_media_by_story(staged_dir, max_stories=story_n)
    missing = [i + 1 for i, bucket in enumerate(story_media) if not bucket]

    use_openai = config.BROLL_SOURCE == "openai"
    use_localai = config.BROLL_SOURCE == "localai"
    use_runway = config.BROLL_SOURCE == "runway"
    use_article = config.BROLL_SOURCE == "article"
    use_generated = config.BROLL_SOURCE == "generated"

    if use_localai:
        try:
            if not media_paths:
                logger.info("B-roll: generating fully local topic-driven images…")
                local_images = generate_local_ai_story_images(items[:story_n], temp_dir / "local_ai_broll")
                stage_extra_files(local_images, staged_dir)
            elif missing:
                logger.info("B-roll: filling missing stories with local generated images %s…", missing)
                miss_items = [items[i - 1] for i in missing if i - 1 < len(items)]
                local_images = generate_local_ai_story_images(
                    miss_items,
                    temp_dir / "local_ai_broll_missing",
                    story_indices_1based=missing,
                )
                stage_extra_files(local_images, staged_dir)
        except Exception as e:
            logger.warning("Local AI image generation failed (%s). Continue with local/article/generated media.", e)

    elif use_runway:
        try:
            if not media_paths:
                logger.info("B-roll: generating real AI images and clips with Runway…")
                runway_media = generate_story_media_with_runway(
                    items[:story_n],
                    temp_dir / "runway_broll",
                    api_key=config.RUNWAY_API_KEY,
                    image_model=os.getenv("RUNWAY_IMAGE_MODEL", "gen4_image"),
                    video_model=os.getenv("RUNWAY_VIDEO_MODEL", "gen4.5"),
                    ratio=os.getenv("RUNWAY_RATIO", "1280:720"),
                    duration=int(os.getenv("RUNWAY_DURATION_SEC", "5")),
                )
                if runway_media:
                    stage_extra_files(runway_media, staged_dir)
                else:
                    logger.info("Runway returned no media. Falling back to article/generated visuals…")
                    article_media = fetch_story_article_media(items[:story_n], temp_dir / "article_broll")
                    if article_media:
                        stage_extra_files(article_media, staged_dir)
                    else:
                        generated = generate_story_media(items[:story_n], temp_dir / "generated_broll")
                        stage_extra_files(generated, staged_dir)
            elif missing:
                logger.info("B-roll: filling missing stories with Runway %s…", missing)
                miss_items = [items[i - 1] for i in missing if i - 1 < len(items)]
                runway_media = generate_story_media_with_runway(
                    miss_items,
                    temp_dir / "runway_broll_missing",
                    api_key=config.RUNWAY_API_KEY,
                    image_model=os.getenv("RUNWAY_IMAGE_MODEL", "gen4_image"),
                    video_model=os.getenv("RUNWAY_VIDEO_MODEL", "gen4.5"),
                    ratio=os.getenv("RUNWAY_RATIO", "1280:720"),
                    duration=int(os.getenv("RUNWAY_DURATION_SEC", "5")),
                    story_indices_1based=missing,
                )
                if runway_media:
                    stage_extra_files(runway_media, staged_dir)
        except Exception as e:
            logger.warning("Runway story media failed (%s). Continue with article/generated/local media.", e)

    elif use_article:
        try:
            if not media_paths:
                logger.info("B-roll: fetching article images and clips from source pages…")
                article_media = fetch_story_article_media(items[:story_n], temp_dir / "article_broll")
                if article_media:
                    stage_extra_files(article_media, staged_dir)
                else:
                    logger.info("No article media found. Falling back to generated story visuals…")
                    generated = generate_story_media(items[:story_n], temp_dir / "generated_broll")
                    stage_extra_files(generated, staged_dir)
            elif missing:
                logger.info("B-roll: filling missing stories from article pages %s…", missing)
                miss_items = [items[i - 1] for i in missing if i - 1 < len(items)]
                article_media = fetch_story_article_media(
                    miss_items,
                    temp_dir / "article_broll_missing",
                    story_indices_1based=missing,
                )
                if article_media:
                    stage_extra_files(article_media, staged_dir)
                still_missing_media, _ = group_news_media_by_story(staged_dir, max_stories=story_n)
                still_missing = [i + 1 for i, bucket in enumerate(still_missing_media) if not bucket]
                if still_missing:
                    logger.info("Article pages still missing visuals %s. Filling with generated story visuals…", still_missing)
                    still_missing_items = [items[i - 1] for i in still_missing if i - 1 < len(items)]
                    generated = generate_story_media(
                        still_missing_items,
                        temp_dir / "generated_broll_missing",
                        story_indices_1based=still_missing,
                    )
                    stage_extra_files(generated, staged_dir)
        except Exception as e:
            logger.warning("Article story media failed (%s). Continue with generated/local media.", e)

    elif use_generated:
        try:
            if not media_paths:
                logger.info("B-roll: generating story-wise local visuals and short clips…")
                generated = generate_story_media(items[:story_n], temp_dir / "generated_broll")
                stage_extra_files(generated, staged_dir)
            elif missing:
                logger.info("B-roll: filling missing stories with generated visuals %s…", missing)
                miss_items = [items[i - 1] for i in missing if i - 1 < len(items)]
                generated = generate_story_media(
                    miss_items,
                    temp_dir / "generated_broll_missing",
                    story_indices_1based=missing,
                )
                stage_extra_files(generated, staged_dir)
        except Exception as e:
            logger.warning("Generated story visuals failed (%s). Continue with local/empty media.", e)

    elif use_openai:
        try:
            if not media_paths:
                logger.info("B-roll: generating unique images per headline (OpenAI)…")
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

    if not no_seo_llm and config.seo_llm_enabled() and config.has_seo_provider_credentials():
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
        "--no-seo-llm",
        action="store_true",
        help="Do not use LLM for title/description/tags (use template)",
    )
    args = p.parse_args()
    run(
        dry_run=args.dry_run,
        skip_upload=args.skip_upload,
        privacy=args.privacy,
        no_seo_llm=args.no_seo_llm,
        preflight_only=args.preflight,
    )


if __name__ == "__main__":
    main()
