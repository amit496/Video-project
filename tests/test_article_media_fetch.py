from src.article_media_fetch import _extract_meta_image


def test_extract_meta_image_prefers_og_image():
    html = """
    <html>
      <head>
        <meta property="og:image" content="/images/story-main.jpg" />
        <meta name="twitter:image" content="https://cdn.example.com/twitter.jpg" />
      </head>
    </html>
    """
    url = _extract_meta_image(html, "https://example.com/news/story")
    assert url == "https://example.com/images/story-main.jpg"
