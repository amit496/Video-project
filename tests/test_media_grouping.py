from pathlib import Path

from src.media_sources import group_news_media_by_story


def test_grouping_by_prefix(tmp_path: Path):
    d = tmp_path / "news_today"
    d.mkdir()
    (d / "01_a.jpg").write_bytes(b"x")
    (d / "01_b.png").write_bytes(b"x")
    (d / "02_clip.mp4").write_bytes(b"x")
    (d / "random.jpg").write_bytes(b"x")

    story, general = group_news_media_by_story(d, max_stories=3)
    assert len(story) == 3
    assert [p.name for p in story[0]] == ["01_a.jpg", "01_b.png"]
    assert [p.name for p in story[1]] == ["02_clip.mp4"]
    assert story[2] == []
    assert [p.name for p in general] == ["random.jpg"]

