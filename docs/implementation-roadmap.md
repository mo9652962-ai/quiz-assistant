# C14–C18 Implementation Roadmap

目标：在不破坏现有 CLI、domain/application service、SQLite 数据和 14 个测试的前提下，逐步交付 Web、合规边界和 Windows 发布能力。每一阶段遵循 **先写失败测试（RED）→最小实现（GREEN）→重构（REFACTOR）→回归与回滚演练**。

当前进度：C14/C15 核心路径已实现并通过 21 个测试与 Ruff；C16 已加入 Vue 3/Vite 页面、统一 API client、独立端口代理和本机 Playwright smoke；C17 已加入 AI allowlist/脱敏基础门禁。完整多用户账户、C18 SQLite 在线备份与 PyInstaller 发布仍待实施。

## 阶段总览

| 阶段 | 主题 | 主要产出 | 失败时回滚 |
|---|---|---|---|
| C14 | CLI 兼容式迁移 | Typer/Rich 展示适配、稳定 JSON/退出码 | 保留 `argparse` 入口和旧命令 |
| C15 | FastAPI API | API app、schema、auth、health/queries/practice/reviews/import/backup | API 目录可移除，CLI 不受影响 |
| C16 | Vue 3/Vite 前端与 E2E | 页面、API client、Playwright 测试 | 继续使用 CLI；不写入真实数据 |
| C17 | 合规与安全边界 | allowlist、确认、审计、停止/拒绝路径 | 关闭外部 provider 和写操作开关 |
| C18 | Windows 运维与发布 | uv 锁定、迁移/备份、PyInstaller onedir、启动器 | 回到 Python+uv 运行包和已验证备份 |

## C14 — CLI

输入：当前 `src/quiz_assistant/cli.py` 的 `argparse` 命令和 `main(argv)`；当前 `pyproject.toml`；现有 14 个测试。

拟改文件：

- `pyproject.toml`：增加 Typer/Rich，锁定兼容范围。
- `src/quiz_assistant/cli.py`：抽出 command handler 与 render/JSON serializer；保留兼容入口。
- 可新增 `src/quiz_assistant/presentation/cli.py`、`tests/unit/test_cli_contract.py`。

失败测试先写：

- 旧命令的 `--help`、`--json`、重复 `--option`、`--dry-run` 仍得到相同语义。
- 14 个现有测试保持原样且不能删除。
- 管道输出不含 ANSI；JSON 可被 `json.loads` 读取；`import` 有拒绝行时仍返回非零码。
- `practice --count 0/-1`、`backup restore` 缺参数、未知选项得到可预测错误。

实现与验收：

1. 让 application service 返回结构化结果，展示层才使用 Rich Table/Progress。
2. 首先把 `init/import/search/answer/review/backup` 接到 Typer wrapper；`practice` 最后迁移。
3. TTY 才启用 Rich；`--json` 明确禁用 Rich。
4. 验收：`uv run --locked pytest`、`uv run --locked ruff check src tests`、旧命令 smoke test 全部执行并保存日志。

回滚：入口默认保留 `argparse`；若 Typer 帮助/异常行为不兼容，退回旧入口，保留已抽出的纯 serializer，不回滚 domain/application 代码。

## C15 — FastAPI API

输入：`application/*_service.py`、`domain/*`、SQLite schema v2、`docs/api-contract-draft.md`。

拟新增/修改文件：

- `src/quiz_assistant/api/app.py`、`api/dependencies.py`、`api/errors.py`、`api/auth.py`。
- `src/quiz_assistant/api/schemas.py`、`api/routes/health.py`、`banks.py`、`imports.py`、`queries.py`、`practice.py`、`reviews.py`、`backups.py`。
- `pyproject.toml` 增加 FastAPI/Uvicorn/python-multipart；`tests/api/`。

失败测试先写：

