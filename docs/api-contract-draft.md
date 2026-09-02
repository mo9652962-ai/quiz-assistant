# API Contract Draft

状态：研究草案，C15 实现前需要用户确认认证、答案披露和远程访问策略。  
默认部署：FastAPI 与 Vue 构建产物同进程，监听 `127.0.0.1`；开发环境为 Vite `http://127.0.0.1:5173` 代理 `/api`。

当前实现状态：C15 已落地 FastAPI app、`/api/health`、`/api/banks`、`/api/queries`、practice session/answer、`/api/reviews`、`/api/imports`、`/api/backups`；C16 已加入 Vue Router 页面、Vite `/api` proxy、统一 API client、加载/错误/空态和本机 Playwright smoke。当前使用本地 session token 测试/保护写操作。多用户账户、远程网络暴露和 SQLite 在线备份升级属于后续阶段。

## 1. 通用约定

Base path：`/api`。JSON 使用 UTF-8；时间使用 UTC ISO 8601；ID 使用字符串；列表默认按稳定 ID/时间排序；分页首版使用 `limit`，不得让客户端任意拼 SQL。

状态码：

| 状态码 | 用途 |
|---:|---|
| 200 | 查询、同步导入/备份成功 |
| 201 | 创建 session 成功 |
| 202 | 仅在导入/备份实测需要异步时使用，响应必须带 `job_id` |
| 400 | 参数组合或业务状态非法 |
| 401 | 缺少/无效本地会话 |
| 403 | 会话存在但不允许该动作，或需要显式确认 |
| 404 | bank/question/session/job/backup 不存在 |
| 409 | 版本冲突、目标库已存在、重复或正在迁移 |
| 413 | 上传超过配置上限 |
| 422 | Pydantic 输入校验失败 |
| 500 | 未预期内部错误；不得返回 secret、绝对路径或 provider 原始响应 |

统一错误体：

```json
{
  "code": "validation_error",
  "message": "request validation failed",
  "details": [{"field": "count", "reason": "must be between 1 and 100"}],
  "request_id": "req_01..."
}
```

成功响应可带 `request_id`，但不返回本机绝对路径。FastAPI 默认会为 schema 生成 OpenAPI；路由错误映射应统一包成上述错误体，而不是让前端依赖不同异常格式。

## 2. 核心 schema

### 2.1 `QuestionSummary`（不含答案）

```json
{
  "id": "eng-000001",
  "bank": "english-basic",
  "version": 1,
  "type": "single_choice",
  "stem": "Which sentence is grammatically correct?",
  "options": [
    {"key": "A", "text": "He go to school."},
    {"key": "B", "text": "He goes to school."}
  ],
  "tags": ["grammar"],
  "status": "active"
}
```

`Option` 在练习开始和 review 队列中不得含 `correct`；服务端内部仍复用当前 Pydantic `Question`。答案字段只在显式允许的结果中出现。

### 2.2 `MatchResult`

```json
{
  "status": "high_confidence",
  "question_id": "eng-000001",
  "answer_keys": ["B"],
  "answer_texts": ["He goes to school."],
  "method": "normalized_exact",
  "score": 0.98,
  "evidence": ["normalized stem uniquely matches"],
  "normalizer_version": "v1",
  "alternatives": []
}
```

服务端必须调用当前 `query_service.query_questions()` 和 domain matcher。`needs_confirmation` 时不得被前端静默转成 `high_confidence`；如果用户未确认，UI 只展示候选、分数、证据和替代项。

### 2.3 `PracticeSession`

```json
{
  "id": "session-uuid",
  "mode": "practice",
  "started_at": "2026-09-02T08:00:00+00:00",
  "questions": [{"id": "q-1", "type": "single_choice", "stem": "...", "options": []}],
  "answer_reveal": "after_user_confirmation"
}
```

### 2.4 `AnswerSubmission` / `AnswerResult`

请求：

```json
{"question_id":"q-1","answer":"B","elapsed_ms":12000,"reveal_answer":false}
```

响应：

