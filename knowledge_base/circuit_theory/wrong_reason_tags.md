# 电路理论错因标签

| 标签 | 含义 | 典型触发 |
|---|---|---|
| `reference_direction_error` | 参考方向或符号错误 | 未先定义电压、电流方向 |
| `kcl_kvl_sign_error` | KCL/KVL 符号错误 | 同一支路在方程中符号不一致 |
| `dependent_source_zeroed_error` | 错误置零受控源 | 求等效电阻或时间常数时关闭受控源 |
| `supernode_constraint_missing` | 超节点约束缺失 | 只写 KCL，未写电压源约束 |
| `initial_continuity_error` | 初值连续性错误 | 电容电压或电感电流突变 |
| `time_constant_error` | 时间常数错误 | 看入电阻、RC/RL 关系错误 |
| `phasor_sign_error` | 相量或阻抗符号错误 | 电容阻抗、相位转换错误 |
| `complex_power_conjugate_error` | 复功率共轭错误 | 使用 `UI` 代替 `UI*` |
| `phase_line_quantity_confusion` | 线量与相量混淆 | Y/Δ 关系套错 |
| `dot_convention_error` | 同名端判断错误 | 互感电压符号错误 |
| `unit_scale_error` | 单位倍率错误 | m、μ、k 换算遗漏 |
| `insufficient_information` | 条件不足 | 缺图、缺参数或拓扑不清 |

标签只表示可观察的解题错误，不用于评价学生能力或态度。
