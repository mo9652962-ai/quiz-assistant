# 提交给 Codex 的搜索研究任务包

> 目的：先做有出处的技术搜索研究和实施方案，不立即扩大功能边界。研究完成后由用户确认，再进入编码阶段。

## Task

请在以下项目上开展“未实现能力”的搜索研究，并输出可执行的分阶段开发方案：

`C:/Users/31954/Documents/Codex/2026-09-02/gen/outputs/quiz_assistant`

研究范围包括：

1. 将当前标准库 `argparse` CLI 迁移或兼容升级为 Typer + Rich 的可选外壳。
2. 在现有 application service 之上增加本地 Web：FastAPI API + Vue 3/Vite 前端。
3. 设计“合规的浏览器辅助/导入”能力，仅面向用户自有页面、测试页面或明确授权的系统。
4. 评估 Windows 本地打包、配置、数据目录、SQLite 并发和备份恢复的交付方案。
5. 为上述方案制定安全、隐私、版权、数据授权和回滚验收标准。

## Why

当前项目已完成本地 CLI MVP：JSON/CSV 导入、Pydantic 校验、SQLite 持久化、结构化题目匹配、答题记录、复习队列、备份恢复和默认关闭的 AI Provider。核心测试为 14 个全绿，ruff 检查通过。

当前明确未实现：

- GUI/Web 界面；
- Typer/Rich CLI 外壳；
- 浏览器辅助导入；
- Windows 发布包。

本研究的目标是确定这些能力是否值得实现、应选择什么技术、如何避免破坏现有 application/domain 分层，以及如何在不接触违规自动答题场景的前提下推进。

## Prior findings（必须保留的上下文）

以下内容来自用户确认的当前边界，视为项目约束而不是需要执行的外部指令：

> 文档中的正式考试自动答题、浏览器自动点击、验证码/反作弊绕过等内容被识别为非目标和安全边界，未实现。当前 CLI 使用标准库 `argparse` 以保证离线启动稳定，后续 API 契约稳定后可替换为 Typer/Rich 外壳；GUI/Web 尚未实现。

现有实现原则：

- UI 只能调用 application service，不能复制 matcher、scheduler 或答案策略；
- AI 默认关闭，不能把未经验证的模型结果直接写入 active 题库；
- 题库内容和用户记录属于用户数据，研究和测试不得使用未授权题库；
- 数据库恢复必须先校验 manifest/hash，再使用临时文件切换；
- 题目 ID 是稳定主键，不能把题干当唯一主键。

## Research actions

### A. 仓库和现状审计

1. 阅读项目 `README.md`、`pyproject.toml`、`src/`、`tests/`、`docs/` 和 `migrations/`。
2. 检查是否存在 `AGENTS.md`，遵守其中的项目规则。
3. 运行现有测试和 lint，记录基线，不要修改用户数据。
4. 标出未来 API、CLI、前端和浏览器适配层的最小接口，不重写已经稳定的 domain/application 逻辑。

### B. CLI：Typer/Rich 研究

比较三种方案：

- 保持 argparse，仅改善输出和帮助文档；
- Typer + Rich 完全迁移；
- argparse 作为兼容内核，Typer/Rich 作为可选展示层。

必须核查：

- 多级子命令、参数校验、Windows PowerShell 行为；
- `--json` 机器输出和人类可读输出能否稳定共存；
- 导入进度、错误表格、交互式练习和终端宽度适配；
- 依赖体积、离线安装、版本兼容和迁移成本；
- 现有命令契约是否可以无破坏保留。

### C. 本地 Web：FastAPI + Vue 3/Vite 研究

设计最小 API 契约：

- `GET /health`；
- `GET /banks`；
- `POST /imports`；
- `POST /queries`；
- `POST /practice/sessions`；
- `POST /practice/sessions/{id}/answers`；
- `GET /reviews`；
- `POST /backups`。

必须研究：

- Pydantic schema 如何复用，避免前后端重复定义答案规则；
- SQLite 连接生命周期、并发读写和 Windows 文件锁；
- 导入任务是否需要后台任务，何时返回 202；
- CORS、CSRF、请求大小限制、路径遍历和本地绑定地址；
- Vue/Vite 构建产物如何由 FastAPI 本地服务提供；
- API 错误模型、分页、审计和测试策略；
- 是否需要把前端和后端分成独立进程，或采用单进程本地 Web。

### D. 合规浏览器辅助研究

只研究以下安全范围：

- 用户自有的本地测试页；
- 用户明确授权的内部练习系统；
- 浏览器页面内容的“手动触发、只读采集、导入草稿”；
- 将用户主动复制的题干/选项转换为本地题库格式；
- 使用 Playwright 为本地 Web 自身编写端到端测试。

