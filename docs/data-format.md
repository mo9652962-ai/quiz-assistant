# 数据格式

JSON 可以是题目数组，也可以是单个题目对象或 `{ "questions": [...] }`。题目 ID 是稳定主键，不能用题干代替。`single_choice` 必须恰好一个正确选项，`multiple_choice` 至少一个，`true_false` 导入时规范为 A/B 两个选项，`short_answer` 使用 `answer_aliases`。

原始题干保留在 `stem`，查询索引另存 `normalized_stem`。规范化版本写入匹配结果，升级规范化规则时可以重建索引而不改变旧答题记录。

