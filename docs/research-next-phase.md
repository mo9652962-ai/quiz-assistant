# 下一阶段实施研究与决策

研究日期：2026-09-02（Asia/Shanghai）  
研究边界：本文件只给出实现建议，不直接修改业务代码、`data/quiz.db`、用户记录或 API key。

## 1. 结论先行

推荐采用：**兼容式 CLI 迁移 + FastAPI 同进程 API + Vue 3/Vite SPA + SQLite 本地优先 + Windows 单机发布**。

理由是：现有 domain/application service 已能承载导入、查询、练习、复习、备份和 AI 结果校验；Web 层只需把这些能力映射为 DTO，避免让 Vue 或路由层复制 matcher、scheduler、answer policy。CLI 不应一次性重写为全新命令树，而应先保留旧参数/退出码/`--json` 输出，再逐个把展示替换为 Typer/Rich。FastAPI 同步调用轻量 application service，导入和备份只有在实测超时后才使用 `202 + job`。

这不是对自动答题的授权。任何模型结果仍只能成为候选或待确认结果，不能写入 active 题目、替代用户答案、自动提交到第三方平台或绕过登录/验证码。

## 2. 研究时基线与当前实现状态

静态审查对象：`README.md`、`pyproject.toml`、`src/`、`tests/`、`docs/`、`migrations/`。

已确认事实：

- `pyproject.toml` 当前只声明 `pydantic>=2.7,<3`；CLI 入口为 `quiz_assistant.cli:main`，实现仍为 `argparse`。
- `src/quiz_assistant/application/` 已有 import/query/practice/review/backup service；domain 层已有 matcher、answer policy、scheduler。
- SQLite schema 当前为版本 2，包含 `question_banks`、`questions`、`options`、`tags`、`practice_sessions`、`answer_events`、`review_state`、`ai_audits`。
- `Settings` 默认数据库为 `data/quiz.db`，并创建 `raw`、`exports`、`backups` 目录；AI 默认关闭。
- `tests/` 当前有 14 个测试函数，覆盖 Pydantic 题型约束、匹配、AI stub、导入、练习、复习状态和备份恢复。
- 研究开始时没有 FastAPI、Vue/Vite、Typer、Rich 或 Playwright 实现；项目级 `AGENTS.md` 不存在。当前已完成 C14/C15 的第一批实现：Typer 兼容入口、FastAPI app、8 条核心 API 路由、本地 session header、答案披露门禁、AI allowlist/脱敏配置和显式备份覆盖确认。
- 本次执行环境没有可用的 `python` 或 `ruff` 命令，因此测试与 lint 只能列为“未执行”，不能宣称通过。

实现后复核：通过工作区内置 Python 与隔离依赖重新运行，当前为 21 个 pytest 通过、Ruff 通过；C16 Vue/Vite 页面、API client、Playwright smoke 已完成，C18 PyInstaller/SQLite 在线备份仍未完成。

## 3. 技术选择对比

### 3.1 CLI

| 方案 | 优点 | 风险/成本 | 结论 |
|---|---|---|---|
| 继续使用 `argparse` | 零迁移成本；标准库；现有调用和退出码稳定 | 参数声明分散；交互式输出、表格、进度和 shell completion 需要自行补齐 | 作为兼容内核保留，短期不单独扩展 |
| 全量迁移 Typer + Rich | 类型注解直接生成参数/帮助；Typer 支持多级 command；Rich 适合进度、表格和错误展示；长期体验最好 | 依赖增加；Click/Typer 版本变化可能改变帮助文本、metavar、异常输出；旧脚本和快照可能受影响 | 目标形态，但不一次性切换 |
| argparse 内核 + Typer/Rich 展示适配层 | 保留 `main(argv)`、旧参数语义、`--json` 和退出码；逐命令替换；可在 CI 比较旧/新输出 | 同时维护两套入口一段时间；需要明确“业务返回值”和“展示层输出”的边界 | **推荐 C14 采用** |