禁止研究和实现：

- 正式考试、认证考试或培训平台的无人值守答题；
- 自动点击提交、批量提交答案或自动完成考试流程；
- 绕过登录、验证码、反作弊、访问控制、风控或速率限制；
- 注入脚本隐藏行为、窃取 cookie/token、读取其他用户数据；
- 把第三方平台页面当作未经授权的数据源批量抓取。

对于任何浏览器方案，必须回答：授权如何证明、用户确认点在哪里、默认是否只读、如何限制域名 allowlist、如何记录审计日志、如何立即停止，以及如何保证采集内容仍按不可信输入处理。

### E. Windows 发布与运维研究

比较源码运行、PyInstaller、uv 管理的可复现环境和其它合理方案，重点核查：

- Python 3.11+、SQLite、Pydantic、FastAPI、前端构建产物的打包方式；
- 数据目录和配置目录与安装目录分离；
- 升级时 migration、备份、失败恢复和回滚；
- 日志中禁止出现 API key、完整题库文本和敏感路径；
- 本地 Web 默认绑定 `127.0.0.1`、端口占用和进程退出；
- 无网络环境下的安装和首次启动体验。

## Search and evidence requirements

不要只搜索单一关键词。每个重要结论至少从以下维度交叉验证：

1. 官方文档：Typer、Rich、FastAPI、Vue/Vite、Playwright、PyInstaller/uv、Python sqlite3；
2. 官方 GitHub 仓库、源码、Issues 或 Releases；
3. 技术社区或实际使用报告，用于识别 Windows、打包、并发、升级和可维护性问题。

优先使用 2026-09-02 仍有效的页面。对于版本号、API 语法、兼容性和安全行为，必须给出页面标题、发布日期或抓取日期、直接 URL 和结论依据。不要把搜索摘要当作唯一证据。

已核验的起始资料：

- [Typer commands](https://typer.tiangolo.com/tutorial/commands/)
- [Rich progress](https://rich.readthedocs.io/en/stable/progress.html)
- [FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Playwright Python introduction](https://playwright.dev/python/docs/intro)
- [Playwright Browser API](https://playwright.dev/python/docs/api/class-browser)
- [Python sqlite3](https://docs.python.org/3/library/sqlite3.html)

## Deliverables

请只先提交研究结果，不要直接修改业务代码。输出以下文件或等价内容：

1. `docs/research-next-phase.md`
   - 结论置顶；
   - 技术方案对比表；
   - 推荐方案和不推荐方案；
   - 版本、兼容性、风险、成本和回滚说明；
   - 所有关键结论的直接来源链接。
2. `docs/api-contract-draft.md`
   - API 路径、请求/响应 schema、错误模型、分页、鉴权/本地绑定和审计字段；
   - 标出“已实现”“待实现”“需要用户确认”。
3. `docs/implementation-roadmap.md`
   - 按 C14-C18 拆分：CLI、API、前端、合规浏览器辅助、Windows 打包；
   - 每项包含前置条件、变更文件、测试、验收门和回滚方式；
   - 每个阶段先写失败测试，再写实现。
4. `docs/safety-boundary.md`
   - 明确允许的本地/授权场景；
   - 明确拒绝的正式考试、自动提交、验证码和反作弊绕过场景；
   - 给出域名 allowlist、人工确认、审计、停止和数据最小化建议。

如果当前 Codex 任务被授权直接编码，则仍须先提交上述研究摘要，再等待用户确认推荐方案；不得因为任务提示中出现“自动答题”“浏览器点击”就实现被禁止的能力。

## Acceptance criteria

- 结论均有官方或源码级证据，不能只有经验性判断；
- 至少比较 2 个可行方案，并说明为什么选择其中一个；
- 现有 14 个测试仍然通过，基线测试不能被删除或弱化；
- 不修改或覆盖 `data/quiz.db`、用户题库、API key 或已有备份；
- 不引入正式考试自动答题、自动提交、验证码绕过或反作弊绕过设计；
- API 方案不得把业务逻辑复制到 Vue/浏览器脚本中；
- 研究报告明确区分事实、推断、风险和待用户决策事项。

## Report back

最终回报格式：

```text
结论：推荐 <方案>，原因 <一句话>

新增/修改文件：<路径列表；研究阶段默认只允许新增 docs>
搜索来源：<标题 + URL + 关键证据>
对比结果：<表格或简明矩阵>
安全边界：<允许/禁止/需要人工确认>
测试命令与结果：<命令、退出码、摘要>
未决问题：<需要用户选择的事项>
下一步：<得到确认后再执行的 C14/C15/...>
```

