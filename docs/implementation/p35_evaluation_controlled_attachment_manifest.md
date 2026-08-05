# P35：评测受控附件 manifest

## 目标

为未来的图片/PDF 评测案例建立可验证的附件边界，使附件字节变化能够进入报告 provenance，同时避免把任意本地路径直接发送给任务接口或教师端。

## 当前审计结论

- 当前 `evaluation/cases/` 有 73 个案例，`file_refs` 仍为空，暂无实际附件案例。
- 现有上传服务已经负责用户上传文件的文件名校验、存储根目录边界和内容校验；评测案例不是用户上传流程，不能复用原始路径作为已授权附件。
- 本阶段只实现评测案例根目录内的离线 manifest 校验，不自动读取外部路径、不执行 OCR、不调用真实 Provider，也不改变冻结 Solver 基线。

## 实现

- 新增 `evaluation_case_attachment_manifest(cases, root)`：
  - 只接受 `file_refs` 中的相对 `path`；
  - 拒绝绝对路径、Windows drive/UNC 路径、目录穿越、缺失文件和符号链接越界；
  - 当前只允许 `.png/.jpg/.jpeg/.webp/.pdf`；
  - 按案例 ID和附件顺序记录内部 canonical entry，计算附件字节 SHA-256 与大小；
  - 只返回 manifest hash 和附件数量，不返回原始路径列表。
- `EvaluationRunMetadata` 新增：
  - `case_attachment_manifest_sha256`；
  - `case_attachment_manifest_version=evaluation_case_attachments.v1`；
  - `case_attachment_count`。
- `scripts/run_evaluation.py` 在 `--validate-only` 中报告附件 manifest 错误；存在不安全附件时，正式评测不会继续执行。
- provenance/readiness 会将缺少附件 manifest 识别为 `partial`，并给出重新生成带附件 manifest 报告的下一动作。

## 可复现验证

```powershell
.\.venv\Scripts\python.exe scripts\run_evaluation.py --validate-only
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_evaluation_framework.py apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe apps/api/app
node --check apps/api/app/static/debug/teacher.js
.\.venv\Scripts\python.exe scripts\validate_config.py
.\.venv\Scripts\python.exe scripts\check_sensitive_files.py
```

当前案例目录的附件数量应为 `0`，manifest 仍会对空附件集合生成稳定 hash；这不表示已有图片/PDF 评测覆盖率。

## 风险与下一步

- manifest 校验已完成，但 runner 尚未把案例文件自动上传为生产 `AttachmentRef`；因此新增附件案例前仍需明确离线测试上传适配和授权边界，不能只填写 `file_refs` 就声称多模态评测已完成。
- 后续 P36 可在不触碰真实 Provider 的前提下，为本地 mock 流程增加受控 `AttachmentRef` 适配，并补充图片/PDF 的解析质量与 OCR 证据测试。
- 三个演示案例仍由用户自行设计，不纳入自动生成或自动评分结论。