Typer 官方命令文档明确支持通过 `Typer()` 和 `@app.command()` 组织多命令应用；Rich 官方文档支持单任务和多任务进度显示。两者适合展示层，但不应进入 domain/application service。[Typer commands](https://typer.tiangolo.com/tutorial/commands/)；[Rich progress](https://rich.readthedocs.io/en/latest/progress.html)

迁移规则：

1. 先抽出纯函数 `build_*_result()` 和 `render_*()`，让 application service 返回 Pydantic/dataclass，而不是直接 `print`。
2. 先把 `init/import/search/answer/review/backup` 接到兼容适配层；`practice` 的交互循环最后迁移。
3. `--json` 输出保持稳定字段、UTF-8、退出码；Rich 只对 TTY 默认启用，管道/CI 自动降级为纯文本或 JSON。
4. 对 `--option` 重复参数、路径、整数范围、`--wrong/--due` 组合做显式校验；错误统一为非零退出码。

### 3.2 Web API 与前端

| 方案 | 优点 | 风险/成本 | 结论 |
|---|---|---|---|
| FastAPI API + Vue/Vite 开发服务器 + 生产时 FastAPI 提供 `dist` | 开发 HMR 快；生产可单进程；API schema 与 Pydantic/OpenAPI 对齐 | CORS、Vite proxy、静态 fallback、构建路径需分别测试 | **推荐** |
| FastAPI API + 独立 Nginx/Node 静态服务器 | 部署边界清晰；静态资源能力成熟 | Windows 安装和进程管理更重；本地数据目录与服务生命周期分散 | 仅在以后需要多用户/反向代理时采用 |
| Flask/Jinja 或纯服务端 HTML | 依赖少；单进程简单 | 交互状态、练习页面和 API 客户端复用较弱；不符合既定 Vue 3/Vite 范围 | 不推荐 |

Vue Quick Start 说明新项目使用 Vite 构建并采用 Single-File Components；Vite 官方说明开发服务器提供 HMR、生产构建输出静态 bundle，且 `vite preview` 只用于本地预览而不是生产服务。[Vue Quick Start](https://vuejs.org/guide/quick-start.html)；[Vite guide](https://vite.dev/guide/)；[Vite static deploy](https://vite.dev/guide/static-deploy.html)

API 设计规则：

- 路由层只做鉴权、输入 schema、错误映射和序列化；所有业务动作调用 `application.*_service`。
- `Question` 的正确字段不进入练习会话初始 payload；答题结果由服务端判定，前端不能改写 `is_correct`、`review_state` 或 session owner。
- 导入使用 `UploadFile`；FastAPI 文档指出大文件用 `UploadFile` 可利用 spooled file，且表单上传需要 `python-multipart`。[Request files](https://fastapi.tiangolo.com/tutorial/request-files/)
- 小型本地导入/备份先同步返回 200；若测试证明耗时明显或需要持续进度，再使用 `202 Accepted` 和任务状态资源。FastAPI `BackgroundTasks` 适合响应后执行的小任务，官方明确指出重型、跨进程任务应考虑 Celery 等更大的队列系统；本项目第一阶段不引入队列。[Background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- 生产构建由 FastAPI 托管；开发环境通过 Vite proxy 访问 `/api`，而不是把任意 CORS 暴露给浏览器。

### 3.3 数据库、备份与迁移

| 方案 | 优点 | 风险/成本 | 结论 |
|---|---|---|---|
| 当前 `shutil.copy2` + hash manifest | 实现简单；已有恢复前 hash 校验和临时文件替换 | 运行中写入时的快照一致性和 WAL/sidecar 文件处理需要补强 | 作为兼容 fallback，不作为长期备份核心 |
| Python `sqlite3.Connection.backup()` + manifest + 原子替换 | 官方 API 支持连接并发访问时创建备份，并支持 progress callback；更适合在线快照 | 需要明确连接生命周期和不覆盖当前库的 restore 策略 | **推荐 C18** |
| 导出 SQL/JSON 再重建 | 可读、易迁移、跨版本灵活 | 丢失索引/SQLite 元数据和部分运行状态风险；恢复慢 | 作为灾难性迁移/人工诊断格式，不作为默认备份 |

Python `sqlite3` 文档记录了 `Connection.backup()` 可在数据库被其他客户端访问时工作；SQLite Online Backup API 还说明源库只在实际读取期间短暂加读锁。现有 `initialize()` 用 `executescript()` 建表并写 schema version，后续需改成明确的版本迁移步骤并加入集成测试。[Python sqlite3](https://docs.python.org/3/library/sqlite3.html)；[SQLite Online Backup API](https://www.sqlite.org/backup.html)

迁移策略：每次 schema 版本只前进不回退；启动时先校验版本，再按 `v2 -> v3` 逐步执行；迁移前自动创建备份；失败时回滚事务并保留原库；不覆盖用户库、不把 migration 临时文件放到 Web 静态根目录。

### 3.4 Windows 发布

| 方案 | 优点 | 风险/成本 | 结论 |
|---|---|---|---|
| 直接运行 Python + uv 环境 | 可诊断、升级简单、开发成本低 | 目标机器需要 Python/依赖/启动脚本；路径和 PowerShell 策略不一致 | 开发与内部测试通道 |
| PyInstaller `onedir` + 启动器 | 目标机无需 Python；目录可写数据与安装目录可分离；问题较易诊断 | 需在 Windows 构建；需处理静态 `dist`、manifest、VC runtime、升级/卸载 | **推荐正式发布** |
| PyInstaller `onefile` | 单文件分发方便 | 启动解压、杀软误报、运行时写目录和恢复失败更难排查 | 不作为首发默认 |

PyInstaller 官方文档要求按目标操作系统分别构建；Windows 还需关注 Visual C++ runtime。`onedir` 更适合本项目的数据目录和故障恢复。[PyInstaller usage](https://pyinstaller.org/en/stable/usage.html)

uv 的 lockfile 会记录跨平台的精确解析版本，官方建议将 `uv.lock` 纳入版本控制，且由 uv 管理而非手工编辑；这比只在 `pyproject.toml` 写宽范围更适合 Windows 可复现安装。[uv project layout](https://docs.astral.sh/uv/concepts/projects/layout/)；[uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)

## 4. 版本与兼容性快照

以下版本是 2026-09-02 研究时观察到的上游 release，不是要求无条件追最新；实际实现必须用 `uv.lock` 固定可验证组合。

| 组件 | 研究快照 | 项目建议 | 主要兼容性风险 |
|---|---:|---|---|
| Python | 3.11+（项目约束） | 保持 `>=3.11`，Windows CI 至少测 3.11/3.12 | `StrEnum`、Pydantic v2 和打包解释器版本必须一致 |
| Pydantic | `>=2.7,<3`（当前约束） | 保持主版本约束，API schema 统一复用 | v1/v2 validator 写法不同 |
| Typer | 0.27.2 release | C14 锁定经测试的小版本；不依赖未锁定 Click 行为 | 0.27 有帮助/metavar/异常行为变更风险；[releases](https://github.com/fastapi/typer/releases) |
| Rich | 15.0.0 release | 作为 CLI 可选展示依赖；CI/管道禁用颜色 | Rich 输出不应成为 JSON 合同；[release](https://github.com/Textualize/rich/releases) |
| FastAPI | 0.141.1 release | C15 与 Starlette/Pydantic 一起锁定 | lifespan、validation error、OpenAPI 细节随版本变化；[releases](https://github.com/fastapi/fastapi/releases) |
| Vue/Vite | Vue 3 + Vite 当前主线 | `package-lock.json`/等效锁文件；构建产物纳入包 | Vite dev proxy 与生产 base path 不同；Vite 不把 `preview` 当生产服务 |
| Playwright | Python plugin 当前主线 | 锁定 `pytest-playwright` 与浏览器 revision；CI 明确 Chromium | 浏览器下载体积、Windows 支持矩阵和 headed/headless 差异 |
| PyInstaller | 6.22.2 release | Windows 构建机固定版本，产出 `onedir` | 目标系统 runtime、hidden imports、静态资源路径；[releases](https://github.com/pyinstaller/pyinstaller/releases) |
| uv | 0.12.9 release | 用 `uv lock --check`/`uv run --locked` 做安装门禁 | lockfile 与 metadata 不一致会拒绝运行；[releases](https://github.com/astral-sh/uv/releases) |

Typer、FastAPI、Rich、PyInstaller 的版本号来自各自官方 GitHub Releases 页面；不应把检索页面的“latest”当作永久兼容承诺。

## 5. 实施与回滚总原则

- 每个 C 阶段先新增失败测试，再写实现；不删除或改弱现有 14 个测试。
- 每阶段只改对应目录；API/前端新代码不直接操作 `sqlite3`，统一调用 application service。
- 任何 schema 变化先备份，再迁移；迁移失败保留原文件和诊断日志。
- 任何新依赖先写入 `pyproject.toml`/前端 lockfile，再在干净 Windows 环境复现安装。
- C14 保留旧 CLI 入口，C15/C16 不改变 CLI；C18 发布失败可回到 Python+uv 运行通道。
- “回滚”指恢复 Git 代码版本并从已验证备份恢复数据，不使用不可逆的 `reset --hard` 或覆盖用户库。

## 6. 研究来源与实际项目对照

实际项目仅用于识别模式，不复制其数据或代码：

- [Quiz-Card](https://github.com/ziyadsaf/Quiz-Card)：CSV 输入、顺序练习、重答、SQLite flashcard；可借鉴导入/练习最小闭环，但其四选项和扣分规则不适合直接替换本项目。
- [AWS-Quiz-SAA-C03](https://github.com/CarbonRaven/AWS-Quiz-SAA-C03)：JSON 到 SQLite、SM-2、标签筛选和 Flask 页面；可作为 Web/复习功能的对照，但其 Docker/Flask 部署不适合首个 Windows 单机包。
- [question-bank-mcp](https://github.com/woodstocksoftware/question-bank-mcp)：题型、标签、`draft/active/archived` 状态、搜索过滤和批量激活；支持本项目继续坚持“草稿不能进入 active 练习”。其中 AI suggestions 仅是功能模式，不构成本项目的自动写入授权。
- [math-question-bank releases](https://github.com/JudgePeach/math-question-bank/releases)：展示了 AI 解题/OCR/组卷等扩展方向；本项目只采纳“AI 必须成为显式可选能力”的边界，不采纳自动抓取或自动提交。

## 7. 待用户确认项

以下选择会改变实现，不在本研究阶段擅自决定：

1. 是否要多用户账户/远程访问；若不需要，C15 只实现本机单用户会话和严格 localhost 绑定。
2. “查询/答案”页面是否允许高置信度匹配直接显示答案，还是所有答案都必须二次点击确认。
3. 是否允许用户主动启用外部 AI provider；若允许，需要确认 provider allowlist、数据离开本机的提示、留存周期和日志脱敏规则。
4. 是否需要在首版支持备份恢复的覆盖当前库；默认建议必须显式 `force`/二次确认。
