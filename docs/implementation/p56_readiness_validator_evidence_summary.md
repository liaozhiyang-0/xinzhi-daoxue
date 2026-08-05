# P56：readiness 校验器证据状态汇总

## 目标

P55 已在队列和 Promotion 中展示校验器来源，但 readiness 只显示教师材料证据的缺失/不可追踪状态。本阶段在同一只读汇总中增加确定性校验证据状态，明确区分两条独立链路：教师是否提交可追踪材料证据，以及系统是否有有限校验器证据。

## 新增行为

- `deterministic_evidence_status`：`ready`、`partial` 或 `unavailable`。
- `deterministic_evidence_ready_count` 与未就绪 proposal ID。
- `deterministic_evidence_scope_counts` 与校验器 ID 列表。
- 教师 readiness 卡片显示 `ready/total` 和适用范围。

这些字段只读，不会批准教师决定、不启用候选模板、不创建 release，也不执行 Provider/OCR。当前 CT/AE 的确定性证据均已就绪，但教师材料证据仍为 pending，因此 readiness 仍保持阻塞。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
```

## 风险与边界

校验器证据只适用于各课程清单声明的有限范围；`ready` 不代表教师材料证据已提交，不会改变 `runtime_eligible`、Promotion 或 release 状态。
