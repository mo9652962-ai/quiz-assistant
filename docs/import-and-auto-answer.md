# 题库导入与本地自动答题

## 支持的格式

本仓库当前支持三种本地文件格式：

- `.json`：一个题目数组，或 `{ "questions": [...] }`。
- `.jsonl`：每行一个题目对象，适合批量生成和增量导入。
- `.csv`：使用固定字段，见 `examples/questions.csv`。

本项目的数据库模型是“扁平题目”模型，当前不直接接收另一个墨题项目使用的 `.esq` 压缩包。若手里是 ESQ 包，应先把每道题转换为本项目的 JSON/JSONL 记录，并保留来源、卷名和授权信息；不要直接修改 SQLite 文件塞题。

## 导入步骤

在项目根目录执行：

```powershell
python -m quiz_assistant init --db data/quiz.db
python -m quiz_assistant import examples/questions.json --db data/quiz.db --dry-run --json
python -m quiz_assistant import examples/questions.json --db data/quiz.db --json
```

`dry-run` 只校验和统计，不写入题目。正式导入后，重复 `id` 会跳过；逐行校验失败会计入拒绝数，并写入数据库目录下的 `rejected.jsonl`。导入前应确认题库内容有合法来源和使用授权。

也可以在 Web 页面操作：

1. 打开“导入题库”。
2. 选择 `.json`、`.jsonl` 或 `.csv` 文件。
3. 点击“预览（dry-run）”，先查看总行数、可导入数和拒绝项。
4. 确认无误后点击“确认写入题库”。

API 方式使用 `multipart/form-data`：

```powershell
curl.exe -H "X-Quiz-Session: <local-session>" `
  -F "file=@examples/questions.json" `
  -F "dry_run=true" `
  http://127.0.0.1:8765/api/imports
```

## JSON/JSONL 记录格式

选择题至少需要 `id`、`bank`、`type`、`stem` 和两个选项；正式题目必须标出正确选项：

```json
{
  "id": "english-basic-000001",
  "bank": "english-basic",
  "type": "single_choice",
  "stem": "Which sentence is grammatically correct?",
  "options": [
    {"key": "A", "text": "He go to school."},
    {"key": "B", "text": "He goes to school.", "correct": true},
    {"key": "C", "text": "He going to school."},
    {"key": "D", "text": "He gone to school."}
  ],
  "explanation": "第三人称单数主语 He 后使用 goes。",
  "tags": ["语法"],
  "source": {"kind": "manual", "ref": "source-id-or-url"}
}
```

简答题不放 `options`，使用 `answer_aliases`：

```json
{
  "id": "english-basic-000002",
  "bank": "english-basic",
  "type": "short_answer",
  "stem": "Capital of France?",
  "answer_aliases": ["Paris", "巴黎"]
}
```

JSONL 只需把多个 JSON 对象逐行排列，不能把整个文件写成一个 JSON 数组；空行会跳过。CSV 模板中的 `correct_keys` 支持 `A,B` 或 `A;B`。

## 本地自动答题

本项目的“自动答题”是本地题库匹配辅助，不会登录或操作第三方考试页面，也不会替用户向外部平台提交答案。

- CLI：`python -m quiz_assistant answer --text "题干" --option "A. 选项" --json`。
- Web：在“查询答案”粘贴题干，可附带选项。
- 练习页：点击“本地自动匹配”，系统只会在高置信度时填入选项，仍需用户检查并点击“提交答案”。

返回 `auto_answerable: true` 且 `status: "high_confidence"` 时，才允许自动填入/直接显示本地答案。`needs_confirmation` 或 `no_match` 只给候选、分数和证据，不自动作答。

推荐的使用闭环是：

```text
准备有授权的题库 → dry-run → 正式导入 → 查询/本地匹配 → 人工确认 → 提交本地练习 → 错题复习
```