- 未认证的写请求返回 401；不存在或过期 session 不能访问其他 session。
- `/health` 不泄露绝对路径；生产 app 默认绑定 `127.0.0.1`。
- practice session 响应不含 `correct`；只有用户提交当前 session 的 answer 才写 `answer_events`。
- `POST /queries` 的结果与 `query_service` 一致；候选/待确认状态不能被路由改写。
- 导入 dry-run 不改数据库；验证失败返回 ImportReport/422，而不是 500。
- 备份恢复没有确认、hash 不匹配或目标已存在时拒绝且保留原库。

实现与验收：

1. app factory 用 lifespan 做 readiness/migration 预检；不要在模块 import 时打开全局连接。
2. 每个 route 只做 DTO、依赖、错误映射；调用 application service。
3. `/api` 统一错误体、request id、limit 上限、输入大小上限；开发 CORS 只允许明确 origin。
4. 首版导入/备份同步；若性能测试需要，再引入 `202 + job`，不使用无状态 fire-and-forget。
5. 验收：FastAPI TestClient/API contract tests + 14 个原测试 + 同一 fixture 的 CLI/API 结果对比。

回滚：禁用 Web 启动器仍可执行 `quiz`；删除/停用 API route 不影响 application service。若 schema 需要变化，必须先备份并用单独 migration 版本，不在 C15 直接重建数据库。

## C16 — Vue 3/Vite 与 Playwright

输入：C15 OpenAPI/contract、API 页面映射、现有 JSON fixtures；用户确认的答案披露文案。

拟新增文件：

- `frontend/package.json`、lockfile、`vite.config.*`、`src/main.*`、`src/router.*`、`src/api/client.*`。
- `frontend/src/views/Dashboard.vue`、`Import.vue`、`Search.vue`、`Practice.vue`、`Review.vue`、`Settings.vue`。
- `tests/e2e/`、Playwright 配置及本地启动脚本。

失败测试先写：

- 页面在 API down、空 bank、导入拒绝、session 失效时展示明确错误，不吞异常。
- practice 页面收到的网络 payload 中不能出现 `correct: true` 或 `correct_keys`。
- 用户未点击确认时，候选答案不会进入 active 练习或写入题目。
- dry-run 预览不改变题目数量；确认导入后，API 与 CLI 查询结果一致。
- wrong/due 复习路径能打开题目并通过同一个 answer endpoint 记录事件。

实现与验收：

1. Vite 开发服务器 proxy `/api` 到 FastAPI；生产由 FastAPI 托管 `dist` 并验证 SPA fallback。
2. API client 只传用户产生的字段，忽略服务端只读字段；统一处理 401/403/422。
3. Playwright 使用官方 pytest plugin，固定 Chromium，默认 headless；测试服务使用临时 `QUIZ_DB_PATH` 和临时备份目录。
4. 验收：Playwright smoke（健康、导入 dry-run、搜索、练习提交、复习、备份确认）+ 前端构建；不访问第三方学习/考试平台。

