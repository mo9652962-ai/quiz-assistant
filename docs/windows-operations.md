# Windows 运维与发布

## 构建 onedir 包

构建机需要先安装 Python 3.11+、Node.js 和本机 Tesseract OCR。项目 OCR 依赖和 PyInstaller 安装到项目虚拟环境：

```powershell
cd C:\path\to\quiz_assistant
py -3.11 -m venv .venv
uv sync --locked --extra dev --extra ocr --extra package
Push-Location frontend
npm ci
Pop-Location
.\packaging\build.ps1
```

如果尚未安装 uv，可先按 uv 官方 Windows 安装方式安装；项目要求使用仓库内的 `uv.lock`，不要手工编辑锁文件。构建前可执行 `uv lock --check`，发现 `pyproject.toml` 与锁文件不一致时先重新生成并复核 diff。

产物位于 `artifacts/onedir/quiz-assistant/`，首发使用目录包，不使用 onefile。安装目录可以替换，用户数据不会放在安装目录。

## 启动和数据目录

```powershell
.\packaging\run.ps1
```

启动器只绑定 `127.0.0.1`，会检查端口占用并报出可诊断错误；它不会自动结束其它进程，也不会降级监听 `0.0.0.0`。默认数据目录为：

```text
%LOCALAPPDATA%\QuizAssistant\data\quiz.db
%LOCALAPPDATA%\QuizAssistant\data\backups\
%LOCALAPPDATA%\QuizAssistant\data\exports\
```

启动器会为本地 session 生成随机 token 并打印到当前控制台；浏览器辅助模式需要使用这个 token。也可以在启动前设置 `QUIZ_LOCAL_SESSION_TOKEN`，以便固定本地开发配置。

## 备份、完整性和恢复

升级前先创建带 manifest/hash 的备份。恢复前必须执行 SQLite `PRAGMA integrity_check`，核对 manifest 和 SHA-256，然后使用临时数据库替换；恢复失败应保留原库。不要把 `.db-wal` 或 `.db-shm` 当作可忽略附件，也不要用“重新初始化”代替恢复。

建议的升级顺序：

1. 停止旧版本服务并保留旧的 onedir 目录。
2. 创建并核验当前数据库备份。
3. 用新版本执行 migration；失败时停止，不覆盖原库。
4. 启动新版本，检查 `/api/health`、题库读取和本地查询。
5. 发现问题时停止新版本，回滚程序目录；只有用户明确确认后才恢复数据库。

## 回滚和排障

- 端口占用：查看 `Get-NetTCPConnection -LocalPort 8765 -State Listen`，记录 owning PID 后由用户决定是否停止；启动器不会强制杀进程。
- 服务无法启动：直接运行 onedir 下的 `quiz-assistant.exe`，保留控制台日志，不把 API key、session token 或完整题面写入日志文件。
- 前端 404：确认包内存在 `frontend\dist\index.html`，并确认构建是在 PyInstaller 之前完成。
- OCR 503：确认 Pillow/pytesseract 已随包安装，并确认 Tesseract 位于 PATH、`TESSERACT_CMD` 或常见 Windows 安装路径。
- 升级失败：保留旧 onedir、数据库备份和 manifest；不要删除或覆盖 `%LOCALAPPDATA%\QuizAssistant\data`。

远程写入、远程导入、备份恢复 API 和 workspace AI provider 仍由 Phase C/Phase D 服务端门禁控制，本发布包不会放宽这些限制。