```json
{
  "question_id":"q-1",
  "is_correct":true,
  "answer_event_id":42,
  "review_state":{"due_at":"2026-09-03T08:00:00+00:00","repetitions":1,"interval_days":1.0,"ease":2.5,"lapses":0},
  "answer_revealed":false,
  "correct_keys":null,
  "explanation":null
}
```

若 `reveal_answer=true`，仍需服务端判断本次会话是否有用户明确确认；否则返回 403 `confirmation_required`。这不是自动提交：答案必须来自本次用户请求，后端才写 `answer_events` 和 `review_state`。

### 2.5 `ImportReport`

```json
{
  "source_name":"sample_questions.json",
  "dry_run":true,
  "total":3,
  "imported":2,
  "skipped_duplicate":0,
  "rejected_count":1,
  "rejected":[{"row_number":3,"error":"...","raw":{}}]
}
```

`raw` 只用于用户刚上传文件的诊断，不能被日志重复记录；响应不返回上传内容之外的本机路径。大文件异步时，`POST /imports` 只返回 `{job_id,status,source_name}`，再由受控的任务查询接口读取状态；首版优先同步并设置大小/行数上限。

### 2.6 `BackupReport`

```json
{
  "backup_id":"20260902T080000Z",
  "format_version":1,
  "schema_version":2,
  "file_count":1,
  "sha256":"...",
  "verified":true,
  "created_at":"2026-09-02T08:00:00+00:00"
}
```

不返回备份目录绝对路径；UI 只显示受控的 backup id 和相对状态。恢复前服务端必须验证 manifest/hash、schema 兼容性并写入临时文件，再原子替换。

## 3. 路由草案

### `GET /api/health`

认证：本机探活可匿名；不返回数据库路径。  
响应：`{"status":"ok","schema_version":2,"ai_enabled":false}`。  
失败：迁移进行中返回 409 或 `status: "degraded"`，不接受写请求。

### `GET /api/banks`

认证：本地会话。  
查询：`status=active|all`（默认 active）、`limit`。  
响应：`{"items":[{"name":"english-basic","version":1,"question_count":2,"active_count":2}],"total":1}`。  
业务来源：`query_service`/repository，只读。

### `POST /api/imports`

认证：本地会话；必须带用户从导入页发起的明确动作。  
请求：`multipart/form-data`：`file`、`dry_run`、可选 `bank`。上传 MIME 和后缀只作为初筛，实际内容必须经过现有 Pydantic 校验。  
响应：同步 `200 ImportReport`，或异步 `202 job`。  
副作用：非 dry-run 才写库；拒绝行写入受控诊断文件。禁止接收 URL 作为“导入源”，避免把服务变成抓取器。

### `POST /api/queries`

请求：

```json
{"text":"Which sentence is grammatically correct?","options":[],"top_k":5,"bank":"english-basic","reveal":"candidate"}
```

校验：`top_k` 1–20；`reveal` 为 `none|candidate`，默认 `none`。  
响应：`MatchResult`；未达阈值返回 `no_match`。`reveal=candidate` 仍受 `answer_policy` 和待确认状态控制。  
业务来源：`query_service.query_questions()`，不在路由层复制 matcher。

### `POST /api/practice/sessions`

请求：`{"bank":"english-basic","tag":"grammar","count":10,"mode":"practice"}`。  
校验：`count` 1–100；只选 active 题；session 由后端生成 UUID。  
响应：`201 PracticeSession`，题目不含正确答案。  
业务来源：`practice_service.start_practice()` + repository `create_session()`。

### `POST /api/practice/sessions/{session_id}/answers`

认证：本地会话，并校验 session owner/状态。  
请求/响应：见 `AnswerSubmission`/`AnswerResult`。  
业务来源：`practice_service.submit_answer()`；后端忽略客户端传入的 `is_correct`、`correct_keys`、`review_state` 等未知或只读字段。  
禁止：代用户批量提交、重放不属于当前 session 的 question、用请求体覆盖历史答案。

### `GET /api/reviews`

