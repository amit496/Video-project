from src.local_ai_image_gen import _pick_theme


def test_pick_theme_changes_for_weather_story():
    theme = _pick_theme("Heavy rains and flooding disrupt travel across coastal regions")
    assert theme["accent"] == (96, 212, 255)
