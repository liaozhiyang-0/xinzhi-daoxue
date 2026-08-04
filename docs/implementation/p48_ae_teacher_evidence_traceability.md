# P48：AE 教师复核证据可追踪性

## 现状与目标

AE 已有 6 个错误池候选、教师复核记录和乐观并发控制，但队列只展示候选与教师证据引用，不能直接看到候选是否有确定性验证器和测试支撑。本阶段补充候选签名的证据映射，并把状态透传到 API 和教师工作台。

## 实现

- `config/course_assets/AE.yaml` 新增 `error_signature_evidence.v1`：将 6 个候选签名分别映射到验证器冲突类型。
- `scripts/audit_course_assets.py` 检查候选数量、映射完整性、验证器冲突类型和测试文件，输出 `error_signature_evidence`；当前 6/6 为 `evidence_ready`。
- 教师复核队列新增 `deterministic_evidence_status` 与 `deterministic_conflict_types` 字段。
- 教师工作台展示确定性证据状态和冲突类型，但仍要求教师提供独立的材料/案例证据；这两个状态不会改变 `runtime_eligible`。

## 边界与风险

- `evidence_ready` 只表示代码与测试证据存在，不等价于教师批准、模型准确率、官方规则核验或竞赛成绩。
- 6 个候选的教师决定仍为 `pending`，候选模板仍禁用，未生成 release 文件。
- 审计和队列均为读操作；保存教师决定仍需要 source fingerprint、reviewer 和 evidence refs。
- 三个演示案例继续由用户设计，未纳入本阶段自动生成或审批。

## 验证

```powershell
.venv\Scripts\python.exe scripts/audit_course_assets.py --course AE
.venv\Scripts\python.exe -m pytest apps/api/tests/test_course_asset_audit.py apps/api/tests/test_course_asset_review_api.py apps/api/tests/test_teacher_web.py -q --no-cov
```
