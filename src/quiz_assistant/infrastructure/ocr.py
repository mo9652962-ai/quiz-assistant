from __future__ import annotations

import os
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

MAX_OCR_IMAGE_BYTES = 10 * 1024 * 1024
MAX_OCR_TEXT_CHARS = 50_000
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
_QUESTION_START = re.compile(r"^\s*(\d{1,3})\s*[.)、]\s*(.*?)\s*$")
_OPTION_MARK = re.compile(r"(?<![A-Za-z0-9])([A-Ha-h])\s*[.)、:：]\s*")


class OCRInputError(ValueError):
    """The uploaded file is not an accepted, bounded image input."""


class OCRUnavailableError(RuntimeError):
    """The optional OCR runtime or its Tesseract executable is unavailable."""


@dataclass(frozen=True)
class OCROption:
    key: str
    text: str


@dataclass(frozen=True)
class OCRQuestion:
    number: int
    stem: str
    options: list[OCROption]
    confidence: float
    status: str
    issues: list[str]


@dataclass(frozen=True)
class OCRDocument:
    text: str
    questions: list[OCRQuestion]


def parse_ocr_text(text: str) -> OCRDocument:
    """Parse common numbered-question OCR text without guessing answers."""
    if not isinstance(text, str):
        raise OCRInputError("OCR text must be a string")
    text = text[:MAX_OCR_TEXT_CHARS]
    current_number: int | None = None
    stem_parts: list[str] = []
    options: list[OCROption] = []
    parsed: list[OCRQuestion] = []

    def flush() -> None:
        nonlocal current_number, stem_parts, options
        if current_number is None:
            return
        stem = " ".join(stem_parts).strip()
        parsed.append(_validate_question(current_number, stem, options))
        current_number = None
        stem_parts = []
        options = []

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        question_match = _QUESTION_START.match(line)
        if question_match:
            flush()
            current_number = int(question_match.group(1))
            stem, inline_options = _split_options(question_match.group(2))
            if stem:
                stem_parts.append(stem)
            options.extend(inline_options)
            continue
        if current_number is None:
            continue
        if _OPTION_MARK.match(line):
            _, line_options = _split_options(line)
            options.extend(line_options)
        elif options:
            options[-1] = OCROption(options[-1].key, f"{options[-1].text} {line}".strip())
        else:
            stem_parts.append(line)
    flush()
    return OCRDocument(text=text, questions=parsed)


def recognize_image(
    data: bytes,
    filename: str,
    *,
    ocr_reader: Callable[[bytes, str], str] | None = None,
) -> OCRDocument:
    """Recognize one bounded local image using an injectable OCR reader for tests."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        raise OCRInputError("only PNG, JPG, JPEG, WEBP, and BMP images are supported")
    if not data:
        raise OCRInputError("image file is empty")
    if len(data) > MAX_OCR_IMAGE_BYTES:
        raise OCRInputError("image exceeds 10 MiB limit")
    if ocr_reader is not None:
        return parse_ocr_text(ocr_reader(data, filename))
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise OCRUnavailableError(
            "OCR requires the optional 'ocr' dependency: Pillow and pytesseract"
        ) from exc
    try:
        _configure_tesseract(pytesseract)
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            text = pytesseract.image_to_string(image, lang="eng")
    except pytesseract.pytesseract.TesseractNotFoundError as exc:
        raise OCRUnavailableError("Tesseract executable was not found on PATH") from exc
    except Exception as exc:
        raise OCRInputError("image could not be decoded or recognized") from exc
    return parse_ocr_text(text)


def _configure_tesseract(pytesseract_module) -> None:
    """Use an explicit or common Windows install when Tesseract is not on PATH."""
    if shutil.which("tesseract"):
        return
    candidates = [
        os.environ.get("TESSERACT_CMD", ""),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            pytesseract_module.pytesseract.tesseract_cmd = candidate
            return


def _split_options(value: str) -> tuple[str, list[OCROption]]:
    matches = list(_OPTION_MARK.finditer(value))
    if not matches:
        return value.strip(), []
    stem = value[: matches[0].start()].strip()
    parsed: list[OCROption] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        option_text = value[match.end() : end].strip()
        parsed.append(OCROption(match.group(1).upper(), option_text))
    return stem, parsed


def _validate_question(number: int, stem: str, options: list[OCROption]) -> OCRQuestion:
    issues: list[str] = []
    if len(stem) < 8:
        issues.append("stem is too short")
    if len(options) < 2:
        issues.append("at least two options are required")
    keys = [option.key for option in options]
    if len(keys) != len(set(keys)):
        issues.append("option keys must be unique")
    if any(not option.text for option in options):
        issues.append("option text must not be blank")

    confidence = 0.0
    if stem:
        confidence += 0.35
    if len(stem) >= 15:
        confidence += 0.15
    if len(options) >= 2:
        confidence += 0.25
    if len(options) >= 4:
        confidence += 0.15
    if keys and len(keys) == len(set(keys)):
        confidence += 0.10
    if options and all(option.text for option in options):
        confidence += 0.10
    confidence = round(min(confidence, 1.0), 3)
    structural_error = any(
        issue in {"at least two options are required", "option keys must be unique", "option text must not be blank"}
        for issue in issues
    )
    if confidence >= 0.85 and not issues:
        status = "high_confidence"
    elif structural_error:
        status = "rejected"
    elif confidence >= 0.60:
        status = "needs_review"
    else:
        status = "rejected"
    return OCRQuestion(number, stem, list(options), confidence, status, issues)
