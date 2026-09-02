# 安全与合规边界

本项目是本地题库与练习辅助工具。默认目标是：用户提供或已授权的题库，在本机完成导入、匹配、练习、复习和备份。以下规则是实现门禁，不是可由模型或前端自行放宽的提示词。

## 1. 明确允许

在用户明确发起且目标属于本机数据时允许：

- 读取用户主动选择的本地 JSON/CSV 文件并做 Pydantic 校验、dry-run、拒绝行报告。
- 在本地 SQLite 中导入、查询、创建练习 session、记录用户亲自提交的答案、更新复习状态。
- 使用现有 deterministic matcher、normalizer、option evidence 返回匹配候选和置信度。
- 用户主动点击“查看答案/确认候选”后，在本项目 UI 中显示题库已有答案或模型候选。
- 创建经过 hash/manifest 验证的本地备份，并在用户二次确认后恢复到指定本地数据库。
- 为本项目自己的 Web 页面编写 Playwright 测试，使用临时数据库、fixture 和本机服务。
- 在用户确认 provider、数据范围、保留期和 allowlist 后，把最小必要题面发给外部 AI provider；默认关闭。

“允许”不等于自动进行。写入题库、答案披露、外部 provider 调用和恢复当前库都必须有清晰的用户动作和可审计结果。

## 2. 明确拒绝

以下请求直接拒绝，不通过改写提示词、代理、浏览器自动化或“仅测试”名义规避：

| 类别 | 拒绝内容 |
|---|---|
| 代答/代提交 | 自动解答正在进行的考试、测验或受限训练平台；代用户点击提交、确认成绩、完成作业/考试流程 |
| 认证绕过 | 绕过登录、验证码、MFA、访问控制、付费墙或设备/组织限制 |
| 凭证与隐私 | 获取、提取或复用 cookie、session token、Authorization header、API key、浏览器密码或其他用户凭证 |
| 未授权抓取 | 将第三方学习/考试页面作为未授权数据源批量抓取，或从任意 URL 自动下载题目/答案 |
| 规避控制 | 注入脚本隐藏自动化、规避速率限制/检测、伪造用户操作、伪造答案事件或篡改服务端 `is_correct` |
| 危险扩展 | 自动执行模型返回的代码/命令；把模型返回 URL 当作下载/访问指令；把模型输出直接写入 active 答案 |

说明：只做本地 UI 的 Playwright 测试是允许的；使用 Playwright 操作第三方考试/学习平台以获取题目、答案、token 或提交答案不允许。

## 3. 需要用户确认的动作

| 动作 | 确认内容 | 默认 |
|---|---|---|
| 显示候选答案 | 展示题目 ID、匹配方法、分数、证据、替代项；用户点击确认后显示 | 不显示答案，仅显示候选状态 |
| 外部 AI 调用 | provider、base URL、model、要发送的字段、是否留存原文、预计网络行为 | AI 关闭 |
| 导入写入 | 文件名、行数、dry-run 结果、拒绝数量、目标 bank | 只预览不写库 |
| 备份恢复 | backup id、schema version、hash、目标库、是否覆盖当前库 | 只创建，不恢复 |
| 远程监听 | host、端口、网络范围、认证方案、风险提示 | 仅 `127.0.0.1` |
| 解释/导出用户记录 | 导出范围、目标文件、是否包含题面/答案/用户答案 | 不自动导出 |

确认必须绑定到一次动作和一次 session，不能由 URL 参数、隐藏字段或模型输出代替。拒绝/取消/超时后不得自动重试该高风险动作。

## 4. AI provider 边界

### 4.1 数据最小化

默认只发送完成候选判断所需的题干、选项和用户显式提供的上下文；不发送整库、用户身份、文件路径、历史全量答案、cookie、token 或本地环境变量。`reasoning_summary` 只作为说明文本，不作为事实或执行指令。

### 4.2 结果处理

外部返回必须经过 Pydantic schema 和 domain 业务校验：

- `answer_keys` 必须是题目中存在的 option key，去重且符合题型数量。
- `answer_texts` 必须逐项精确映射 option key，禁止模型自行替换选项文本。
- confidence 在 0–1；缺失、冲突、低分或 uncertainty 非空时进入 `needs_confirmation`。
- 未通过校验的结果只写最小化失败审计 hash/状态，不写入 active question、correct option 或 review state。
- AI 失败、超时、非 JSON、schema 不兼容只返回可恢复错误，不影响本地练习。

### 4.3 allowlist 与停止条件

首版 allowlist 默认为空；用户确认后才允许配置明确的 HTTPS base URL、model 和超时。以下任一条件发生就停止 provider 调用并要求人工处理：

