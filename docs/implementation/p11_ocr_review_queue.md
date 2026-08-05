# P11：PDF/OCR 教师复核队列

## 目标

把原始课程库审计出的 PDF 解析问题整理成可分派、可复核的草稿队列。队列不执行 OCR，不修改原始资料，也不代表教师已经批准内容。

## 队列字段

- `queue_id`：由课程、相对路径和文件校验和生成的稳定 ID。
- `review_status`：新条目固定为 `pending_teacher_review`。
- `review_action`：区分选择 OCR 页面、确认低文本页、拆分/调整解析上限和解析失败检查。
- `ocr_candidate_pages`：只记录启发式候选页，不是 OCR 结果。
- `ocr_confidence`：当前固定为 `null`，`ocr_confidence_source` 为 `not_available`。
- `checksum`：教师复核时确认的是当前文件版本，文件变化后 queue ID 会变化。

## 生成方式

默认只输出到终端，不写文件：

```powershell
.\.venv\Scripts\python.exe scripts\generate_ocr_review_queue.py
```

明确指定输出路径后，才会写入 JSON：

```powershell
.\.venv\Scripts\python.exe scripts\generate_ocr_review_queue.py `
  --course CT --course AE `
  --output .local_outputs\ocr_review_queue.json
```

该命令会重新执行只读课程审计，可能需要数分钟；不会调用 Provider、OCR 引擎或 Docker。输出目录不应提交包含学生隐私或真实 OCR 内容的文件。

## 当前边界

- 队列是维护和教师复核输入，不是数据库审批记录；真正的材料发布仍走已有材料复核 API。
- 超过知识库解析大小限制的 PDF 先进入拆分/限制检查，不自动提高全局限制。
- 教师确认前不得把候选页描述成已完成 OCR，也不得填充虚构置信度。

## 验证与风险

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_knowledge_ocr_review.py apps/api/tests/test_knowledge_api.py -q --no-cov
```

测试只验证队列快照和教师只读边界；没有真实 OCR 质量结论，也不会把候选页自动写入索引。
