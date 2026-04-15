"""Runway-backed story media generation.

Flow per story:
- Generate one cinematic image from the story prompt
- Turn that image into a short video clip
- Save outputs locally using existing story index naming

Docs used:
- Runway text/image generation and image-to-video APIs
- GET /v1/tasks/{id} polling flow
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import requests

from .news_fetcher import NewsItem
from .story_media_gen import build_story_visual_prompt

logger = logging.getLogger(__name__)

RUNWAY_BASE_URL = "https://api.dev.runwayml.com/v1"
RUNWAY_VERSION = "2024-11-06"


class RunwayError(RuntimeError):
    pass


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Runway-Version": RUNWAY_VERSION,
    }


def _create_task(api_key: str, endpoint: str, payload: dict) -> str:
    url = f"{RUNWAY_BASE_URL}{endpoint}"
    r = requests.post(url, headers=_headers(api_key), json=payload, timeout=120)
    if r.status_code >= 400:
        raise RunwayError(f"Runway task create failed {r.status_code}: {r.text[:500]}")
    task_id = (r.json() or {}).get("id")
    if not task_id:
        raise RunwayError("Runway task create returned no task id")
    return task_id


def _wait_for_task(api_key: str, task_id: str, poll_sec: int = 5, timeout_sec: int = 900) -> dict:
    url = f"{RUNWAY_BASE_URL}/tasks/{task_id}"
    deadline = time.time() + timeout_sec
    last_status = None
    while time.time() < deadline:
        r = requests.get(url, headers=_headers(api_key), timeout=60)
        if r.status_code >= 400:
            raise RunwayError(f"Runway task fetch failed {r.status_code}: {r.text[:500]}")
        data = r.json() or {}
        status = (data.get("status") or "").upper()
        if status != last_status:
            logger.info("Runway task %s status=%s", task_id, status or "UNKNOWN")
            last_status = status
        if status == "SUCCEEDED":
            return data
        if status in {"FAILED", "CANCELLED", "ABORTED"}:
            code = data.get("failureCode") or "unknown"
            raise RunwayError(f"Runway task {task_id} failed with status={status} code={code}")
        time.sleep(poll_sec)
    raise RunwayError(f"Runway task {task_id} timed out after {timeout_sec}s")


def _download_file(url: str, dest: Path) -> Path:
    r = requests.get(url, timeout=300, stream=True)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return dest


def _image_prompt(item: NewsItem) -> str:
    base = build_story_visual_prompt(item)
    return (
        f"{base} "
        "Photoreal, dramatic but believable global-news visual, premium documentary look, "
        "broadcast quality, natural skin and lighting, strong composition."
    )


def _video_prompt(item: NewsItem) -> str:
    return (
        f"News footage for: {item.title}. "
        "Subtle natural motion, cinematic camera drift, realistic environmental movement, "
        "broadcast b-roll, professional newsroom documentary feel, no text overlays."
    )


def _generate_image(api_key: str, item: NewsItem, ratio: str, model: str, timeout_sec: int) -> str:
    task_id = _create_task(
        api_key,
        "/text_to_image",
        {
            "model": model,
            "ratio": ratio,
            "promptText": _image_prompt(item)[:1000],
        },
    )
    task = _wait_for_task(api_key, task_id, timeout_sec=timeout_sec)
    output = task.get("output") or []
    if not output:
        raise RunwayError("Runway image task succeeded but returned no output URL")
    return str(output[0])


def _generate_video(api_key: str, prompt_image_url: str, item: NewsItem, ratio: str, duration: int, model: str, timeout_sec: int) -> str:
    task_id = _create_task(
        api_key,
        "/image_to_video",
        {
            "model": model,
            "promptImage": prompt_image_url,
            "promptText": _video_prompt(item)[:1000],
            "ratio": ratio,
            "duration": duration,
        },
    )
    task = _wait_for_task(api_key, task_id, timeout_sec=timeout_sec)
    output = task.get("output") or []
    if not output:
        raise RunwayError("Runway video task succeeded but returned no output URL")
    return str(output[0])


def generate_story_media_with_runway(
    items: list[NewsItem],
    out_dir: Path,
    api_key: str,
    image_model: str = "gen4_image",
    video_model: str = "gen4.5",
    ratio: str = "1280:720",
    duration: int = 5,
    timeout_sec: int = 900,
    story_indices_1based: list[int] | None = None,
) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "runway_media_manifest.jsonl"
    produced: list[Path] = []

    for pos, item in enumerate(items, 1):
        idx = story_indices_1based[pos - 1] if story_indices_1based and pos - 1 < len(story_indices_1based) else pos
        try:
            image_url = _generate_image(api_key, item, ratio=ratio, model=image_model, timeout_sec=timeout_sec)
            image_path = _download_file(image_url, out_dir / f"{idx:02d}_runway_image.jpg")
            produced.append(image_path)

            video_url = _generate_video(
                api_key,
                image_url,
                item,
                ratio=ratio,
                duration=duration,
                model=video_model,
                timeout_sec=timeout_sec,
            )
            video_path = _download_file(video_url, out_dir / f"{idx:02d}_runway_clip.mp4")
            produced.append(video_path)

            with manifest_path.open("a", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "story_index": idx,
                            "title": item.title,
                            "image_model": image_model,
                            "video_model": video_model,
                            "image_url": image_url,
                            "video_url": video_url,
                            "image_file": image_path.name,
                            "video_file": video_path.name,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        except Exception as e:
            logger.warning("Runway media failed for story %s: %s", idx, e)

    return produced
