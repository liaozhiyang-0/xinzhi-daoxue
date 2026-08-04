# P42：CT/AE 错误模板教师证据审核闭环

## 目标

CT 与 AE 的错误模板提案此前已经完成候选整理，但提案仍处于 `enabled: false` 和 `teacher_review.status: pending`。本阶段补齐可审计的教师审核写入流程，不把候选模板自动提升为运行时能力，也不处理用户负责设计的三个演示案例。

## 接口

读取审核队列：

```text
GET /api/v1/knowledge/course-asset-review-queue?course_id=CT|AE
```

保存审核决策：

```text
PUT /api/v1/knowledge/course-asset-review-decisions/{course_id}
```

保存请求必须带上读取时返回的 `source_fingerprint`。每条决策必须对应当前队列中的 proposal，`approved` 或 `rejected` 必须提供至少一个 `evidence_refs`；缺少证据、重复/未知 proposal 或队列已变化时拒绝保存。

## 边界

- 写入目标仅为 `config/error_pool/reviews/{CT|AE}.yaml`，采用临时文件后原子替换。
- 审核文件包含审核人、时间、决策、备注和证据引用，并写入现有审计日志。
- 审核完成后队列会刷新，但 `runtime_loaded` 和 `runtime_eligible` 仍为 `false`；后续如需进入运行时，必须新增独立的、可复核的发布/提升步骤。
- 接口受现有教师/管理员权限闸门保护；开启认证时审核人以服务端身份为准，不信任请求体冒充身份。
- 不调用真实 Provider、OCR 或外部服务，不修改 `SOLVER_CT v1.0/SOLVER_CT_V1`，不包含三个演示案例。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_review_api.py -q
.\.venv\Scripts\python.exe -m ruff check apps/api/app/contracts/knowledge.py apps/api/app/contracts/__init__.py apps/api/app/services/course_asset_review.py apps/api/app/api/v1/knowledge.py apps/api/tests/test_course_asset_review_api.py
.\.venv\Scripts\python.exe scripts/export_openapi.py
```

验证重点：CT 队列 4 条、AE 队列 6 条；审核保存要求证据；源指纹过期返回 409；原子保存后队列反映审核结果，但运行时资格仍关闭。

## 后续

下一阶段可在教师审核证据充分后，单独设计“审核结果 → 运行时模板”的显式提升流程，并继续保持 dry-run、变更审计和冻结基线边界。
