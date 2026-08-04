# P13：OCR 复核证据增强与决策合并

## 本阶段改动

- 超过知识库解析大小限制的 PDF 仍不提取文本，但会尝试读取 PDF 页数元数据，方便教师规划拆分或后续 OCR 范围。
- 决策校验报告现在包含每条候选的 `review_decision`、审核人、时间、证据引用和备注。
- 决策仍然是审计数据，不会改变 `index_status`、自动执行 OCR 或发布知识库内容。

## 验证边界

页数元数据读取依赖 PDF 结构索引；结构损坏时页数可能为 `0`，这表示“未知”，不是空 PDF。超限文件不因页数读取成功而获得文本索引资格。

`valid=true` 只说明决策文件与队列快照匹配、字段完整、动作适用于当前 PDF 状态。只有后续明确实现并授权的 OCR/人工发布流程才能消费这些决策。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_knowledge_ocr_review.py -q --no-cov
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy apps/api/app
```

本阶段没有修改数据库 migration、`SOLVER_CT_V1`、冻结基线或 Provider 配置。