查询：`wrong=true`、`due=true`、`limit=20`，至少一个筛选条件可选；默认不泄露答案。  
响应：`{"items":[{"question":QuestionSummary,"due_at":"...","repetitions":1,"interval_days":1.0,"ease":2.5,"lapses":0}],"total":1}`。  
业务来源：`review_service.review_queue()`。

### `POST /api/backups`

请求：

```json
{"action":"create"}
```

创建返回 `200 BackupReport`；恢复请求必须为：

```json
{"action":"restore","backup_id":"20260902T080000Z","confirm":"RESTORE_CURRENT_DATABASE","force":false}
```

恢复要求：本地会话、二次确认、manifest/hash 校验、schema 兼容性检查、目标文件存在时默认 409；`force` 只能在明确确认后启用。恢复失败必须保留原库并删除/隔离临时文件。  
业务来源：`backup_service`，C18 改为 `sqlite3.Connection.backup()` 快照。

## 4. 认证、授权、CORS 与 CSRF

首版建议采用“单用户、本机、每次启动的短期会话 header”，例如 `X-Quiz-Session`；token 只存内存，不写题库、不进日志、不作为 URL 参数。创建/展示会话时由本机控制台或首屏要求用户明确确认。是否改为持久登录账户是待确认项。

- 生产只监听 `127.0.0.1`；Uvicorn 官方默认 host 就是 `127.0.0.1`，`0.0.0.0` 才会暴露到本地网络，因此后者必须是显式 opt-in 且伴随强警告。[Uvicorn settings](https://www.uvicorn.org/settings/)
- 生产前端由同一个 FastAPI origin 提供，默认不需要 CORS；开发只 allowlist `http://127.0.0.1:5173` 与必要的 `http://localhost:5173`，不使用 `*`。
- 若使用 cookie session，必须新增 CSRF token、SameSite/Origin 校验；若坚持 header bearer，禁止把 token 放 cookie，并拒绝跨 origin 的写请求。OWASP 将 CSRF 定义为利用已认证身份迫使用户执行状态改变请求，且仅 POST 不是防护措施。[OWASP CSRF](https://owasp.org/www-community/attacks/csrf)
- 任何读取其他用户、任意 bank、任意文件路径的 capability 都必须在服务端授权；不能只靠隐藏按钮或前端过滤。OWASP A01 明确要求 deny by default、服务端复用访问控制和记录失败。[OWASP A01](https://owasp.org/Top10/en/A01_2021-Broken_Access_Control/)
- 账号、多用户、远程 host、代理转发和 HTTPS 不属于默认首版授权；用户确认后才能扩展。

## 5. 页面与调用映射

| 页面 | API | 权限/关键交互 |
|---|---|---|
| Dashboard | `/health`, `/banks`, `/reviews` | 只读；显示数据库/迁移状态，不显示绝对路径 |
| Import | `POST /imports` | 用户选本地文件、预览 dry-run、确认后写入；显示拒绝行 |
| Search/Answer | `POST /queries` | 显示匹配证据/替代项；候选答案需按策略确认 |
| Practice | `POST /practice/sessions`、`.../answers` | 初始题目无答案；每次提交来自用户输入；答案披露需显式操作 |
| Review | `GET /reviews` + practice answers | wrong/due 过滤；复习和答题仍走同一 application service |
| Settings/Backup | `POST /backups` | 创建可直接操作；恢复必须显示 backup id、hash、二次确认 |

## 6. 实现分类

### C15 必须实现

- FastAPI app factory、lifespan 中的 schema readiness 检查、统一错误体、Pydantic request/response schema。
- `/health`、`/banks`、`/queries`、practice session/answer、`/reviews` 的同步路径。
- `127.0.0.1` 默认绑定、开发 CORS allowlist、header session guard、正确答案不进入 practice start payload。

### C16 必须实现

- Vue Router 页面、API client、loading/error/empty states、导入 dry-run 确认、答案确认对话框。
- Vite dev proxy 与生产 dist 托管；前端 E2E 只访问本机测试服务和 fixture。

### C18 再实现

- `/backups` 的在线快照、schema/version/hash 反馈、恢复前确认与原子替换。
- 202 job 只在性能测试证明需要后加入，且必须有 job 状态和失败可见性。
