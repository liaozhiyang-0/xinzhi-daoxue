# P53：CT 结构化平衡校验器

## 实现范围

新增 `CTValidator` 并挂载到现有专业校验流程。它只检查 `AcademicProblem.relations` 中的显式结构化数据：

- `rule: kcl_kvl_consistency`（或 `kcl`、`kvl`）要求 `candidate_lhs` 与 `candidate_rhs` 为有限数值；
- `rule: power_energy_balance` 要求 `supplied_power`、`absorbed_power`，可选 `generated_power` 为有限数值；
- 可选 `tolerance` 控制比较容差。

缺字段、非数值、自然语言描述和未声明拓扑均跳过，不产生自动冲突。校验只改变专业校验结果中的风险与冲突，不调用 Provider、OCR 或冻结基线。

## 证据来源

CT 规则证据现在支持每条规则声明独立的 `validator_id`/`validator_path`：结构化平衡规则使用 `ct_deterministic_v1`，单位、符号和电容初值规则继续引用已有的有限 `student_verification_v1`。资产审计显示 CT 规则证据为 `5/5 covered`，但候选错误模板仍需教师复核，未进入 runtime。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_ct_validator.py apps/api/tests/test_course_asset_audit.py apps/api/tests/test_universal_academic_solver.py -q --no-cov
.venv\Scripts\python.exe scripts/audit_course_assets.py --course CT --course AE
```
