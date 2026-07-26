# 本地知识库元数据覆盖层

本目录只保存课程发现规则、同义词和经人工复核前不得正式启用的 OCR 清洗草稿。原始教材目录保持只读，不在 Git 中提交。

- `courses/`：课程名称、Markdown 匹配规则、章节别名和排除路径。
- `synonyms/`：查询扩展词；仅用于本地词项检索。
- `corrections/`：OCR 覆盖规则。自动发现项必须为 `review_status: draft`。

清洗规则字段为 `original`、`replacement`、`document_path`、`scope`、`reason` 和 `review_status`。阶段 1.6 的运行时只应用 `review_status: approved` 的规则，因此本轮草稿不会静默改写索引内容。
