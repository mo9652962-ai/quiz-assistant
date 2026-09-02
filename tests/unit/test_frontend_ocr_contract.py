from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_frontend_exposes_batch_ocr_page_and_client_method():
    main = (ROOT / "frontend" / "src" / "main.js").read_text(encoding="utf-8")
    client = (ROOT / "frontend" / "src" / "api" / "client.js").read_text(encoding="utf-8")
    view = (ROOT / "frontend" / "src" / "views" / "OcrView.vue").read_text(encoding="utf-8")

    assert "OcrView" in main and "path: '/ocr'" in main
    assert "ocrRecognize" in client and "append('files'" in client
    assert "multiple" in view and "截图识别" in view
