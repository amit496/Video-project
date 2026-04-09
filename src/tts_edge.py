"""
Text-to-speech using edge-tts (free). Indian English: en-IN-NeerjaNeural, hi-IN-SwaraNeural for Hindi.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import edge_tts

logger = logging.getLogger(__name__)

# Indian English female (change via env EDGE_TTS_VOICE)
DEFAULT_VOICE = "en-IN-NeerjaNeural"


async def _speak_async(text: str, out_path: Path, voice: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


def synthesize_to_file(text: str, out_wav: Path, voice: str | None = None) -> Path:
    import os

    v = voice or os.getenv("EDGE_TTS_VOICE", DEFAULT_VOICE)
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_speak_async(text, out_wav, v))
    return out_wav
