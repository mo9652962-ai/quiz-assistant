# Security Policy for quiz-assistant

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Security & Local-First Boundaries

`quiz-assistant` is a zero-dependency (Python standard library + SQLite) command-line question bank manager.
- **Offline First:** All question storage, fuzzy matching, and SM-2 spaced repetition algorithms execute 100% locally.
- **Data Protection:** Database operations use parameterized queries to prevent SQL injection.

## Reporting a Vulnerability

Please report security issues privately via GitHub Security Advisories or contact `mo9652962-ai@users.noreply.github.com`.
