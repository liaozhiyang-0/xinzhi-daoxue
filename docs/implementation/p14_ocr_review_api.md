# P14：教师侧只读 OCR 复核 API

## 接入内容

新增：

```text
GET /api/v1/knowledge/ocr-review-queue?course_id=CT
```

接口只允许教师或管理员（生产环境启用认证时），返回当前本地课程库审计出的 PDF/OCR 复核队列。没有指定课程时返回所有课程。

接口在后台线程执行本地审计，不执行 OCR、不调用模型 Provider、不写入索引。若配置的决策目录中存在 `CT.yaml`、`AE.yaml` 等文件，会一并返回决策校验报告和逐条合并状态。

默认决策目录：

```text
.local_outputs/ocr_decisions/
```

可通过 `KNOWLEDGE_OCR_DECISIONS_PATH` 配置。决策文件的生成和校验仍使用：

```powershell
.\.venv\Scripts\python.exe scripts\generate_ocr_review_queue.py `
  --course CT --decision-template-course CT `
  --output .local_outputs\ocr_decisions\CT.yaml
```

## 安全与发布边界

- 学生端不暴露此接口。
- `pending`、`request_ocr`、`split_pdf` 等状态只作为教师维护信息，不会自动改变 `index_status`。
- 只有本地课程审计和 YAML 校验，未接入 OCR 执行器或真实 Provider。
- 队列每次请求重新读取文件校验和，决策文件与当前版本不匹配时报告 stale checksum。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_knowledge_api.py -q --no-cov
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy apps/api/app
```