Playwright 官方推荐 pytest plugin，并支持 Chromium/Firefox/WebKit 与隔离 context；浏览器安装是单独步骤，Windows CI 需要缓存或预装。[Playwright intro](https://playwright.dev/python/docs/intro)；[Browser API](https://playwright.dev/python/docs/api/class-browser)

回滚：前端只读/临时数据；构建失败不覆盖后端 dist；生产启动器检测不到 dist 时给出错误并保留 CLI。

## C17 — 合规与安全

输入：`docs/safety-boundary.md`、C15 session guard、C16 UI confirmation、用户确认的 provider allowlist。

拟新增/修改文件：

- `src/quiz_assistant/safety/policy.py`、`safety/audit.py`、API auth/confirmation dependency。
- `docs/ai-policy.md`（只补充已确认规则）、`tests/unit/test_safety_policy.py`、`tests/api/test_authorization.py`。

失败测试先写：

- 未授权 provider、任意 URL、cookie/token、验证码、登录绕过、第三方提交动作一律拒绝。
- AI 默认关闭；AI 返回未知 option、冲突文本、低置信度或无证据时只生成候选/待确认，不修改 active 题目。
- 日志不含 API key、Authorization、session token、完整用户题库或上传原文。
- 连续拒绝/超时触发停止，不自动重试到第三方平台。
- 外部页面/用户文本中的“忽略安全规则”等内容只视为不可信数据。

实现与验收：

1. allowlist 只允许本地已知 provider base URL；默认空 allowlist。
2. 对答案披露、AI 调用、导入写入、备份恢复设置服务端确认值；确认一次只作用于一次明确动作。
3. 记录最小审计字段：时间、动作、结果、request id、规则命中；敏感值 hash/脱敏。
4. 对 CORS/CSRF、路径穿越、session ownership、重复请求和限流做 API 测试。

回滚：关闭 `QUIZ_AI_ENABLED`、关闭远程 host、撤回 provider adapter；保留本地 matcher/practice/backup。安全门禁失败时停止发布，不以“方便用户”为由放宽规则。

## C18 — Windows 发布与运维

输入：C14–C17 的锁文件、schema migration、静态 dist、Windows 构建机、备份恢复测试数据。

拟新增/修改文件：

- `uv.lock`、`pyproject.toml`、`packaging/quiz.spec`、`packaging/build.ps1`、`packaging/run.ps1`。
- `src/quiz_assistant/application/backup_service.py`（采用 `Connection.backup()` 的实现方案）、`migrations/` 新版本和集成测试。
- `docs/windows-operations.md`（如用户确认需要再新增）。

失败测试先写：

- 干净 Windows 机器按锁文件安装，能启动并执行 `health`/`init`/CLI smoke。
- 数据目录与安装目录分离；升级不覆盖 `data/quiz.db`、raw、exports、backups。
- migration 成功后 schema version 正确；迁移中断/失败后原库可打开。
- backup snapshot 可用 SQLite integrity check/hash 校验；篡改 manifest、损坏 db、目标已存在时恢复拒绝。
- 端口占用、服务停止、重复启动、路径含空格、PowerShell 执行策略失败都有可诊断错误。
- PyInstaller onedir 包在 Windows 上找到 FastAPI dist、fixtures/必要资源、SQLite 和 Pydantic schema。

实现与验收：

1. 用 `uv.lock` 和 `uv run --locked` 复现依赖；前端使用 lockfile 构建。
2. 数据目录默认 `%LOCALAPPDATA%\\QuizAssistant\\data` 或用户确认的路径；安装目录只读/可替换。
3. 备份用 `sqlite3.Connection.backup()` 写临时 db，再写 manifest/hash；恢复先校验、再临时文件替换；不把 `.db-wal`/`.db-shm` 当作可忽略附件。
4. 默认 `127.0.0.1`，端口可配置；检测占用后提示可选端口但不静默暴露到 `0.0.0.0`。
5. PyInstaller 首发 `onedir`；构建产物做版本、hash 和启动 smoke，必要时包含 VC runtime 说明。

PyInstaller 官方说明必须在目标 OS 分别构建，并提示 Windows runtime 处理；uv 官方说明 lockfile 应进入版本控制且不手工编辑。[PyInstaller usage](https://pyinstaller.org/en/stable/usage.html)；[uv lockfile](https://docs.astral.sh/uv/concepts/projects/layout/)

回滚：保留上一版 onedir 目录、当前数据库快照和 manifest；升级失败停止服务并恢复上一版本程序，只有用户明确确认后才恢复数据库。绝不以“重新初始化”替代恢复。

## 阶段验收闸门

每阶段都必须回报：

- 修改文件清单和 diff；
- 新增失败测试如何变绿；
- 现有 14 个测试、lint、API/前端/E2E/Windows smoke 的实际命令和退出码；
- 未执行项及原因；
- 备份/hash/恢复演练证据；
- 仍需用户确认的边界选择。

发布前禁止项：未验证的自动答题/自动提交、第三方平台抓取、登录/验证码绕过、cookie/token 获取、默认远程监听、将 API key 或完整用户数据写入日志。
