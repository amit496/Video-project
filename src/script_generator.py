"""Generate a long-form spoken news script from headlines (OpenAI or Gemini)."""

from __future__ import annotations

import logging
import os

from openai import OpenAI

from . import config

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_HI = """आप एक प्रोफेशनल भारतीय न्यूज़ एंकर हैं। आपको YouTube के लिए एक continuous news script लिखनी है।
नियम:
- भाषा: सरल, स्पष्ट, शुद्ध/सामान्य हिन्दी (बहुत ज्यादा कठिन शब्द नहीं)।
- दिए गए headlines/summaries के बाहर कोई नए facts invent नहीं करने हैं।
- Target length: user द्वारा दिए गए word count के आसपास (15 मिनट के लिए ~130 wpm)।
- Format: 5 सेकंड का intro, फिर story-wise segments with smooth transitions, end में short outro।
- Output plain text हो (कोई brackets/stage directions नहीं)।
- Spoken script में URLs नहीं आने चाहिए।
"""

SYSTEM_PROMPT_EN = """You are an Indian news presenter writing a single continuous script for a YouTube video.
Rules:
- Use simple, clear English that Indian viewers understand easily.
- Cover ALL provided stories fairly; no invented facts — only expand from given headlines/summaries.
- Target spoken length: approximately the word count the user specifies (for ~15 min at ~130 wpm).
- Structure: 5-second intro, then segments per story with transitions, brief outro.
- No stage directions in brackets; output plain text to be read aloud only.
- Do not include URLs in the spoken script.
"""


def estimate_words_for_duration(seconds: int, wpm: int = 130) -> int:
    return max(400, int(seconds / 60 * wpm))

def _generate_openai(news_blob: str, target_duration_sec: int) -> str:
    words = estimate_words_for_duration(target_duration_sec)
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY missing in .env")

    client = OpenAI(api_key=config.OPENAI_API_KEY)
    user_msg = (
        "Here are today's world news items (from RSS). Write one script.\n\n"
        f"Target approximately {words} words for ~{target_duration_sec // 60} minutes of speech.\n\n"
        f"{news_blob}"
    )
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_SCRIPT_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT_EN},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.5,
        max_tokens=min(16000, words * 2),
    )
    text = (resp.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("Empty script from OpenAI")
    return text


def _generate_gemini(news_blob: str, target_duration_sec: int) -> str:
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY missing in .env")
    words = estimate_words_for_duration(target_duration_sec)
    model = os.getenv("GEMINI_SCRIPT_MODEL", "gemini-1.5-flash")

    # Lazy import so local users without gemini deps can still use OpenAI
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    prompt = (
        f"{SYSTEM_PROMPT_HI}\n\n"
        f"लक्ष्य: लगभग {words} शब्द (करीब {target_duration_sec // 60} मिनट)।\n\n"
        f"आज की खबरें:\n{news_blob}\n"
    )
    resp = client.models.generate_content(model=model, contents=prompt)
    text = (getattr(resp, "text", None) or "").strip()
    if not text:
        raise RuntimeError("Empty script from Gemini")
    return text


def generate_script(news_blob: str, target_duration_sec: int | None = None) -> str:
    target = target_duration_sec or config.TARGET_DURATION_SEC
    provider = config.SCRIPT_PROVIDER
    if provider == "gemini":
        return _generate_gemini(news_blob, target)
    return _generate_openai(news_blob, target)
