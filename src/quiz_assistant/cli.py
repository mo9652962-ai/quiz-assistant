from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import typer
from rich.console import Console

from quiz_assistant import __version__
from quiz_assistant.application.backup_service import create_backup, restore_backup
from quiz_assistant.application.import_service import import_questions
from quiz_assistant.application.practice_service import start_practice, submit_answer
from quiz_assistant.application.query_service import query_questions
from quiz_assistant.application.review_service import review_queue
from quiz_assistant.config import Settings
from quiz_assistant.infrastructure.db import connect, initialize
from quiz_assistant.infrastructure.repositories import create_session

app = typer.Typer(
    no_args_is_help=True,
    help="Local-first question bank practice assistant",
    add_completion=True,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"quiz-assistant {__version__}")
        raise typer.Exit()


@app.callback()
def _app_callback(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version"
    ),
) -> None:
    """Local-first question bank practice assistant."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quiz", description="Local-first question bank practice assistant"
    )
    parser.add_argument("--version", action="version", version=f"quiz-assistant {__version__}")
    subs = parser.add_subparsers(dest="command", required=True)

    init = subs.add_parser("init", help="initialize the local database")
    init.add_argument("--db", default=None)

    imp = subs.add_parser("import", help="import a JSON or CSV question file")
    imp.add_argument("source")
    imp.add_argument("--db", default=None)
    imp.add_argument("--dry-run", action="store_true")
    imp.add_argument("--json", action="store_true", dest="as_json")

    for name in ("search", "answer"):
        cmd = subs.add_parser(name, help="find a question and its candidate answer")
        cmd.add_argument("--text", required=True, help="question text or question id")
        cmd.add_argument(
            "--option", action="append", default=[], help="optional choice text; repeatable"
        )
        cmd.add_argument("--top", type=int, default=5)
        cmd.add_argument("--bank", default=None)
        cmd.add_argument("--db", default=None)
        cmd.add_argument("--json", action="store_true", dest="as_json")

    practice = subs.add_parser("practice", help="start an interactive practice session")
    practice.add_argument("--bank", default=None)
    practice.add_argument("--tag", default=None)
    practice.add_argument("--count", type=int, default=10)
    practice.add_argument("--db", default=None)

    review = subs.add_parser("review", help="show wrong or due questions")
    review.add_argument("--wrong", action="store_true")
    review.add_argument("--due", action="store_true")
    review.add_argument("--limit", type=int, default=20)
    review.add_argument("--db", default=None)

    export = subs.add_parser("export", help="export answer history")
    export.add_argument("--format", choices=("csv", "json", "md"), default="csv")
    export.add_argument("--out", required=True)
    export.add_argument("--db", default=None)

    backup = subs.add_parser("backup", help="create or restore a validated SQLite backup")
    backup.add_argument("action", choices=("create", "restore"))
    backup.add_argument("--db", default=None)
    backup.add_argument("--dir", default=None)
    backup.add_argument("--force", action="store_true")
    return parser


def _settings(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env(args.db)
    settings.ensure_dirs()
    return settings


def _result_json(result) -> dict:
    return {
        "status": result.status,
        "question_id": result.question_id,
        "answer_keys": result.answer_keys,
        "answer_texts": result.answer_texts,
        "method": result.method,
        "score": result.score,
        "evidence": result.evidence,
        "normalizer_version": result.normalizer_version,
        "alternatives": [
            {"question_id": item.question.id, "score": item.score, "method": item.method}
            for item in result.alternatives
        ],
    }


def _print_result(result, as_json: bool = False) -> None:
    payload = _result_json(result)
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"状态: {payload['status']} | 分数: {payload['score']:.3f} | 方法: {payload['method']}")
    if payload["question_id"]:
        print(f"题目: {payload['question_id']}")
        print(f"候选答案: {', '.join(payload['answer_keys']) or '无'}")
        print(f"依据: {'; '.join(payload['evidence'])}")
    else:
        print("未找到足够可信的本地候选。")


def _export(db_path: Path, output: Path, fmt: str) -> None:
    initialize(db_path)
    with connect(db_path) as db:
        rows = [
            dict(row)
            for row in db.execute("SELECT * FROM answer_events ORDER BY created_at").fetchall()
        ]
    output.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    elif fmt == "md":
        lines = [
            "# 答题记录",
            "",
            "| 时间 | 题目 | 用户答案 | 正确 | 置信度 |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {r['created_at']} | {r['question_id']} | {r['user_answer']} | {'是' if r['is_correct'] else '否'} | {r['confidence'] or ''} |"
            for r in rows
        ]
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        with output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["id"])
            writer.writeheader()
            writer.writerows(rows)


def _legacy_main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    settings = _settings(args)
    if args.command == "init":
        initialize(settings.db_path)
        print(f"initialized quiz database: {settings.db_path.resolve()}")
        return 0
    if args.command == "import":
        report = import_questions(args.source, settings.db_path, dry_run=args.dry_run)
        print(
            report.model_dump_json(indent=2)
            if args.as_json
            else f"导入完成: total={report.total}, imported={report.imported}, duplicate={report.skipped_duplicate}, rejected={report.rejected_count}"
        )
        return 0 if not report.rejected else 2
    if args.command in {"search", "answer"}:
        _print_result(
            query_questions(settings.db_path, args.text, args.option, args.top, args.bank),
            args.as_json,
        )
        return 0
    if args.command == "practice":
        questions = start_practice(settings.db_path, bank=args.bank, tag=args.tag, count=args.count)
        if not questions:
            print("没有符合条件的题目。")
            return 0
        with connect(settings.db_path) as db:
            session_id = create_session(
                db, "practice", json.dumps({"bank": args.bank, "tag": args.tag})
            )
        for index, question in enumerate(questions, start=1):
            print(f"\n[{index}/{len(questions)}] {question.stem}")
            for option in question.options:
                print(f"  {option.key}. {option.text}")
            answer = input("答案（多选用逗号分隔，退出输入 q）: ").strip()
            if answer.lower() == "q":
                break
            correct, _ = submit_answer(settings.db_path, question.id, answer, session_id=session_id)
            print("正确" if correct else "再复盘一下；可用 quiz review --wrong 查看")
        return 0
    if args.command == "review":
        for item in review_queue(
            settings.db_path, wrong=args.wrong, due=args.due, limit=args.limit
        ):
            print(
                f"{item.question.id} | due={item.due_at or 'now'} | reps={item.repetitions} | {item.question.stem}"
            )
        return 0
    if args.command == "export":
        _export(settings.db_path, Path(args.out), args.format)
        print(f"exported: {Path(args.out).resolve()}")
        return 0
    if args.command == "backup":
        if args.action == "create":
            target = create_backup(settings.db_path, args.dir)
            print(f"backup created: {target.resolve()}")
        else:
            if not args.dir:
                raise SystemExit("backup restore requires --dir")
            restore_backup(args.dir, settings.db_path, force=args.force)
            print(f"backup restored: {settings.db_path.resolve()}")
        return 0
    return 1


def _args(*parts: str | None) -> list[str]:
    return [part for part in parts if part is not None]


@app.command("init")
def init_command(db: str | None = typer.Option(None, "--db")) -> None:
    """Initialize the local database."""
    raise typer.Exit(_legacy_main(_args("init", "--db", db)))


@app.command("import")
def import_command(
    source: str = typer.Argument(...),
    db: str | None = typer.Option(None, "--db"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Import a JSON or CSV question file."""
    raise typer.Exit(
        _legacy_main(_args("import", source, "--db", db, "--dry-run" if dry_run else None, "--json" if as_json else None))
    )


