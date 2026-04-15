import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY", "").strip()
TARGET_DURATION_SEC = int(os.getenv("TARGET_DURATION_SEC", "900"))
ANCHOR_IMAGE_DIR = Path(os.getenv("ANCHOR_IMAGE_DIR", str(ROOT / "assets" / "anchor")))
# Har roz yahan images/videos daalen (filename order = play order), jaise 01.jpg, 02.mp4
NEWS_MEDIA_DIR = Path(os.getenv("NEWS_MEDIA_DIR", str(ROOT / "assets" / "news_today")))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(ROOT / "output")))
TEMP_DIR = Path(os.getenv("TEMP_DIR", str(ROOT / "temp")))
YOUTUBE_CLIENT_SECRETS = Path(os.getenv("YOUTUBE_CLIENT_SECRETS", str(ROOT / "secrets" / "client_secret.json")))
YOUTUBE_TOKEN_PICKLE = Path(os.getenv("YOUTUBE_TOKEN_PICKLE", str(ROOT / "secrets" / "youtube_token.pickle")))

# B-roll source: localai | runway | article | generated | openai | local
# localai = fully local topic-driven image generation, no API
# runway = real AI image generation + image-to-video via Runway API
# article = fetch article-page image and turn it into a short clip
# generated = create story cards + short clips locally from headline/summary
# local = only news_today/, no auto download/generation
BROLL_SOURCE = os.getenv("BROLL_SOURCE", "localai").strip().lower()

SCRIPT_PROVIDER = os.getenv("SCRIPT_PROVIDER", "template").strip().lower()  # openai | gemini | template
SEO_PROVIDER = os.getenv("SEO_PROVIDER", "openai").strip().lower()  # openai | gemini

VALID_BROLL_SOURCES = {"localai", "runway", "article", "generated", "openai", "local"}
VALID_SCRIPT_PROVIDERS = {"openai", "gemini", "template", "local", "offline", "none"}
VALID_SEO_PROVIDERS = {"openai", "gemini"}

NEWS_MUSIC_DIR = Path(os.getenv("NEWS_MUSIC_DIR", str(ROOT / "assets" / "news_music")))
BACKGROUND_MUSIC_FILE = os.getenv("BACKGROUND_MUSIC", "").strip()

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
ANCHOR_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
NEWS_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
NEWS_MUSIC_DIR.mkdir(parents=True, exist_ok=True)


def pick_background_music() -> Path | None:
    """Single file from BACKGROUND_MUSIC, else random track from NEWS_MUSIC_DIR."""
    if BACKGROUND_MUSIC_FILE:
        p = Path(BACKGROUND_MUSIC_FILE)
        if p.is_file():
            return p
    exts = (".mp3", ".wav", ".m4a", ".aac", ".ogg")
    tracks = [p for p in NEWS_MUSIC_DIR.iterdir() if p.is_file() and p.suffix.lower() in exts]
    if not tracks:
        return None
    import random

    return random.choice(tracks)


def seo_llm_enabled() -> bool:
    return os.getenv("SEO_METADATA_USE_LLM", "1").strip().lower() in ("1", "true", "yes", "on")


def has_script_provider_credentials() -> bool:
    if SCRIPT_PROVIDER == "openai":
        return bool(OPENAI_API_KEY)
    if SCRIPT_PROVIDER == "gemini":
        return bool(GEMINI_API_KEY)
    return True


def has_seo_provider_credentials() -> bool:
    if SEO_PROVIDER == "openai":
        return bool(OPENAI_API_KEY)
    if SEO_PROVIDER == "gemini":
        return bool(GEMINI_API_KEY)
    return False
