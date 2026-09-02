from __future__ import annotations

import json
from pathlib import Path

from quiz_assistant.infrastructure.db import connect, initialize
from quiz_assistant.infrastructure.file_formats import load_records
from quiz_assistant.infrastructure.repositories import insert_question, question_exists
from quiz_assistant.schemas.import_report import ImportReport, RejectedRow
from quiz_assistant.schemas.question import question_from_payload


def import_questions(
    source: str | Path, db_path: str | Path, *, dry_run: bool = False
) -> ImportReport:
    initialize(db_path)
    report = ImportReport(source=str(source), dry_run=dry_run)
    rejected_path = Path(db_path).parent / "rejected.jsonl"
    rejected_lines: list[str] = []
    with connect(db_path) as db:
        try:
            records = load_records(source)
            for row_number, raw in records:
                report.total += 1
                try:
                    question = question_from_payload(raw)
                    if question_exists(db, question.id):
                        report.skipped_duplicate += 1
                        continue
                    if not dry_run:
                        insert_question(db, question, str(source))
                    report.imported += 1
                except (
                    TypeError,
                    ValueError,
                    KeyError,
                ) as exc:  # row-level rejection is part of the public import contract
                    rejected = RejectedRow(row_number=row_number, error=str(exc), raw=raw)
                    report.rejected.append(rejected)
                    rejected_lines.append(rejected.model_dump_json())
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            report.total += 1
            rejected = RejectedRow(row_number=1, error=str(exc), raw={})
            report.rejected.append(rejected)
            rejected_lines.append(rejected.model_dump_json())
    if rejected_lines:
        rejected_path.write_text("\n".join(rejected_lines) + "\n", encoding="utf-8")
    return report
