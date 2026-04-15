from src.news_fetcher import NewsItem
from src.story_media_gen import build_story_visual_prompt


def test_story_visual_prompt_uses_title_and_summary():
    item = NewsItem(
        title="Major storms disrupt travel across Europe",
        summary="Air and rail services were delayed after severe weather alerts were issued in multiple regions.",
        link="https://example.com/news",
        published="Tue, 14 Apr 2026 10:00:00 GMT",
    )
    prompt = build_story_visual_prompt(item)
    assert "Major storms disrupt travel across Europe" in prompt
    assert "severe weather alerts" in prompt
    assert "16:9 frame" in prompt
