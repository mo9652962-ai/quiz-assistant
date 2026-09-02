# Quiz Assistant

一个本地优先的题库、匹配和练习 CLI。它只面向自有题库与学习复盘，不操作第三方考试页面、不自动提交答案，也不绕过登录、验证码或反作弊机制。

## 当前交付

- JSON/CSV 导入：UTF-8 BOM、逐行 Pydantic 校验、重复 ID 跳过、`rejected.jsonl` 错误报告、`--dry-run`
- SQLite：题库、题目、选项、标签、答题事件、复习状态和迁移版本
- 分层匹配：ID/raw exact、Unicode NFKC 规范化、选项辅助、token/序列相似度；返回状态、分数、方法、候选和证据
- 练习与复习：单选、多选、判断题、简答题；答题事件；轻量 SM-2 风格调度器；wrong/due 队列
- 备份恢复：数据库副本 + SHA-256 manifest，恢复前校验并使用临时文件替换
- AI 接口：安全的本地 stub 与可选 OpenAI-compatible adapter；真实网络默认关闭，结果不自动进入 active 题库

## Windows 快速开始

```powershell
cd C:\path\to\quiz_assistant
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m quiz_assistant init
python -m quiz_assistant import tests\fixtures\sample_questions.json
python -m quiz_assistant search --text "Which sentence is grammatically correct?"
python -m quiz_assistant practice --bank english-basic --count 3
python -m quiz_assistant review --wrong --due
python -m quiz_assistant backup create
```

也可以安装后使用 `quiz` 命令。数据库默认是 `data/quiz.db`，可用 `--db` 或 `QUIZ_DB_PATH` 覆盖。

## CSV 字段

必需字段为 `id,type,stem`；选择题使用 `option_a` 至 `option_d` 与 `correct_keys`，其它可选字段为 `explanation,tags,source_ref`。`correct_keys` 支持逗号或分号分隔。简答题把正确答案别名放在 `correct_keys`。

## 开发与验证

```powershell
python -m pytest
ruff check src tests
```

本实现刻意使用 Python 标准库 `sqlite3` 和 `argparse`，降低 Windows 离线运行的依赖面；Pydantic、pytest、ruff 在 `pyproject.toml` 中声明。CLI 保持子命令契约稳定，后续可在 API 稳定后替换为 Typer/Rich 外壳。没有网络配置时，AI 不会发起请求。

## 研究依据

实现取舍参考了文档附录列出的公开项目：

- [Quiz-Card](https://github.com/ziyadsaf/Quiz-Card)：CSV、CLI、错题闭环和 SQLite 持久化
- [AWS-Quiz-SAA-C03](https://github.com/CarbonRaven/AWS-Quiz-SAA-C03)：JSON 到 SQLite、SM-2 和筛选复习
- [question-bank-mcp](https://github.com/woodstocksoftware/question-bank-mcp)：题型、标签、状态和题库分层
- [math-question-bank](https://github.com/JudgePeach/math-question-bank)：本地题库与 AI 辅助的边界启示
- [OpenAI Chat API Reference](https://developers.openai.com/api/reference/resources/chat)：结构化 JSON Schema 优先于旧 JSON mode 的接口依据

这些来源只用于架构研究，没有复制其题库内容或代码；使用第三方题库前仍需自行核验许可证和数据授权。
