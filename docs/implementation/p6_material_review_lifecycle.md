# P6 课程材料教师复核闭环

## 目标

把 PDF/OCR 质量启发式和教师工作台的只读片段预览连接为可追踪的复核流程。复核状态只表示教师对当前上传版本的处理结论，不把启发式结果包装成 OCR 置信度或教学效果指标。

## 状态与边界

- `not_required`：解析为 ready 且没有质量报告要求人工复核。
- `pending`：解析不完整、失败，或质量报告标记需要人工复核。
- `approved`：教师或管理员确认当前版本可以进入知识库发布流程。
- `rejected`：教师或管理员确认当前版本不能发布；备注可记录后续处理方向。

状态保存在 `files` 表的增量迁移 `20260804_0012` 中，并记录复核人、UTC 时间和长度受限备注。复核备注不写入审计详情，审计日志只记录是否存在备注，避免把自由文本扩大到审计检索面。

## API

- `GET /api/v1/knowledge/materials`：返回质量字段和复核字段。
- `GET /api/v1/knowledge/materials/{file_id}/chunks`：教师/管理员只读查看有限解析片段。
- `POST /api/v1/knowledge/materials/{file_id}/review`：提交 `approved` 或 `rejected` 和可选备注。
- `POST /api/v1/knowledge/materials/{file_id}/publish`：对质量报告要求复核的材料，仅在状态为 `approved` 时允许发布。

认证开启时，上述管理接口要求 teacher 或 admin；认证关闭时沿用本地开发模式。批准动作仍要求解析状态为 `ready`，不会把 OCR 缺失、解析失败的材料伪装成可发布内容。

## 可复现验证

```powershell
cd C:\Users\86184\Desktop\xinzhi-daoxue
python -m pytest apps/api/tests/test_document_ingestion.py -q
python -m ruff check apps/api/app/models apps/api/app/contracts apps/api/app/api/v1/knowledge.py apps/api/app/services/document_ingestion.py apps/api/tests/test_document_ingestion.py
python -m mypy apps/api/app
```

当前阶段未执行真实 OCR、真实 Provider 或 Docker；测试使用本地测试数据库和 Mock 配置。

## 后续

下一步应让教师工作台显示复核状态并提供受控的“通过/退回”操作，再补充带低文本 PDF 的端到端门禁测试。三个演示案例继续由项目方自行设计，不由本阶段自动生成。
