from pathlib import Path


def test_browser_helper_is_fill_only_and_never_clicks_or_submits():
    script = (
        Path(__file__).parents[2] / "browser" / "quiz-assistant-fill-only.user.js"
    ).read_text(encoding="utf-8")

    assert "@name         Quiz Assistant · Fill Only" in script
    assert "GM_xmlhttpRequest" in script
    assert "dispatchEvent(new Event('change'" in script
    assert ".click(" not in script
    assert "submit" not in script.lower()
