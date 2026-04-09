"""Optional talking-head anchor using external tools (GPU recommended).

This module is a wrapper: it does NOT ship model weights.
Supported (user-installed) options:
- SadTalker (recommended): generates talking video from single image + audio.
- Wav2Lip: lip-sync a face video; needs a driving video template.

Pipeline behavior:
- If env LIPSYNC_ENABLE=1 and SadTalker command is available, generate an anchor clip.
- Otherwise fallback to static anchor image (existing behavior).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def sadtalker_available() -> bool:
    return bool(os.getenv("SADTALKER_DIR", "").strip()) and Path(os.getenv("SADTALKER_DIR", "")).is_dir()


def generate_talking_anchor(image_path: Path, audio_path: Path, out_dir: Path) -> Path | None:
    """Returns path to generated mp4 or None."""
    if os.getenv("LIPSYNC_ENABLE", "0").strip().lower() not in ("1", "true", "yes", "on"):
        return None
    sdir = Path(os.getenv("SADTALKER_DIR", "")).expanduser()
    if not sdir.is_dir():
        return None

    python_bin = os.getenv("SADTALKER_PYTHON", "").strip() or shutil.which("python") or "python"
    script = sdir / "inference.py"
    if not script.is_file():
        return None

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # SadTalker typically outputs into results/; we point it to our out_dir via --result_dir
    cmd = [
        python_bin,
        str(script),
        "--driven_audio",
        str(audio_path),
        "--source_image",
        str(image_path),
        "--result_dir",
        str(out_dir),
        "--still",
        "--preprocess",
        "full",
        "--enhancer",
        "gfpgan",
    ]
    subprocess.run(cmd, check=False, cwd=str(sdir))

    # Try to find a produced mp4
    candidates = sorted(out_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None

