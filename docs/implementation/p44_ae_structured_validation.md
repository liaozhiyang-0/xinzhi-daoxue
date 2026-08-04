# P44：AE 结构化条件验证增强

## 现状与目标

AE CoursePack 已声明二极管、BJT、MOS、反馈等题型，但原有 `AEValidator` 主要依赖答案文本标记，且部分题型没有显式分析模式。本阶段补充有限的结构化条件校验，让已有 `known_conditions` 能参与可解释的本地复核；这不是模型评测结果，也不代表 AE CoursePack 已经达到完整覆盖。

## 新增检查

- `diode_circuit`：当 `v_d` 或阳极/阴极电压表明不是正向偏置，却声称二极管正向导通时，报告 `diode_operating_region`。
- `bjt_bias`：当 `v_ce < 0` 却声称工作在 active/放大区时，报告 `q_point_region_mismatch`。
- `feedback`：当结构化条件为 negative/positive，而答案明确写出相反极性时，报告 `feedback_polarity`。
- `diode_circuit`、`bjt_bias`、`mos_bias`、`small_signal_amplifier` 现在有显式分析模式，不再完全依赖文本分类。

所有检查都满足以下边界：

- 只使用请求中的结构化条件和答案文本，不调用 Provider、OCR 或外部服务。
- 只生成 `ProfessionalValidationResult` 冲突，不自动重写答案、不修改冻结 `SOLVER_CT v1.0/SOLVER_CT_V1`。
- 条件不足时保持不确定，不把缺少条件推断成物理结论。
- 三个演示案例继续由负责人设计，不由本阶段生成或修改。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest `
  apps/api/tests/test_ae_validator.py `
  apps/api/tests/test_targeted_solver_optimization.py -q --no-cov
```

测试覆盖冲突检测、无冲突的一致答案、显式题型模式和“不触发 regeneration”约束。

## 当前限制与后续

`config/course_assets/AE.yaml` 仍标记 CoursePack 为 `basic`，因为小信号前置条件、单位一致性、频率响应和完整器件模型尚未形成同等强度的结构化验证。下一阶段应先为这些规则建立输入字段契约和最小离线案例，再决定是否扩大验证范围，不能仅凭文本规则把状态改成 complete。
