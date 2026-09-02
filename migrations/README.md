# SQLite migrations

`quiz_assistant.infrastructure.db.initialize()` applies idempotent migrations on startup and records the current version in `schema_meta`. Version 2 adds `questions.answer_aliases_json` and is backward-compatible with a version 1 database. Future schema changes should increment `SCHEMA_VERSION`, add an explicit compatibility step, and include an integration test.

