# P45：AE 小信号与频率条件验证

## 现状与范围

AE 课程注册表已经声明 `small_signal_prerequisite` 与 `unit_consistency` 规则，但此前验证器没有消费结构化的 Q 点状态、目标单位或频率边界。本阶段只补充可解释的本地确定性检查，不改变 `ACADEMIC_PROBLEM_SOLVER` 的 Provider 链路，也不把 AE CoursePack 从 `basic` 提升为 `complete`。

## 新增检查

- `small_signal_amplifier`：当请求明确提供 `q_point_status`、`bias_status` 或 `small_signal_prerequisite` 时，只有 `verified`、`valid`、`pass`、`ready` 等明确通过状态才允许继续使用小信号模型；`pending`、`invalid` 等状态会报告 `small_signal_prerequisite_missing`。
- 目标单位：当请求只有一个明确的 `target_quantities[].unit`，且结构化答案提供 `final_answer_detail.unit` 时，按物理量纲比较电压、电流、电阻、频率、增益等单位，冲突报告为 `unit_consistency`。目标数量多个或答案单位缺失时不作猜测。
- `frequency_response`：读取 `f_L`/`lower_cutoff_frequency`、`f_H`/`upper_cutoff_frequency` 与 `frequency`/`signal_frequency`；支持 Hz、kHz、MHz、GHz 的换算，检查截止频率顺序，并在答案明确声称 midband/passband 时检查信号频率是否落在通带内。

## 边界与风险

- 所有检查只依赖 `AcademicProblem.known_conditions`、`target_quantities`、结构化最终答案和答案文本，不调用 Provider、OCR、数据库或外部服务。
- 缺少结构化条件不会被推断为失败；这避免了把普通文本题和 OCR 不完整题目误报为前置条件错误。
- 单位检查比较物理量纲，不执行数值换算；多个目标量的答案单位映射仍需后续扩展。
- 频率条件缺少单位时不擅自假定量纲；非频率单位会报告 `frequency_unit`。当前不覆盖完整的 Bode 曲线、相位裕度或器件寄生参数模型。
- 该阶段没有生成错误池发布文件，也没有改变 `runtime_course_pack_status: basic`。

## 验证

```powershell
.venv\Scripts\python.exe -m pytest apps/api/tests/test_ae_validator.py apps/api/tests/test_targeted_solver_optimization.py -q --no-cov
```

本阶段测试覆盖：小信号前置条件通过/不通过、结构化目标单位冲突、频率单位换算、截止频率倒置、通带边界以及缺少条件时不误报。
