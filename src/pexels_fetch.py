"""Download landscape photos from Pexels (free API key) and keep a license log."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.pexels.com/v1/search"


def _clean_query(title: str, max_len: int = 70) -> str:
    t = re.sub(r"[^\w\s-]", " ", title, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:max_len] or "world news"


def fetch_one_image(api_key: str, query: str, dest: Path, timeout: int = 45) -> dict | None:
    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 1, "orientation": "landscape", "size": "large"}
    r = requests.get(SEARCH_URL, headers=headers, params=params, timeout=timeout)
    if r.status_code == 401:
        logger.error("Pexels API key invalid.")
        return None
    if r.status_code != 200:
        logger.warning("Pexels search failed (%s): %s", r.status_code, query[:40])
        return None
    data = r.json()
    photos = data.get("photos") or []
    if not photos:
        logger.warning("Pexels: no results for %s", query[:50])
        return None
    p0 = photos[0] or {}
    src = (p0.get("src") or {}).get("large") or (p0.get("src") or {}).get("original")
    if not src:
        return None
    ir = requests.get(src, timeout=timeout)
    ir.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(ir.content)
    return {
        "provider": "pexels",
        "query": query,
        "dest_file": dest.name,
        "pexels_id": p0.get("id"),
        "url": p0.get("url"),
        "photographer": p0.get("photographer"),
        "photographer_url": p0.get("photographer_url"),
        "license_note": "Follow Pexels license terms. Store attribution if required by client policy.",
        "src_used": src,
    }


def _append_license_log(out_dir: Path, entries: list[dict]) -> None:
    if not entries:
        return
    log_path = Path(out_dir) / "license_log.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def download_broll_for_titles(titles: list[str], out_dir: Path, api_key: str, max_images: int = 10) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    log_entries: list[dict] = []
    for i, title in enumerate(titles[:max_images], 1):
        q = _clean_query(title)
        dest = out_dir / f"{i:02d}_pexels.jpg"
        meta = fetch_one_image(api_key, q, dest)
        if meta:
            saved.append(dest)
            log_entries.append(meta)
            logger.info("Pexels: saved %s (%s)", dest.name, q[:50])
        else:
            fallback = _clean_query(" ".join(title.split()[:3]) or "global news")
            meta2 = fetch_one_image(api_key, fallback, dest) if fallback != q else None
            if meta2:
                saved.append(dest)
                log_entries.append(meta2)
    _append_license_log(out_dir, log_entries)
    return saved
