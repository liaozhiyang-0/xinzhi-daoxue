# P43：CT/AE 错误模板显式发布闸门

## 目标

P42 已能记录教师审核决策，但审核记录不能直接等同于运行时能力。本阶段增加从审核记录到正式错误池的独立发布流程，默认 dry-run，只有明确执行且整门课程提案全部满足证据条件时才写入运行时 YAML。

## 流程

```text
教师审核与证据
        ↓
promote_error_pool.py（默认 dry-run）
        ↓
全量 approved + evidence_refs + exact_rule + 源指纹一致
        ↓ 仅显式 --execute
config/error_pool/{CT|AE}.yaml
config/error_pool/releases/{CT|AE}.yaml
        ↓
ErrorPoolRegistry 重载后提供正式匹配
```

运行：

```powershell
# 只读计划；当前 pending 时应输出 status=blocked，不会写文件
.\.venv\Scripts\python.exe scripts/promote_error_pool.py --course CT
.\.venv\Scripts\python.exe scripts/promote_error_pool.py --course AE

# 只有确认 dry-run 为 ready 后才允许显式执行
.\.venv\Scripts\python.exe scripts/promote_error_pool.py `
  --course CT --execute --source-fingerprint <dry-run-source-fingerprint>
```

## 安全与可追溯性

- 课程级发布是原子决策：任意 proposal 仍为 pending/rejected、证据为空、审核记录不完整、模板非法或运行时签名冲突，整次发布阻断。
- 发布前把旧运行时 YAML 保存到 `.local_outputs/error_pool_promotion_backups/{course}/`；发布记录保存审核人、审核时间、证据引用、源指纹和运行时内容指纹。
- 可以使用发布报告中的备份路径执行显式回滚：

  ```powershell
  .\.venv\Scripts\python.exe scripts/promote_error_pool.py `
    --course CT --rollback .local_outputs/error_pool_promotion_backups/CT/<backup>.yaml
  ```

- 发布后的课程审核队列会识别 active release，避免把已经发布的候选重新报告为 schema 错误；回滚后队列恢复为已审核但待发布状态。
- 教师工作台现在可以保存审核决策与证据，但不提供直接发布按钮；正式发布仍由受控 dry-run/execute 流程完成。
- 不修改 `SOLVER_CT v1.0/SOLVER_CT_V1`，不调用真实 Provider/OCR/Docker，不生成或纳入三个演示案例，也不写入真实凭据。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest `
  apps/api/tests/test_error_pool_promotion.py `
  apps/api/tests/test_course_asset_review_api.py -q
.\.venv\Scripts\python.exe -m ruff check .
node --check apps/api/app/static/debug/teacher.js
```

验证应覆盖：pending 计划只读阻断、全量批准后的临时目录发布、运行时匹配、发布记录、回滚、源指纹冲突和审核队列恢复。

当前仓库 CT/AE 审核记录仍为 pending，因此本阶段只验证了临时目录中的 execute 路径，未对真实运行时配置执行发布。
