# P52：CT 有限规则证据边界

## 目标

CT 课程资产审计此前没有 `verification_rule_evidence` 声明，无法区分“没有声明证据”和“已有有限确定性规则”。P52 先登记已有的有限规则；P53 在同一边界上补充结构化 KCL/KVL 与功率平衡校验，并支持每条规则声明自己的校验器来源。不修改冻结的 `SOLVER_CT_V1`，也不把通用学生作业校验描述为完整 CT 求解器验证。

## 当前结果

- `reference_direction`：由 `StudentVerificationService` 的确定性符号比较覆盖。
- `unit_consistency`：由单位存在性与单位兼容性规则覆盖。
- `initial_condition_continuity`：由 CT 一阶电路电容电压连续性短语规则覆盖。
- `kcl_kvl_consistency`、`power_energy_balance`：由 `ct_deterministic_v1` 覆盖，但只接受显式结构化数值，不从自然语言推断拓扑或功率方向。

因此 CT 的规则证据覆盖率为 `5/5`，审计状态为 `covered`；这不等于所有自然语言题目都可自动验证，也不是运行时模板发布或冻结基线变更。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_teaching_loop_phase2_services.py apps/api/tests/test_course_asset_audit.py -q --no-cov
.venv\Scripts\python.exe scripts/audit_course_assets.py --course CT --course AE
```

三个演示案例仍由用户设计，不在本阶段范围内。
