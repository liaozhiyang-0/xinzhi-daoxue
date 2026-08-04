# P16 OCR 复核队列快照缓存

## 目标

降低教师工作台重复读取 OCR 复核队列时的等待时间，同时保持队列只读、结果可追溯和文件变化可感知。本阶段没有新增 OCR 执行能力，也没有接入真实 Provider。

## 实现边界

新增 `KnowledgeOCRReviewSnapshotCache`：

- 指纹由课程源文件的相对路径、文件大小、修改时间、解析大小配置和对应课程的决策 YAML 元数据组成；不读取文件内容，不改变原始课程资料。
- 先查进程内存，再查 `.local_outputs/ocr_review_snapshots/` 的 JSON 快照。
- 快照采用临时文件写入后原子替换，损坏或无法写入时自动回退到正常审计。
- 指纹变化或 TTL 超过 `KNOWLEDGE_OCR_REVIEW_CACHE_TTL_SECONDS` 时重新审计；并发请求在同一进程内串行构建同一快照。
- API 响应新增 `cache_status`、`cache_backend`、`source_fingerprint` 和 `snapshot_age_seconds`，便于教师工作台和后续可观测性使用。

默认配置：

```text
KNOWLEDGE_OCR_REVIEW_CACHE_ENABLED=true
KNOWLEDGE_OCR_REVIEW_CACHE_PATH=./.local_outputs/ocr_review_snapshots
KNOWLEDGE_OCR_REVIEW_CACHE_TTL_SECONDS=300
```

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_knowledge_ocr_review_cache.py -q
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_knowledge_api.py::test_ocr_review_queue_is_teacher_read_only_snapshot -q
```

覆盖项包括内存命中、TTL 失效、源文件/决策文件元数据失效、跨实例磁盘命中和并发构建串行化。

## 风险与后续

当前指纹使用文件元数据而不是内容哈希，正常新增、删除、修改文件均会失效，但极端情况下若文件内容变化且大小与修改时间都被人为恢复，缓存可能无法识别。后续如需更强一致性，可在低频后台刷新时增加内容哈希；不应在教师请求路径中无条件读取所有文件内容。
