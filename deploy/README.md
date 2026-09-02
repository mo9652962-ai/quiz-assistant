# Phase C remote read-only pilot

本目录只描述受控的远程试运行入口。应用的数据访问入口已经支持以 PostgreSQL URL
作为 database target：设置 `QUIZ_DATABASE_URL=postgresql://...` 后，FastAPI、账户/session、
题库查询和 repository 会通过 PostgreSQL 适配层访问数据库。真实 staging migration/import
仍需在部署环境执行并留存行数、隔离和回滚证据。

## 启动边界

FastAPI 必须只监听 `127.0.0.1:8765`，公开 HTTPS 入口交给 Caddy。远程配置必须同时满足：

- `QUIZ_REMOTE_ENABLED=true` 和 `QUIZ_REMOTE_READ_ONLY=true`；
- `QUIZ_REMOTE_PUBLIC_ORIGIN` 是 HTTPS origin；
- `QUIZ_REMOTE_TLS_PROXY_ENABLED=true` 且配置可信代理列表；
- `QUIZ_REMOTE_ALLOW_SQLITE=true` 仅可用于同机磁盘上的临时试运行；
- 外部 AI 保持关闭。

不满足这些条件时，`quiz_assistant.server:app` 在导入阶段拒绝启动。远程写入、导入、
备份恢复和外部 AI 属于后续 Phase D，不由前端按钮控制，而由 API 服务端门禁控制。

## 本机试运行

1. 复制项目根目录的 `.env.remote.example` 为本机环境配置，并替换示例域名。
2. 在项目根目录执行：

   ```powershell
   $env:PYTHONPATH = "src"
   python -m uvicorn quiz_assistant.server:app --host 127.0.0.1 --port 8765
   ```

3. 将 `deploy/Caddyfile.example` 中的域名替换为真实域名，加载 Caddy 配置。
4. 先验证 `https://<domain>/api/health`、登录、题库读取、查询和复习读取；确认
   `POST /api/practice/sessions`、`POST /api/imports` 和 `POST /api/backups` 均返回
   `403` 且错误码为 `remote_read_only`。

## 数据迁移

先对本机数据库生成不含 session 的迁移快照：

```powershell
quiz snapshot-export --db data/quiz.db --out work/migration.snapshot.json
```

目标数据库必须是新数据库或只包含初始化 bootstrap 数据；导入是事务性的、幂等的，
不会导入任何 session token/hash。PostgreSQL 目标使用以下命令：

```powershell
quiz postgres-import-snapshot `
  --database-url "$env:QUIZ_DATABASE_URL" `
  --source work/migration.snapshot.json
```

PostgreSQL schema migration 使用：

```powershell
python -m pip install -e ".[remote]"
quiz postgres-migrate --database-url "$env:QUIZ_DATABASE_URL"
```

迁移 runner 会创建 `schema_migrations`，按 `migrations/postgres/*.sql` 的数字前缀顺序
执行，并在任意 migration 失败时 rollback。`postgres-import-snapshot` 会先确保 migration
完成，再按外键依赖顺序导入快照、重置 serial sequence，并在失败时 rollback。应用启动时
也会幂等执行 migration 和本地 bootstrap；切换到 PostgreSQL 前必须在 staging 完成数据行数、
workspace 隔离、登录/session 撤销和恢复演练。

本地部署 smoke test：

```powershell
$env:PYTHONPATH = "src;work/phase-c-deps"
python -m pytest tests/deployment/test_remote_smoke.py -q
```

如果已经拿到专用 staging PostgreSQL 连接，可使用受保护的脚本执行真实 migration；需要显式
传入 `-ConfirmStagingWrite`，避免把迁移误指向生产库。连接串只从环境变量读取，不会作为命令
行参数打印：

```powershell
$env:QUIZ_DATABASE_URL = "postgresql://<staging-user>:<password>@<staging-host>:5432/<database>"
.\scripts\run_postgres_staging_smoke.ps1 `
  -ConfirmStagingWrite `
  -ImportSnapshot `
  -SnapshotPath .\work\migration.snapshot.json
```

未设置连接串、连接串不是 PostgreSQL、未显式确认写入或快照文件不存在时，脚本会在连接数据库
前停止。它只执行 staging schema migration 和可选的快照导入，不会打开远程 API 写入、备份恢复
或 workspace AI provider。

不要把 SQLite 文件放到网络共享盘，不要让客户端直连数据库文件，也不要用已知的
`local-owner/local-owner` 凭据作为公网账户。真正远程上线前还需要完成首个远程 owner
创建/轮换、CSRF、速率限制、未知 Host 拒绝和日志/备份演练；本机没有可用 staging 实例时，
不得把本地模拟测试当作真实 migration/import 证据。
