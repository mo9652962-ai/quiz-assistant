from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from pathlib import Path


def load_records(path: str | Path) -> Iterator[tuple[int, dict[str, object]]]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle), start=2):
                yield row_number, csv_row_to_payload(row)
        return
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8-sig") as handle:
            for row_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    yield row_number, {
                        "__load_error__": f"invalid JSONL: {exc.msg}",
                        "__raw_line__": line.rstrip("\r\n"),
                    }
                    continue
                if not isinstance(item, dict):
                    yield row_number, {
                        "__load_error__": "JSONL row must be an object",
                        "__raw_line__": line.rstrip("\r\n"),
                    }
                    continue
                yield row_number, item
        return
    with path.open("r", encoding="utf-8-sig") as handle:
        parsed = json.load(handle)
    if isinstance(parsed, dict):
        parsed = parsed.get("questions", [parsed])
    if not isinstance(parsed, list):
        raise TypeError("JSON root must be an object or list of questions")
    for row_number, item in enumerate(parsed, start=1):
        if not isinstance(item, dict):
            raise TypeError(f"JSON row {row_number} must be an object")
        yield row_number, item


def csv_row_to_payload(row: dict[str, str | None]) -> dict[str, object]:
    def required(name: str) -> str:
        value = (row.get(name) or "").strip()
        if not value:
            raise ValueError(f"missing required CSV field: {name}")
        return value

    options = []
    for key, column in (("A", "option_a"), ("B", "option_b"), ("C", "option_c"), ("D", "option_d")):
        value = (row.get(column) or "").strip()
        if value:
            options.append({"key": key, "text": value})
    correct_keys = [
        item.strip().upper()
        for item in (row.get("correct_keys") or "").replace(";", ",").split(",")
        if item.strip()
    ]
    q_type = required("type")
    payload: dict[str, object] = {
        "id": required("id"),
        "bank": (row.get("bank") or "default").strip() or "default",
        "type": q_type,
        "stem": required("stem"),
        "options": options,
        "explanation": (row.get("explanation") or "").strip() or None,
        "tags": [
            tag.strip()
            for tag in (row.get("tags") or "").replace(";", ",").split(",")
            if tag.strip()
        ],
        "source_ref": (row.get("source_ref") or "").strip() or None,
    }
    for option in options:
        option["correct"] = option["key"] in correct_keys
    if q_type == "short_answer":
        payload["answer_aliases"] = correct_keys
        payload["options"] = []
    return payload


def write_jsonl(path: str | Path, records: list[object]) -> None:
    with Path(path).open("w", encoding="utf-8") as handle:
        handle.writelines(
            json.dumps(record, ensure_ascii=False, default=str) + "\n" for record in records
        )
