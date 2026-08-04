# P51：课程资产 readiness 与教师证据质量一致性

## 目标

P50 已在教师队列和 Promotion Gate 中识别不可追踪证据，但课程资产 readiness 只统计候选数量，可能无法直接解释证据状态。本阶段把队列证据质量汇总到 readiness，并在发现不可追踪的已决定记录时增加明确 blocker。

## 新增行为

- `teacher_review_evidence` 汇总 `missing`、`traceable`、`untraceable` 数量及 proposal ID。
- 当前 pending 队列显示 `status: missing`，继续由 `teacher_review_required` 阻塞。
- 若队列包含不可追踪的已决定证据，readiness 增加 `teacher_review_evidence_untraceable`，下一步为 `replace_untraceable_teacher_evidence_refs`。
- 教师工作台 readiness 卡片显示证据质量、缺失数和不可追踪数。

该汇总只读，不会批准模板、不改变 Promotion Gate，也不执行 Provider/OCR。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
```

当前仓库 CT/AE 复核记录仍为 pending，readiness 应显示 missing，而不是宣称已完成。

## 风险与边界

该汇总只反映仓库中的证据引用质量；它不能替代教师审批、官方规则、真实用户试用或 release promotion，也不执行 Provider/OCR。
