# P46：AE 增益符号与输入/输出电阻验证

## 现状与范围

`config/skills/AE.yaml` 已声明 `gain_sign_error`，输入/输出电阻技能也复用 `unit_missing`，但原有验证主要依赖共射/共源中文文本，且结构化最终答案没有单位时会被忽略。本阶段把这两个规则接到已有的 `known_conditions`、`target_quantities` 和 `final_answer_detail` 契约上，不修改课程注册表状态、不发布错误池模板。

## 新增检查

- 增益符号：在 `small_signal_amplifier`、`bjt_small_signal` 或 `mos_small_signal` 中，若结构化条件提供 `gain_polarity`、`expected_gain_sign` 或 `transfer_polarity`，并且最终答案显式给出增益数值符号，则检查两者是否一致，冲突类型为 `gain_sign`。
- 输入/输出电阻单位：当结构化目标量声明单位、结构化最终答案也明确给出数值但没有单位时，报告 `unit_missing`；答案提供 `Ω`、`ohm` 或 `kΩ` 等同一电阻量纲时通过，错误量纲报告 `unit_consistency`。
- 若没有结构化最终答案、没有目标单位或目标单位映射不唯一，则不猜测答案含义，继续保持原有兼容行为。

## 风险与边界

- 增益符号检查只读取最终答案中的显式数值，不读取题干中的给定数值，避免把题目条件误当成模型结论。
- 本阶段不自动推断共射/共源拓扑，不替换答案，不调用 Provider/OCR/外部服务。
- `config/error_pool/AE.yaml` 中尚未审核的 `gain_sign_error` 等模板不会被自动加入正式错误池；仍需教师复核和 P43 发布门禁。
- 三个演示案例仍由用户设计，未纳入本阶段自动生成或评测。

## 验证命令

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_ae_validator.py apps/api/tests/test_targeted_solver_optimization.py -q --no-cov
```

测试覆盖显式增益正负号、正确负增益、输入/输出电阻缺少单位、等价电阻单位以及既有 AE 验证边界。
