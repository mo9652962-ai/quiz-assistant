# Research notes

调研时间：2026-09-02（北京时间）。输入文档的附录来源在实现前重新核验，采用“只借鉴公开架构模式、不复制题库和代码”的原则。

| 来源 | 核验到的模式 | 本项目落地 |
|---|---|---|
| [Quiz-Card](https://github.com/ziyadsaf/Quiz-Card) | CSV 导入、CLI 练习、错题回练、SQLite 持久化 | JSON/CSV 导入 + practice/review + answer_events |
| [AWS-Quiz-SAA-C03](https://github.com/CarbonRaven/AWS-Quiz-SAA-C03) | JSON→SQLite、筛选和 SM-2 风格间隔 | 本地数据库与可替换 scheduler |
| [question-bank-mcp](https://github.com/woodstocksoftware/question-bank-mcp) | 题型、标签、draft/active 状态、题库分层 | Pydantic 题型模型、tags、status、bank |
| [math-question-bank](https://github.com/JudgePeach/math-question-bank) | 本地题库与 AI 辅助边界 | AI 接口隔离、默认关闭、只返回候选 |
| [OpenAI Chat API Reference](https://developers.openai.com/api/reference/resources/chat) | 支持结构化 JSON Schema；旧 JSON mode 不是首选 | adapter 发送 `json_schema`，本地仍做 schema/业务校验 |

实现使用 Python 标准库 `sqlite3`，原因是 SQLite 是 Python 标准库接口且能满足单机离线 MVP；Pydantic 用于输入和 AI 返回边界，CLI 的安装入口保持可扩展。

