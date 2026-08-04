# P26：教师 OCR 决策与证据写回

## 目标

P25 已能只读识别 OCR 决策文件缺失、待处理和缺少证据的状态。P26 增加受控的教师写回闭环：教师在工作台逐行选择决策、填写证据引用和备注，服务端校验后原子写入 `.local_outputs/ocr_decisions/<COURSE>.yaml`。

## API 边界

```text
PUT /api/v1/knowledge/ocr-review-decisions/{course_id}
```

请求必须包含：

- 当前 OCR 队列的 `source_fingerprint`；指纹变化时返回 `409`，要求重新加载；
- `reviewer`；认证关闭的本地环境由教师显式填写，认证开启时服务端使用当前教师/管理员身份；
- 覆盖当前队列全部行的 `decisions`；决策值仍沿用 `ocr_review_decisions.v1`；
- 非 `pending` 决策必须至少有一个 `evidence_refs`，否则返回 `422`。

服务端不会执行 OCR、调用 Provider、修改索引状态或修改冻结 Solver。写入使用临时文件加原子替换；成功后记录 `knowledge_ocr.review_decisions.save` 审计事件并失效内存快照。未被修改的既有行会保留原复核人和复核时间。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_knowledge_api.py apps/api/tests/test_knowledge_ocr_review.py -q --no-cov
.\.venv\Scripts\ruff.exe check apps/api/app/contracts/knowledge.py apps/api/app/contracts/__init__.py apps/api/app/services/knowledge_ocr_review.py apps/api/app/services/knowledge_ocr_review_cache.py apps/api/app/api/v1/knowledge.py
node --check apps/api/app/static/debug/teacher.js
.\.venv\Scripts\python.exe -m mypy apps/api/app
```

重点验证：缺证据被拒绝、过期指纹返回 `409`、成功写回后 GET 质量摘要变为 `complete_with_evidence`，且 `ocr_execution_performed` 仍为 `false`。

## 风险与后续

- 文件写入和数据库审计不是跨存储事务；若数据库提交失败，仍需人工核对 YAML 和审计记录。
- 当前写回允许教师保存任意合法决策，但不会自动触发 OCR、索引或发布；执行链路仍需后续明确授权和独立评测。
- 真实课程的决策文件仍不存在时，CT/AE 工作台继续显示 `decision_file_missing`，直到教师实际提交审核结果。
