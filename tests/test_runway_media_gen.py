from src.news_fetcher import NewsItem
from src.runway_media_gen import _image_prompt, _video_prompt


def test_runway_prompts_include_story_context():
    item = NewsItem(
        title="Ceasefire talks continue after overnight strikes",
        summary="Officials said negotiations resumed while regional tensions remained high.",
        link="https://example.com/story",
        published=None,
    )
    assert "Ceasefire talks continue" in _image_prompt(item)
    assert "Photoreal" in _image_prompt(item)
    assert "Subtle natural motion" in _video_prompt(item)
