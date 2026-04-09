"""
Collect recent headlines from public RSS feeds (ToS permitting).
Edit FEEDS to match client-approved sources.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import feedparser
import requests

logger = logging.getLogger(__name__)

# Major English-language world news RSS (trim or replace per client policy)
FEEDS: list[str] = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.cnn.com/rss/edition_world.rss",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.theguardian.com/world/rss",
    "https://feeds.reuters.com/Reuters/worldNews",
]


@dataclass
class NewsItem:
    title: str
    summary: str
    link: str
    published: str | None


def _fetch_feed(url: str, timeout: int = 20) -> feedparser.FeedParserDict:
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "NewsBot/1.0"})
    r.raise_for_status()
    return feedparser.parse(r.content)


def collect_news(max_per_feed: int = 3, max_total: int = 10) -> list[NewsItem]:
    items: list[NewsItem] = []
    for url in FEEDS:
        try:
            parsed = _fetch_feed(url)
            for entry in parsed.entries[:max_per_feed]:
                title = (entry.get("title") or "").strip()
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                link = (entry.get("link") or "").strip()
                published = entry.get("published") or entry.get("updated")
                if not title:
                    continue
                items.append(NewsItem(title=title, summary=summary, link=link, published=published))
        except Exception as e:
            logger.warning("Feed failed %s: %s", url, e)
        if len(items) >= max_total:
            break
    return items[:max_total]


def format_for_prompt(news: Iterable[NewsItem]) -> str:
    lines = []
    for i, n in enumerate(news, 1):
        lines.append(f"{i}. {n.title}\n   {n.summary[:500]}\n   Source: {n.link}")
    return "\n\n".join(lines)
