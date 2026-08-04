# P54：CT 候选错误签名证据映射

## 目标

CT 的候选错误模板此前有 4 条 proposal，但资产审计显示 `error_signature_evidence` 未声明。本阶段为每条 proposal 增加有限的结构化证据映射，同时保持教师复核、runtime 禁用和 Promotion Gate 不变。

## 有限校验范围

- `equivalent_resistance_error`：比较显式候选等效电阻与参考值。
- `kcl_sign_error`：比较显式 KCL 候选方程两侧。
- `phase_sign_error`：比较显式候选相位与参考相位，并按 360° 归一化。
- `power_factor_error`：检查显式功率因数是否超出 `[-1, 1]`。

缺少结构化字段时不判错；这些检查不从自然语言推断拓扑、相位约定或源置零方式，不能替代教师复核。

## 当前状态

CT 审计的候选错误签名证据为 `4/4 evidence_ready`，但 4 条 proposal 仍为 `pending`、`runtime_eligible: false`，不会写入 release 或运行时错误池。

## 风险与边界

证据就绪只表示有限结构化字段可以由确定性校验器复核；它不代表自然语言题目的通用诊断能力、教师审核完成、真实 Provider 结果或竞赛成绩。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_ct_validator.py apps/api/tests/test_course_asset_audit.py apps/api/tests/test_course_asset_review_api.py -q --no-cov
.venv\Scripts\python.exe scripts/audit_course_assets.py --course CT --course AE
```