- provider 不在 allowlist、URL 发生重定向到未允许 host、TLS/证书失败；
- 连续超时、限流、5xx 或响应 schema 失败达到配置阈值；
- 返回要求获取凭证、访问外部页面、执行命令、绕过控制或自动提交；
- 题面包含要求“忽略安全边界”的不可信文本；
- 用户撤销授权或 session 结束。

不得通过循环重试把一次拒绝变成成功；不得把 provider 返回的 URL 作为下一步自动浏览目标。

## 5. Web/API 安全要求

- 默认绑定 `127.0.0.1`；`0.0.0.0` 或局域网访问必须是显式 opt-in，且首版建议直接不支持远程多用户。
- 生产 Vue 与 FastAPI 同源，关闭不必要的 CORS；开发只 allowlist 固定 Vite origin，禁止 `allow_origins=["*"]` 搭配凭证。
- 首版优先使用内存短期 header session；不把 token 放 URL，不写日志，不写数据库。若未来使用 cookie，必须增加 CSRF token、SameSite 和 Origin 校验。
- 所有读写操作在服务端校验 session/资源 ownership；前端隐藏按钮不是授权控制。
- request body、上传文件、`top_k`、`count`、`limit`、路径参数都有长度/范围/文件类型限制；文件操作必须限制在受控 data/raw/exports/backups 根目录。
- API 错误和日志不得包含 API key、Authorization、session token、完整上传原文、完整题库或绝对用户路径。
- 练习起始响应不含正确答案；`is_correct`、`review_state`、`answer_event_id` 只由服务端生成。
- `/api/backups` 的恢复先验证 manifest/hash/schema，再临时写入和原子替换；目标已存在默认拒绝。

FastAPI 文档展示了 bearer token 依赖和 401 行为，但本项目首版不等于已经具备完整多用户 OAuth；若扩展为多用户，必须重新做账户、token 生命周期、撤销和权限设计。[FastAPI security](https://fastapi.tiangolo.com/tutorial/security/first-steps/)

OWASP 将 CSRF 归为利用已认证身份发起状态改变请求，并指出仅限制 POST 不足以防护；OWASP A01 还要求服务端 deny-by-default、复用访问控制、限制 CORS 并记录失败。[OWASP CSRF](https://owasp.org/www-community/attacks/csrf)；[OWASP A01](https://owasp.org/Top10/en/A01_2021-Broken_Access_Control/)

## 6. 审计与留存

只记录实现安全控制所需的最小字段：

```json
{
  "created_at":"2026-09-02T08:00:00+00:00",
  "request_id":"req_01...",
  "action":"ai_candidate|answer_reveal|import_commit|backup_restore",
  "result":"allowed|denied|confirmed|failed",
  "rule":"local_only|allowlist|human_confirmation|schema_validation",
  "question_hash":"sha256...",
  "provider":"local_stub"
}
```

不记录：API key、Authorization、cookie/token、完整题面、完整 AI raw response、用户原始上传文件、浏览器 storage state。审计文件存放在受控 data 目录，按用户确认的留存期轮换；默认不上传云端。

## 7. 人工停止与故障处理

任何用户可通过 UI 的“停止”或关闭本地进程终止正在进行的导入、AI 请求或备份任务。实现必须：

1. 停止后不继续提交外部请求，不自动重启任务；
2. 写出 `stopped_by_user` 或 `failed` 状态，不把半成品当成功；
3. 导入事务回滚，备份临时文件隔离/清理，恢复保留原数据库；
4. 显示可读错误和 request id，不显示秘密；
5. 需要继续时必须由用户重新发起并重新确认。

连续安全拒绝、provider 异常、session 失效或检测到未授权页面时，默认停止并等待人工决定，而不是猜测用户意图。

## 8. 安全验收清单

- [ ] AI 默认关闭，allowlist 默认为空。
- [ ] 没有自动提交、认证绕过、验证码处理、cookie/token 提取或第三方未授权抓取代码。
- [ ] practice payload 不含答案，客户端伪造 `is_correct` 会被忽略/拒绝。
- [ ] `/api` 绑定 localhost；开发 CORS 不是 wildcard。
- [ ] session 不出现在 URL/日志/数据库；cookie 模式有 CSRF 防护。
- [ ] 路径、上传、limit、count 都有限制，文件只能位于受控目录。
- [ ] manifest/hash/schema 校验在恢复前执行，原子替换有失败测试。
- [ ] 日志脱敏测试覆盖 key/token/path/raw response。
- [ ] 14 个既有测试未删除；安全新增测试失败后已变绿。
- [ ] Playwright 只测试本项目本机服务和临时数据。

