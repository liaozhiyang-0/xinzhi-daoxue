# P36：本地 Mock 评测附件适配

## 目标

在 P35 受控 manifest 的基础上，让离线 Mock 评测可以安全地使用案例根目录内的图片附件；附件必须先经过项目已有本地文件接口，再以 `AttachmentRef` 进入任务创建请求。

## 实现

- `EvaluationRunner` 接收显式 `case_attachment_root`，不从环境变量或案例字段推断任意路径。
- runner 使用 P35 的路径校验解析 `file_refs`，逐个通过本地 `/api/v1/files` 上传，读取返回的 `FileRead`，只构造以下受控附件字段：
  - `file_id`、`filename`、`content_type`、`size_bytes`；
  - `storage_key`、`checksum_sha256`；
  - `ingestion_status`、页数、提取结果和解析 metadata。
- 任务接口不再直接收到 `{"path": ...}` 这样的案例原始字典。
- PDF 若仍处于 pending/processing，或解析状态为 failed（通常意味着需要 OCR），该评测案例明确失败，不被伪装成可执行成功。
- 离线模式仍使用 Mock Provider 配置，`allow_cloud=false`；本阶段没有真实 Provider、云端上传或 OCR 调用。
- `run_suite` 在执行结束后恢复原附件根目录状态，避免跨 suite 泄露路径上下文。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_evaluation_framework.py -q --no-cov
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe apps/api/app
node --check apps/api/app/static/debug/teacher.js
.\.venv\Scripts\python.exe scripts\run_evaluation.py --validate-only
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
```

当前案例目录没有 `file_refs`，因此默认离线评测仍然是 0 个附件；适配器的图片上传和 PDF OCR 未就绪拒绝路径由测试中的临时文件覆盖。

## 边界与下一步

- 本阶段只完成本地 Mock 适配，不证明 OCR 质量、真实多模态模型效果或竞赛演示效果。
- PDF 的 OCR 仍需遵循已有教师复核与 OCR decision evidence 流程；不能因为附件可上传就自动批准或发布 OCR 结果。
- 下一阶段可继续增强：为本地 Mock 任务保存附件清理策略、补充 PDF 有文本层/低文本页的解析证据映射，并把附件 manifest 与单案例结果关联起来。
- 三个演示案例继续由用户自行设计，不纳入自动生成或自动评分结论。
