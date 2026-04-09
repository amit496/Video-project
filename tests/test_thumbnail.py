from pathlib import Path

from src.thumbnail_gen import build_youtube_thumbnail


def test_thumbnail_writes_file(tmp_path: Path):
    out = tmp_path / "thumb.jpg"
    build_youtube_thumbnail("World News Today | Test", out, anchor_path=None, subline="Subline")
    assert out.is_file()
    assert out.stat().st_size > 10_000

