# 账户模型、远程 TLS 与用户隔离设计

状态：架构设计稿；Phase A/B 已按本稿实现本地 workspace、账户 session 和基础隔离，Phase C/D 尚未开放。
日期：2026-09-02  
适用范围：Quiz Assistant 的本机单用户、远程多用户和未来团队/租户模式。

## 1. 结论先行

建议采用“两种运行档位、一个资源授权模型”：

| 运行档位 | 身份认证 | 数据库 | 网络边界 | 适用场景 |
|---|---|---|---|---|
| `local` | 当前短期本地 session header | SQLite | 仅 `127.0.0.1` | 个人离线刷题、Windows 单机 |
| `remote` | 服务端会话 + 可选 OIDC | PostgreSQL 优先 | Caddy/反向代理 HTTPS → 回环 FastAPI | 多用户、跨设备、远程访问 |

SQLite 继续作为 local 模式的文件型数据库，不把它直接暴露给客户端，也不让多个远程客户端通过网络文件系统共同打开同一个 `.db` 文件。SQLite 官方明确建议：当许多客户端通过网络访问同一数据库、或需要较多并发写入时，应使用 client/server 数据库；同机应用服务器后面使用 SQLite 仍可成立，但写入会被串行化。[SQLite Appropriate Uses](https://www.sqlite.org/whentouse.html)

远程模式的推荐链路为：

```text
Browser / Mobile client
        │ HTTPS :443
        ▼
Caddy reverse proxy
  - certificate / redirect / HSTS
  - allowed host / request size
        │ HTTP loopback only
        ▼
FastAPI application
  - authentication
  - authorization / workspace scope
  - business services
        │ local socket or private network
        ▼
PostgreSQL (remote)   or   SQLite (local only)
```

不建议首版让 Uvicorn 直接承担公网入口、直接监听 `0.0.0.0`，也不建议将当前单一 `X-Quiz-Session` token 扩展成多用户认证。当前代码中的 session 只适合本机保护，不提供账户、撤销、资源 ownership 或租户隔离。

## 2. 设计目标与非目标

### 2.1 目标

- 用户只能读取和修改自己所属 workspace 的题库、练习、答案事件、复习状态、导入、导出和 AI 审计。
- 管理员权限可被撤销，session 可主动注销、过期和服务端失效。
- 浏览器凭据在整个远程会话中只通过 HTTPS 传输。
- 本机模式不因为增加远程能力而默认开放端口、上传数据或启用外部 AI。
- 从当前 SQLite 数据库迁移到远程模式时，先保留可回滚快照，不原地重写真实数据。
- 关键安全规则有 API contract test、集成测试和部署 smoke test。

### 2.2 非目标

- 不在本设计中实现第三方平台登录绕过、验证码处理、cookie 提取或自动答题/提交。
- 不把数据库文件放到公共文件分享、网络盘或浏览器可下载目录。
- 不以“前端隐藏按钮”代替服务端授权。
- 不在第一版自研完整身份提供商、密码找回邮件平台或多区域高可用系统。

## 3. 账户与身份模型

### 3.1 推荐的身份策略

第一阶段采用“本地账户 + 服务端 opaque session”，OIDC 作为后续可插拔登录方式；不直接采用长期 JWT 作为浏览器 session。

原因：第一方 Web 应用需要服务端立即注销、设备管理、会话审计和权限变更生效，服务端会话比不可撤销的长期 JWT 更容易控制。FastAPI 官方提供 OAuth2、Bearer、JWT、scope 等构件，但这些构件不会自动决定数据库模型、token 生命周期或资源授权，仍需项目自行实现。[FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)

建议字段：

### `users`

| 字段 | 规则 |
|---|---|
| `id` | 随机 UUID/UUIDv7；不使用自增 ID 作为公开身份 |
| `username` | 规范化后唯一；不允许凭此推断其他用户是否存在 |
| `email` | 可选；若作为登录标识，必须验证并唯一 |
| `password_hash` | 仅存 Argon2id hash；永不存明文/可逆密码 |
| `status` | `active`、`disabled`、`pending` |
| `global_role` | 最小化为 `platform_admin` 或 `user` |
| `created_at` / `last_login_at` | UTC 时间；不写入密码、token |

密码哈希使用成熟库，不自行实现算法。FastAPI 官方示例使用 `pwdlib` 的 Argon2，并建议不存在用户时也对 dummy hash 执行校验以降低用户名枚举的时间差。[FastAPI OAuth2/JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)

### `sessions`

| 字段 | 规则 |
|---|---|
| `id` | 随机、不可预测的 session ID；客户端只持有原值 |
| `token_hash` | 数据库只存 hash，不存原 token |
| `user_id` | 外键到 `users` |
| `created_at` / `expires_at` / `last_seen_at` | 绝对过期 + 空闲过期 |
| `revoked_at` | 注销、密码修改、管理员撤销后写入 |
| `client_label` | 可选的人类可读设备名，不采集完整设备指纹 |
| `ip_hash` / `user_agent_family` | 仅用于异常检测，按短留存期清理 |

浏览器默认使用：

- `HttpOnly`、`Secure`、`SameSite=Lax` 的 session cookie；敏感跨站场景改为 `SameSite=Strict`。
- 服务端 synchronizer CSRF token 或 double-submit CSRF token。
- 所有写请求同时校验 CSRF、`Origin`/`Referer` 和 session。
- token 不出现在 URL、日志、错误体、前端分析事件和备份 manifest。

OWASP 要求整个 Web session 使用 HTTPS，而不是只保护登录请求，并建议使用 `Secure` cookie、HSTS 和避免 HTTP/HTTPS 混用。[OWASP Session Management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)

非浏览器客户端可以使用：

- 15 分钟左右过期的 access token；
- 一次性轮换的 refresh token，服务端只存 hash，并检测 refresh replay；
- 设备注销会撤销该设备的 refresh token 链。

不要让 Web 浏览器和移动 API 共用无法撤销的永久 API key。

### 3.2 认证 API 草案

```text
POST /api/auth/login       username/email + password → Set-Cookie session
POST /api/auth/logout      撤销当前 session
POST /api/auth/refresh     仅给非浏览器 access/refresh 客户端
GET  /api/auth/me          返回当前 user 与 workspace membership
GET  /api/auth/sessions    返回当前用户的设备摘要，不返回 token
DELETE /api/auth/sessions/{id}  撤销指定设备 session
```

错误响应统一为模糊信息：`invalid credentials`，不区分“用户不存在”和“密码错误”。登录、注册、密码修改、恢复码都需要独立速率限制和失败审计。

### 3.3 Workspace 与角色

不直接把权限绑定到 `user_id` 的 if/else；使用 workspace membership：

| 角色 | 读取题库 | 导入/编辑 | 查看成员 | 备份恢复 | 管理 provider |
|---|---:|---:|---:|---:|---:|
| `owner` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `editor` | ✓ | ✓ | ✗ | 仅创建 | ✗ |
| `learner` | ✓ | ✗ | ✗ | ✗ | ✗ |
| `viewer` | 仅被授权内容 | ✗ | ✗ | ✗ | ✗ |

首版只实现 `owner`、`editor`、`learner` 三种即可；平台管理员不能默认读所有题面，必须使用独立的 break-glass 操作并留下审计记录。

## 4. 用户隔离与数据模型

### 4.1 资源归属

建议新建 `workspaces` 和 `workspace_memberships`，并给以下现有/新增资源加 `workspace_id`：

```text
workspace
 ├─ question_banks
 │   └─ questions ─ options / tags
 ├─ practice_sessions ─ answer_events
 ├─ review_state
 ├─ imports ─ rejected_rows / raw_objects
 ├─ backups
 ├─ ai_provider_configs
 └─ ai_audits
```

其中 `review_state` 必须同时带 `user_id` 和 `question_id`，因为同一道题的复习间隔属于用户，而不是题库全局状态。`practice_sessions`、`answer_events` 和导出记录也必须保存 `user_id`，不能仅依赖 session ID 推导归属。

### 4.2 强制授权路径

每个 route 使用同一组依赖：

```text
request
  → authenticate_session()
  → load_current_user()
  → resolve_workspace_membership(workspace_id)
  → require_role(action)
  → repository query with workspace_id + ownership predicate
  → application service
```

强制规则：

1. route 不接受客户端传入的 `owner_id`、`is_correct`、`workspace_role` 等只读/派生字段。
2. repository 的读取和写入方法必须显式接收 `ActorContext` 或 `workspace_id`，禁止保留无作用域的 `list_questions()` 给远程 route 使用。
3. 每张租户表的主查询必须带 `workspace_id`；唯一约束改为 `(workspace_id, natural_key)`。
4. 外键和服务层同时校验资源归属，防止“有效 question ID + 另一个 workspace session”组合攻击。
5. 404 与 403 要避免泄露其他 workspace 资源是否存在；跨 workspace 资源统一返回不可访问。
6. 导入临时文件、拒绝行和导出文件使用 `data/workspaces/{opaque_workspace_id}/...`，路径由服务端生成，客户端只能提交 file object ID。

### 4.3 数据库选型

| 方案 | 评价 | 决策 |
|---|---|---|
| 共享 SQLite + `workspace_id` | 可做低并发单机服务，但远程多用户写入受单 writer、文件锁和备份复杂度限制 | 仅 local/小型单机服务 |
| 每用户一个 SQLite 文件 | 物理隔离更直观，适合小规模个人 workspace；跨 workspace 搜索和备份复杂 | 可作为受控过渡方案 |
| PostgreSQL + `workspace_id` | 并发、事务、连接池、备份和远程部署更合适 | remote 推荐 |
| PostgreSQL schema per tenant | 隔离边界强但迁移、连接和运维复杂 | 高敏感/大租户再考虑 |

如果暂时必须用 SQLite 支撑远程试运行，必须满足：数据库永远位于 FastAPI 同机磁盘、客户端永不直连文件、启用 WAL 前做备份/恢复演练、写操作串行化并设置 busy timeout、workspace scope 仍由应用层强制执行。WAL 能改善同机读写并发，但 WAL 依赖同机共享内存索引，不能把网络文件系统当作远程数据库。[SQLite Isolation](https://www.sqlite.org/isolation.html)；[SQLite WAL](https://www2.sqlite.org/wal.html)

### 4.4 备份与恢复隔离

- local：当前用户确认后创建/恢复本机数据库；恢复前保留 pre-restore snapshot。
- remote：默认按 workspace 创建逻辑备份；平台级全量备份只由 owner/受控运维执行。
- 备份包必须包含 schema version、workspace ID、创建时间、文件 hash 和加密/密钥版本，但不包含 session token。
- 下载备份前再次执行 workspace authorization；禁止通过可猜测路径访问其他 workspace 备份。
- 恢复到现有 workspace 前创建新 revision，并默认拒绝跨 workspace 恢复。
- 覆盖恢复必须是显式 UI action + 服务端一次性 confirmation nonce；不能用固定字符串长期授权。

## 5. 远程 TLS 与部署边界

### 5.1 监听策略

```text
local 默认：FastAPI 127.0.0.1:8765
remote：FastAPI 127.0.0.1:8765 + Caddy 0.0.0.0:443
```

`QUIZ_REMOTE_ENABLED=true` 只能在以下条件同时满足时启动：

- 显式配置公开/内网 hostname；
- 配置 TLS 终止代理或完整证书路径；
- 配置首个 owner 创建方式；
- 配置 trusted proxy 列表；
- 配置 PostgreSQL 或明确批准的同机 SQLite 过渡模式；
- 配置备份目录、日志留存和速率限制；
- 启动日志明确显示 remote mode，不打印秘密。

否则进程拒绝以非回环地址启动。Uvicorn 虽然提供 `--ssl-keyfile`、`--ssl-certfile` 等参数，但本项目更推荐把证书生命周期交给专用反向代理，Uvicorn 只服务受控的回环上游。[Uvicorn Settings](https://www.uvicorn.org/settings/)

### 5.2 Caddy 反向代理方案

Caddy 配置方向：

```caddyfile
quiz.example.com {
    encode gzip
    reverse_proxy 127.0.0.1:8765
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "camera=(), microphone=(), geolocation=()"
    }
}
```

上线前必须先确认：域名 DNS、证书续期、端口 80/443、防火墙、反代真实 IP header、FastAPI trusted proxy 和 HSTS 回滚方案。Caddy 官方文档说明，配置有效 hostname 时可自动申请/续期证书并将 HTTP 重定向到 HTTPS；本地 hostname 则使用本地 CA，其他设备必须显式信任该 CA。[Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https)；[Caddy HTTPS Quick-start](https://caddyserver.com/docs/quick-starts/https)

公网部署不使用 `internal` 自签证书作为用户体验方案；内网部署可以使用内部 CA，但必须把根证书安装和轮换作为运维步骤，不能让用户忽略浏览器证书错误。

### 5.3 TLS 验收清单

- HTTP 只用于受控 redirect 或 ACME challenge，不承载登录/业务响应。
- cookie 带 `Secure`、`HttpOnly`、适当 `SameSite`；登录后重新生成 session ID。
- HSTS 在证书、域名和子域确认后再启用；预加载不作为第一版要求。
- 只允许 TLS 1.2+，优先使用代理安全默认值，不手工复制过时 cipher 列表。
- 设置 CSP，至少限制 script、connect、frame、base URI；前端不允许任意远程脚本注入。
- FastAPI 仅信任来自已知反代的 `X-Forwarded-*`；外部用户可伪造的 header 不参与授权或审计身份判断。
- `TrustedHostMiddleware`/反代 host allowlist 拒绝未知 Host，避免 Host header 注入。
- 不把 session、Authorization、密码、AI key 写入 access log、error log、trace 或 analytics。
- 对登录、导入、查询、答题、备份恢复分别设置 body/频率/并发上限。

OWASP TLS 指南指出，未加密页面或混合内容可能暴露 session token，也可能允许响应被篡改；ASVS 5.0 可作为认证、会话、访问控制、输入和部署验收基线。[OWASP TLS](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html)；[OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)

## 6. API 改造边界

### 6.1 保留与替换

| 当前能力 | local 模式 | remote 模式 |
|---|---|---|
| `X-Quiz-Session` | 暂时保留，仅回环地址 | 禁止作为多用户身份凭证 |
| `/api/health` | 匿名可访问，隐藏路径 | 只返回服务状态/版本，不泄露基础设施 |
| `/api/banks`、`/api/queries` | 当前 session guard | `current_user + workspace membership` |
| practice/answer/review | 当前本地 session | session owner + user/workspace scope |
| imports/backups | 本地确认 | workspace role + CSRF + confirmation nonce |
| AI provider | 默认关闭 | workspace allowlist + 管理员授权 + 细粒度审计 |

### 6.2 需要新增的公共依赖

建议新增以下模块，而不是在每个 route 内手写：

```text
src/quiz_assistant/api/auth.py
src/quiz_assistant/api/dependencies.py
src/quiz_assistant/api/authorization.py
src/quiz_assistant/api/csrf.py
src/quiz_assistant/application/account_service.py
src/quiz_assistant/application/workspace_service.py
src/quiz_assistant/infrastructure/session_store.py
src/quiz_assistant/infrastructure/postgres.py
```

`application/*_service.py` 继续承载业务动作；route 只负责认证依赖、DTO、错误映射和 request ID。任何需要判断“这个资源属于谁”的逻辑必须发生在服务端 repository/application 层，而不是 Vue client。

## 7. 迁移与发布阶段

### Phase A：本机兼容层

1. 新增 `local-default` workspace 和不可删除的本地 owner 概念，但不改变现有 SQLite 文件内容。
2. 为现有表增加 nullable `workspace_id`/`user_id` 迁移字段，先回填到 local owner，回填前后做 hash 和 row count 校验。
3. 将当前 `X-Quiz-Session` 映射为 local actor，不把它当作远程账户 token。
4. 增加 ownership 测试：错误 workspace/session 不能读取、答题或恢复。

### Phase B：账户与会话

1. 引入 password hash、opaque session、注销、过期、撤销、登录速率限制。
2. 先实现单 workspace 多账户；默认禁止公开注册，owner 创建邀请或本机 bootstrap。
3. 将 Vue client 改为 cookie session + CSRF；非浏览器 client 单独走 bearer/refresh 方案。
4. 完成密码修改时全量撤销 session、登录失败模糊错误和审计脱敏。

### Phase C：远程只读试运行

1. PostgreSQL schema/migration 与 SQLite 导出/导入工具完成。
2. Caddy staging 域名启用 HTTPS，FastAPI 只监听 loopback。
3. 只开放 health、banks、查询和 review 读取，禁止导入、备份恢复和外部 AI。
4. 用两个 workspace、三个用户做越权、session 撤销、TLS、日志脱敏和备份恢复演练。

### Phase D：受控写入

1. 开放练习/答题/复习写入，验证每条事件的 user/workspace scope。
2. 开放导入 dry-run，再开放确认写入；原始上传文件按 workspace 隔离并限时清理。
3. 开放 workspace owner 备份；恢复前强制 pre-restore snapshot 和一次性 confirmation nonce。
4. 外部 AI 每个 workspace 单独 allowlist、留存期和脱敏配置，默认关闭。

### 回滚

- 任一安全测试失败，关闭 remote feature flag，继续使用 local CLI/SQLite。
- 数据库迁移失败时保留原 SQLite/PostgreSQL 版本和 manifest，不通过“重新初始化”修复。
- TLS 证书、代理或认证异常只停止远程入口，不自动降级为明文公网 HTTP。
- 远程写入发布前保留只读版本程序和数据库快照；回滚程序不等于回滚数据库，后者必须独立确认。

## 8. 必须先写的测试

### 认证/会话

- 错误用户名和错误密码返回相同错误，不暴露账户存在性。
- 密码不出现在日志、异常、数据库备份和前端状态。
- session 过期、注销、改密、管理员撤销立即失效。
- cookie 缺失、CSRF 缺失、Origin 不允许的写请求均拒绝。
- refresh token 复用时撤销该 token family，不自动重试。

### 用户隔离

- user A 不能读取 user B 的 bank/question/session/review/import/backup/AI audit。
- user A 不能把 user B 的 question ID 放入自己的 answer session。
- editor 不能管理成员、provider 或恢复数据库。
- owner 被移除/禁用后已有 session 失效。
- 导出、备份下载和恢复均验证 workspace membership，路径不可穿越。

### TLS/部署

- remote flag 未开启时监听地址只能是 `127.0.0.1`。
- remote flag 开启但没有可信 TLS/反代配置时启动失败。
- HTTP 不返回登录页/业务 JSON，只返回 redirect 或 challenge。
- 未知 Host、伪造 forwarded header、错误 scheme 都不能绕过授权或审计。
- Caddy/应用重启、证书轮换、代理不可达时给出可诊断错误，不泄露密钥。

### 数据与回滚

- SQLite local 数据可迁移到 local-default workspace，行数、hash、题目答案和复习状态一致。
- PostgreSQL 导入失败事务回滚；旧数据仍可读。
- workspace 级备份不能恢复到另一个 workspace。
- 恢复覆盖前自动生成 pre-restore snapshot；恢复失败原库仍可打开。

## 9. 待最终确认的部署参数

本设计已经给出默认决策，但真正实施远程模式前仍需要明确：

| 参数 | 默认建议 |
|---|---|
| 仓库/部署是否公网可见 | private / 内网优先 |
| 登录方式 | 本地账户 + opaque session；后续接 OIDC |
| 是否允许公开注册 | 否，owner 邀请 |
| 远程数据库 | PostgreSQL |
| TLS 终止 | Caddy；FastAPI loopback |
| 备份加密 | workspace key envelope；运维密钥不进仓库 |
| AI provider | workspace allowlist，默认关闭 |
| 账户删除 | 软删除 + 资源保留期，物理删除需二次确认 |
| 平台管理员 | 只做运维，不默认读取题面；break-glass 必须审计 |

## 10. 参考依据

- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [FastAPI OAuth2 with Password and Bearer JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [Uvicorn Settings / HTTPS](https://www.uvicorn.org/settings/)
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP Transport Layer Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html)
- [OWASP ASVS 5.0](https://owasp.org/www-project-application-security-verification-standard/)
- [SQLite Appropriate Uses](https://www.sqlite.org/whentouse.html)
- [SQLite Isolation](https://www.sqlite.org/isolation.html)
- [SQLite WAL](https://www2.sqlite.org/wal.html)
- [Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https)