def _query_command(
    command: str,
    text: str,
    option: list[str],
    top: int,
    bank: str | None,
    db: str | None,
    as_json: bool,
) -> None:
    argv = _args(command, "--text", text, "--top", str(top), "--bank", bank, "--db", db)
    for item in option:
        argv.extend(("--option", item))
    if as_json:
        argv.append("--json")
    raise typer.Exit(_legacy_main(argv))


@app.command("search")
def search_command(
    text: str = typer.Option(..., "--text"),
    option: list[str] = typer.Option([], "--option"),  # noqa: B008 - Typer declaration
    top: int = typer.Option(5, "--top", min=1, max=20),
    bank: str | None = typer.Option(None, "--bank"),
    db: str | None = typer.Option(None, "--db"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Find a question and its candidate answer."""
    _query_command("search", text, option, top, bank, db, as_json)


@app.command("answer")
def answer_command(
    text: str = typer.Option(..., "--text"),
    option: list[str] = typer.Option([], "--option"),  # noqa: B008 - Typer declaration
    top: int = typer.Option(5, "--top", min=1, max=20),
    bank: str | None = typer.Option(None, "--bank"),
    db: str | None = typer.Option(None, "--db"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Find a question and its candidate answer."""
    _query_command("answer", text, option, top, bank, db, as_json)


@app.command("practice")
def practice_command(
    bank: str | None = typer.Option(None, "--bank"),
    tag: str | None = typer.Option(None, "--tag"),
    count: int = typer.Option(10, "--count", min=0, max=100),
    db: str | None = typer.Option(None, "--db"),
) -> None:
    """Start an interactive practice session."""
    raise typer.Exit(_legacy_main(_args("practice", "--bank", bank, "--tag", tag, "--count", str(count), "--db", db)))


@app.command("review")
def review_command(
    wrong: bool = typer.Option(False, "--wrong"),
    due: bool = typer.Option(False, "--due"),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    db: str | None = typer.Option(None, "--db"),
) -> None:
    """Show wrong or due questions."""
    raise typer.Exit(_legacy_main(_args("review", "--wrong" if wrong else None, "--due" if due else None, "--limit", str(limit), "--db", db)))


@app.command("export")
def export_command(
    out: str = typer.Option(..., "--out"),
    fmt: str = typer.Option("csv", "--format"),
    db: str | None = typer.Option(None, "--db"),
) -> None:
    """Export answer history."""
    raise typer.Exit(_legacy_main(_args("export", "--format", fmt, "--out", out, "--db", db)))


@app.command("backup")
def backup_command(
    action: str = typer.Argument(...),
    db: str | None = typer.Option(None, "--db"),
    directory: str | None = typer.Option(None, "--dir"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Create or restore a validated SQLite backup."""
    raise typer.Exit(_legacy_main(_args("backup", action, "--db", db, "--dir", directory, "--force" if force else None)))


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        app()
        return 0
    return _legacy_main(argv)


if __name__ == "__main__":
    sys.exit(main())
