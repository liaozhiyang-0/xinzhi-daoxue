# P49：错误模板发布前证据预览

## 目标

教师复核和 Promotion Gate 已经要求批准项提供证据引用，但原有 dry-run 只返回汇总 blocker。本阶段增加逐候选的只读证据预览，帮助负责人在任何写入动作前核对证据完整性。

## 新增输出

`build_error_pool_promotion_plan` 与 `scripts/promote_error_pool.py` 的 dry-run 报告新增：

- `review_evidence_summary`：每个 proposal 的决定、证据引用数量、审核人/时间是否存在；
- `review_evidence_ready_count`：同时满足 `approved`、至少一个 evidence ref、reviewer 和 reviewed_at 的候选数；
- `review_evidence_not_ready_proposal_ids`：仍不能进入发布候选的 proposal ID 列表。

这些字段只用于解释 Promotion Gate 的状态，不替代 `validate_error_pool_review_document`，也不改变 atomic write、fingerprint、backup 或 rollback 逻辑。

## 当前状态

对仓库当前 AE 配置执行 dry-run 时：

- 6 个候选均为 `pending`；
- `review_evidence_ready_count` 为 0；
- Promotion 状态为 `blocked`，原因包含 `review_pending` 和 `course_review_incomplete`；
- 没有生成 runtime release 文件。

这不是失败的自动化审批，而是预期的安全边界：教师仍需逐项提供材料/案例证据并做出决定。

## 验证

```powershell
.venv\Scripts\python.exe scripts/promote_error_pool.py --course AE
.venv\Scripts\python.exe -m pytest apps/api/tests/test_error_pool_promotion.py -q --no-cov
```

dry-run 在当前 pending 状态下返回非零阻断状态是预期结果；测试同时覆盖 pending 队列和临时目录中全部批准、可回滚的模拟流程。该模拟不代表真实课程发布，也未调用 Provider。
