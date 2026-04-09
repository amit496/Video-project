"""High-quality SEO metadata using LLM (OpenAI or Gemini), with strict JSON output."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from openai import OpenAI

from . import config


@dataclass
class SeoMetadata:
    title: str
    description: str
    tags: list[str]


SYSTEM_PROMPT = """You are an expert YouTube SEO copywriter for a daily WORLD NEWS channel.
Write metadata that is policy-safe, non-clickbait, and optimized for global audience + Indian viewers.

Output MUST be valid JSON only (no markdown), matching this schema:
{
  "title": string,              // <= 100 chars
  "description": string,        // <= 5000 chars, include 2-3 short paragraphs + 8-15 bullet topics + hashtags
  "tags": string[]              // 15-35 tags, each <= 30 chars, no duplicates
}

Rules:
- Do not claim footage ownership; do not mention scraping.
- Do not include URLs.
- Mention "World News" and "India" naturally (not spam).
- Avoid sensitive policy violations; keep tone professional.
"""


def _safe_parse_json(text: str) -> dict:
    text = (text or "").strip()
    # Try direct JSON first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract first {...} block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _generate_openai(script: str, titles: list[str]) -> dict:
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing in .env")
    model = os.getenv("OPENAI_SEO_MODEL", os.getenv("OPENAI_SCRIPT_MODEL", "gpt-4o-mini"))
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    topics = "\n".join([f"- {t}" for t in titles[:12]])
    user = (
        "Create YouTube metadata for today's world news video.\n\n"
        f"Topics:\n{topics}\n\n"
        "Transcript (for context, may be long):\n"
        f"{script[:12000]}"
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
        max_tokens=1200,
    )
    raw = (resp.choices[0].message.content or "").strip()
    return _safe_parse_json(raw)


def _generate_gemini(script: str, titles: list[str]) -> dict:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing in .env")
    model = os.getenv("GEMINI_SEO_MODEL", "gemini-1.5-flash")
    topics = "\n".join([f"- {t}" for t in titles[:12]])
    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        "Create YouTube metadata in Hindi+English mix (Indian audience), but keep it globally understandable.\n\n"
        f"Topics:\n{topics}\n\n"
        f"Transcript:\n{script[:12000]}\n"
    )
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = client.models.generate_content(model=model, contents=prompt)
    raw = (getattr(resp, "text", None) or "").strip()
    return _safe_parse_json(raw)


def generate_seo_metadata(script: str, titles: list[str]) -> SeoMetadata:
    provider = config.SEO_PROVIDER
    if provider == "gemini":
        data = _generate_gemini(script, titles)
    else:
        data = _generate_openai(script, titles)

    title = str(data.get("title", "")).strip()[:100]
    description = str(data.get("description", "")).strip()[:5000]
    tags_raw = data.get("tags") or []
    tags: list[str] = []
    seen = set()
    for t in tags_raw:
        s = str(t).strip()
        if not s:
            continue
        s = s[:30]
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(s)

    if not title or not description or len(tags) < 5:
        raise RuntimeError("LLM returned incomplete SEO metadata")

    return SeoMetadata(title=title, description=description, tags=tags)

