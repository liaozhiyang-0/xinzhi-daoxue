# 电路理论题型索引

## 1. 文件说明

本文件用于汇总《电路理论》课程知识库中的典型题型，服务于题库分类、错题诊断、学习建议生成和课程 Agent 检索。

## 2. 编号规则

- `CT01-T01` 表示电路理论第1章第1类题型；
- `CT02-T01` 表示电路理论第2章第1类题型；
- `CT03-T01` 表示电路理论第3章第1类题型；
- `CT04-T01` 表示电路理论第4章第1类题型。

## 3. 题型总表

| 题型编号 | 题型名称 | 所属章节 | 对应文件 | 核心知识点 | 主要错因标签 |
|---|---|---|---|---|---|
| CT01-T01 | 电路模型抽象 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | 电路模型、理想元件、集中参数假设 | ideal_element_confusion |
| CT01-T02 | 电荷求电流 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | 电流定义、微分、单位换算 | derivative_error, unit_conversion_error, reference_direction_error |
| CT01-T03 | 电流求电荷 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | 电流积分、平均电流、分段波形 | integration_interval_error, piecewise_waveform_expression_error, initial_value_error |
| CT01-T04 | 电压电位判断 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | 电压、电位、参考极性 | voltage_polarity_error, reference_node_error |
| CT01-T05 | 功率正负与守恒 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | 关联参考方向、功率正负、功率守恒 | passive_sign_convention_error, power_balance_error |
| CT01-T06 | 电源约束判断 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | 独立电压源、独立电流源、受控源 | source_direction_error, dependent_source_control_missing |
| CT01-T07 | 受控源基础计算 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | 受控源、控制变量、KCL/KVL | dependent_source_control_missing, control_variable_sign_error, passive_sign_convention_error |
| CT01-T08 | 术语与方程数 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | 支路、结点、回路、网孔、独立方程数 | circuit_topology_identification_error, equation_count_error |
| CT01-T09 | KCL/KVL 建方程 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | KCL、KVL、元件伏安关系 | kcl_sign_error, kvl_polarity_error, equation_incomplete, redundant_equation_error |
| CT01-T10 | 二极管模型判断 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | 导通、截止、分段线性模型 | diode_state_assumption_error, voltage_polarity_error |
| CT01-T11 | 伏安曲线判断 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | 伏安特性、测量误差、非线性判断 | measurement_loading_error, nonlinear_vi_curve_error, nonlinear_element_judgment_error |
| CT01-T12 | 电阻参数识别 | 第1章 电路模型与基本定律 | 01_circuit_models_and_laws.md | 色环、误差、额定功率 | component_parameter_reading_error |
| CT02-T01 | 一端口等效判断 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | 一端口、端口 u-i 关系、等效条件 | port_definition_error, equivalent_condition_error, source_direction_error |
| CT02-T02 | 串并联化简 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | 串联、并联、开路短路、等效电阻 | circuit_topology_identification_error, equivalent_condition_error |
| CT02-T03 | 分压分流计算 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | 串联分压、并联分流、参考方向 | divider_ratio_error |
| CT02-T04 | 混联网络等效 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | 多级串并联、网络重画、局部等效 | circuit_topology_identification_error, port_definition_error, simplification_sequence_error |
| CT02-T05 | 对称性化简 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | 对称结构、等电位点、无电流支路 | symmetry_condition_error |
| CT02-T06 | 电桥平衡化简 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | 桥式电路、平衡条件、中间支路 | bridge_balance_condition_error, equivalent_condition_error |
| CT02-T07 | 星三角变换 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | Y-Δ 变换、Δ-Y 变换、三端网络 | y_delta_transform_error, symmetry_condition_error |
| CT02-T08 | 电源变换 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | 电压源串阻、电流源并阻、端口等效 | source_transform_error, source_direction_error |
| CT02-T09 | 受控源一端口等效 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | 受控源、控制变量、测试源法 | dependent_source_control_missing, dependent_source_zeroed_error, control_variable_sign_error |
| CT02-T10 | 万用表测量误差 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | 电压表内阻、电流表内阻、负载效应 | measurement_loading_error, meter_connection_error |
| CT02-T11 | 仪表量程扩展 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | 分压、分流、表头内阻、量程设计 | meter_range_extension_error |
| CT02-T12 | 直流电桥测量 | 第2章 电阻电路等效变换 | 02_equivalent_transform.md | 单电桥、双电桥、平衡条件、小电阻测量 | bridge_balance_error, bridge_balance_condition_error, meter_connection_error |
| CT03-T01 | 方法选择 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 支路法、节点法、网孔法、回路法 | method_selection_error, equation_count_error |
| CT03-T02 | 支路电流法 | 第3章 电路分析方法 | 03_general_analysis_methods.md | KCL、KVL、支路电流、支路约束 | reference_direction_error, kcl_sign_error, kvl_polarity_error, redundant_equation_error |
| CT03-T03 | 线性方程求解 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 矩阵、行列式、克拉默法则 | controlled_source_analysis_error, calculation_error, source_term_sign_error |
| CT03-T04 | 普通节点法 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 节点电压、KCL、电导矩阵、注入电流 | reference_node_error, kcl_sign_error, node_analysis_error, source_direction_error |
| CT03-T05 | 节点法快捷列写 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 自电导、互电导、节点电导矩阵 | node_analysis_error, source_direction_error, controlled_source_analysis_error |
| CT03-T06 | 含电压源节点法 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 电压源接参考节点、超节点、电压源约束 | source_direction_error, node_analysis_error, voltage_polarity_error |
| CT03-T07 | 含受控源节点法 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 受控源、控制量、节点电压表达 | dependent_source_control_missing, control_variable_sign_error |
| CT03-T08 | 普通网孔法 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 网孔电流、KVL、公共电阻、电压源代数和 | mesh_analysis_error, source_direction_error |
| CT03-T09 | 网孔法快捷列写 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 自电阻、互电阻、网孔电阻矩阵 | mesh_analysis_error, source_direction_error |
| CT03-T10 | 含电流源网孔法 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 边界电流源、公共支路电流源、超网孔 | source_direction_error, mesh_analysis_error |
| CT03-T11 | 含受控源网孔法 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 受控源、网孔电流、控制量表达 | dependent_source_control_missing, control_variable_sign_error |
| CT03-T12 | 回路法分析 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 回路电流、基本回路、独立回路、有向图 | mesh_analysis_error, independent_loop_count_error |
| CT03-T13 | 结果互相验证 | 第3章 电路分析方法 | 03_general_analysis_methods.md | 方法对比、支路电流、功率守恒 | result_verification_missing, reference_direction_error, power_balance_error |
| CT04-T01 | 线性特性判断 | 第4章 电路定理 | 04_circuit_theorems.md | 线性电路、齐次性、可加性、线性响应 | linearity_condition_error, nonlinear_element_ignored, superposition_scope_error |
| CT04-T02 | 叠加求电压电流 | 第4章 电路定理 | 04_circuit_theorems.md | 叠加定理、独立源置零、电阻等效 | source_zeroing_error, dependent_source_zeroed_error, reference_direction_error, superposition_scope_error |
| CT04-T03 | 叠加中的功率 | 第4章 电路定理 | 04_circuit_theorems.md | 叠加适用对象、功率非线性、总响应 | superposition_scope_error, passive_sign_convention_error, response_component_confusion |
| CT04-T04 | 受控源叠加 | 第4章 电路定理 | 04_circuit_theorems.md | 叠加定理、受控源、控制变量 | dependent_source_zeroed_error, dependent_source_control_missing, reference_direction_error |
| CT04-T05 | 替代定理应用 | 第4章 电路定理 | 04_circuit_theorems.md | 替代定理、电压替代、电流替代 | substitution_equivalence_confusion |
| CT04-T06 | 戴维南等效 | 第4章 电路定理 | 04_circuit_theorems.md | 开路电压、等效电阻、负载端口 | thevenin_resistance_error, voltage_polarity_error, dependent_source_zeroed_error |
| CT04-T07 | 诺顿等效 | 第4章 电路定理 | 04_circuit_theorems.md | 短路电流、等效电阻、诺顿源 | reference_direction_error, thevenin_resistance_error, source_transform_error, port_definition_error |
| CT04-T08 | 受控源等效电阻 | 第4章 电路定理 | 04_circuit_theorems.md | 戴维南、受控源、测试源法、开路短路法 | dependent_source_zeroed_error, test_source_direction_error, thevenin_resistance_error |
| CT04-T09 | 最大功率传输 | 第4章 电路定理 | 04_circuit_theorems.md | 戴维南等效、负载功率、匹配思想 | max_ac_power_transfer_error, thevenin_port_error, efficiency_power_confusion |
| CT04-T10 | 特勒根定理 | 第4章 电路定理 | 04_circuit_theorems.md | KCL、KVL、特勒根定理、功率平衡 | power_balance_error, reference_direction_error |
| CT04-T11 | 互易定理 | 第4章 电路定理 | 04_circuit_theorems.md | 互易定理、线性无源网络、激励响应交换 | reciprocity_direction_error, response_component_confusion |
| CT04-T12 | 定理综合选择 | 第4章 电路定理 | 04_circuit_theorems.md | 叠加、戴维南、诺顿、节点法/网孔法 | theorem_selection_error, port_definition_error, equivalent_circuit_misuse |
| CT04-T13 | 电桥与传感测量 | 第4章 电路定理 | 04_circuit_theorems.md | 电桥平衡、戴维南等效、电阻变化 | bridge_balance_error, sensor_resistance_change_error, measurement_loading_error, open_loaded_output_confusion |
| CT05-T01 | 运放模型与端口识别 | 第5章 含运算放大器的电路 | 05_operational_amplifier_circuits.md | 开环与闭环、反相端、同相端、线性区 | op_amp_terminal_confusion, op_amp_linear_region_error, feedback_polarity_error |
| CT05-T02 | 虚短虚断判断 | 第5章 含运算放大器的电路 | 05_operational_amplifier_circuits.md | 理想运放、虚短、虚断、负反馈 | virtual_short_error, virtual_open_error, op_amp_linear_region_error, kcl_sign_error |
| CT05-T03 | 反相比例放大 | 第5章 含运算放大器的电路 | 05_operational_amplifier_circuits.md | 虚地、反相增益、输入电阻 | op_amp_gain_formula_misuse, virtual_ground_confusion, op_amp_saturation_ignored |
| CT05-T04 | 同相比例与电压跟随 | 第5章 含运算放大器的电路 | 05_operational_amplifier_circuits.md | 同相输入、反馈分压、电压跟随器 | op_amp_gain_formula_misuse, feedback_polarity_error, voltage_follower_function_error |
| CT05-T05 | 求和放大电路 | 第5章 含运算放大器的电路 | 05_operational_amplifier_circuits.md | KCL、反相求和、同相加权、权重系数 | op_amp_gain_formula_misuse, equation_incomplete |
| CT05-T06 | 差分放大电路 | 第5章 含运算放大器的电路 | 05_operational_amplifier_circuits.md | 差分输入、电阻匹配、共模抑制 | instrumentation_amplifier_gain_error, component_parameter_reading_error |
| CT05-T07 | 多级运放级联 | 第5章 含运算放大器的电路 | 05_operational_amplifier_circuits.md | 级间变量、增益乘积、输出限幅 | op_amp_cascade_error, equation_incomplete, op_amp_saturation_ignored |
| CT05-T08 | 仪用放大器 | 第5章 含运算放大器的电路 | 05_operational_amplifier_circuits.md | 高输入电阻、差分放大、增益调节 | instrumentation_amplifier_gain_error, component_parameter_reading_error |
| CT05-T09 | 运放线性区与饱和区 | 第5章 含运算放大器的电路 | 05_operational_amplifier_circuits.md | 负反馈、比较器、输出限幅、阈值 | op_amp_saturation_ignored, comparator_threshold_error |
| CT05-T10 | 运放设计与输入输出特性 | 第5章 含运算放大器的电路 | 05_operational_amplifier_circuits.md | 输入电阻、输出限幅、反馈网络、增益设计 | op_amp_saturation_ignored, feedback_polarity_error, op_amp_gain_formula_misuse |
| CT05-T11 | 传感桥路与运放调理 | 第5章 含运算放大器的电路 | 05_operational_amplifier_circuits.md | 电桥输出、差分测量、小信号放大 | sensor_bridge_small_signal_error, op_amp_sign_error, sensor_resistance_change_error |
| CT06-T01 | 非线性伏安特性判断 | 第6章 非线性电阻电路 | 06_nonlinear_resistive_circuits.md | 非线性电阻、伏安曲线、工作点 | nonlinear_vi_curve_error, nonlinear_operating_point_error |
| CT06-T02 | 非线性方程列写 | 第6章 非线性电阻电路 | 06_nonlinear_resistive_circuits.md | 非线性约束、KCL/KVL、物理可行性 | nonlinear_relation_missing, linear_formula_misuse, result_verification_missing |
| CT06-T03 | 分段线性化分析 | 第6章 非线性电阻电路 | 06_nonlinear_resistive_circuits.md | 分段模型、区间假设、自洽检验 | piecewise_linear_region_error |
| CT06-T04 | 二极管分段分析 | 第6章 非线性电阻电路 | 06_nonlinear_resistive_circuits.md | 导通、截止、恒压降模型、假设检验 | diode_state_assumption_error, diode_voltage_drop_ignored, piecewise_linear_region_error |
| CT06-T05 | 图解法求工作点 | 第6章 非线性电阻电路 | 06_nonlinear_resistive_circuits.md | 负载线、图像交点、参考方向 | load_line_error |
| CT06-T06 | 小信号工作点与动态电阻 | 第6章 非线性电阻电路 | 06_nonlinear_resistive_circuits.md | 静态工作点、切线斜率、动态电阻 | nonlinear_operating_point_error, small_signal_equivalent_error |
| CT06-T07 | 小信号等效电路 | 第6章 非线性电阻电路 | 06_nonlinear_resistive_circuits.md | 直流交流分离、小信号等效、线性化条件 | small_signal_equivalent_error, small_signal_condition_error, small_signal_total_confusion, dc_ac_superposition_error |
| CT06-T08 | 限幅电路 | 第6章 非线性电阻电路 | 06_nonlinear_resistive_circuits.md | 二极管阈值、限幅电平、输出波形 | limiter_threshold_error, diode_state_assumption_error |
| CT06-T09 | 整流电路 | 第6章 非线性电阻电路 | 06_nonlinear_resistive_circuits.md | 半波整流、桥式整流、导通路径 | rectifier_conduction_interval_error, diode_voltage_drop_ignored |
| CT06-T10 | 非线性综合假设检验 | 第6章 非线性电阻电路 | 06_nonlinear_resistive_circuits.md | 方程法、图解法、分段法、小信号分析 | nonlinear_method_selection_error, result_verification_missing, small_signal_total_confusion |
| CT07-T01 | 阶跃函数与分段波形 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 单位阶跃、延迟阶跃、门函数、分段表达 | step_shift_error, piecewise_waveform_expression_error |
| CT07-T02 | 冲激函数与广义导数 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 单位冲激、广义导数、跳变量 | impulse_sampling_error, generalized_function_derivative_error, impulse_response_error |
| CT07-T03 | 冲激筛选积分 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 冲激面积、筛选性质、积分区间 | impulse_sampling_error |
| CT07-T04 | 电容伏安关系 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 电容电流、电压积分、初始电压 | capacitor_iv_relation_error, initial_value_error, integration_interval_error |
| CT07-T05 | 电容连续性与冲激电流 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 电容电压连续、广义导数、冲激电流 | capacitor_voltage_continuity_error, impulse_state_jump_error |
| CT07-T06 | 电容储能 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 电场储能、瞬时功率、能量变化 | energy_storage_error, capacitor_energy_formula_error, power_energy_confusion |
| CT07-T07 | 电容串并联与初始电压 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 电容等效、电荷守恒、初始电压分配 | capacitor_series_parallel_formula_error, initial_value_error, charge_conservation_error |
| CT07-T08 | 电感伏安关系 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 电感电压、电流积分、初始电流 | inductor_iv_relation_error, initial_value_error, integration_interval_error |
| CT07-T09 | 电感连续性与冲激电压 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 电感电流连续、广义导数、冲激电压 | inductor_current_continuity_error, impulse_state_jump_error |
| CT07-T10 | 电感储能 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 磁场储能、瞬时功率、能量释放 | energy_storage_error, inductor_energy_formula_error, power_energy_confusion |
| CT07-T11 | 电感串并联与初始电流 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 电感等效、磁链守恒、初始电流分配 | inductor_series_parallel_formula_error, initial_value_error, flux_linkage_conservation_error |
| CT07-T12 | 换路瞬间与初始条件 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 0-、0+、连续性、开关后等效 | dynamic_initial_condition_error, switching_moment_error, capacitor_voltage_continuity_error, inductor_current_continuity_error |
| CT07-T13 | 动态方程建立 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 状态变量、微分方程、初始条件 | dynamic_equation_setup_error, state_variable_selection_error, differential_equation_order_error, dynamic_initial_condition_error |
| CT07-T14 | 零输入与零状态概念 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 零输入、零状态、全响应、初始储能 | zero_input_response_confusion, zero_state_response_confusion, initial_state_zeroing_error |
| CT07-T15 | 自由强迫暂态稳态判断 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | 自由响应、强迫响应、暂态、稳态 | response_component_confusion, transient_steady_state_confusion |
| CT07-T16 | 积分器与微分器应用 | 第7章 电容、电感及动态电路 | 07_capacitors_inductors_dynamic_circuits.md | RC/RL 积分、微分、运放积分器、波形变换 | integrator_differentiator_confusion, op_amp_sign_error, piecewise_waveform_expression_error |
| CT08-T01 | 一阶电路识别 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 一阶电路、状态变量、储能元件独立性 | first_order_identification_error, state_variable_selection_error, storage_equivalence_error |
| CT08-T02 | RC 零输入响应 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 电容放电、初始电压、时间常数 | zero_input_response_confusion, initial_value_error, capacitor_voltage_continuity_error, time_constant_error |
| CT08-T03 | RL 零输入响应 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 电感放电、初始电流、时间常数 | zero_input_response_confusion, initial_value_error, inductor_current_continuity_error, time_constant_error |
| CT08-T04 | RC 阶跃响应 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 电容充电、零状态响应、终值、时间常数 | zero_state_response_confusion, final_value_error, time_constant_error, three_element_method_error |
| CT08-T05 | RL 阶跃响应 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 电感建流、零状态响应、终值、时间常数 | zero_state_response_confusion, final_value_error, time_constant_error, three_element_method_error |
| CT08-T06 | 三要素法 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 初始值、稳态值、时间常数、完全响应 | three_element_method_error, initial_value_error, final_value_error, source_zeroing_error |
| CT08-T07 | 换路瞬间变量判断 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 换路瞬间、状态连续性、非状态变量 | switching_moment_error, non_state_variable_continuity_error, dynamic_initial_condition_error |
| CT08-T08 | 分段换路响应 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 多次换路、分段初值、时间平移 | piecewise_switching_error, time_origin_shift_error, dynamic_initial_condition_error |
| CT08-T09 | 含受控源一阶电路 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 受控源、等效电阻、测试源法、时间常数 | time_constant_error, dependent_source_zeroed_error, test_source_direction_error |
| CT08-T10 | 含运放一阶电路 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 虚短虚断、电容反馈、积分器、饱和 | op_amp_linear_region_error, virtual_short_error, virtual_open_error, integrator_initial_value_error, op_amp_saturation_ignored |
| CT08-T11 | 正弦激励暂态稳态 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 正弦稳态、指数暂态、初始条件 | transient_steady_state_confusion, phase_reference_error |
| CT08-T12 | 冲激响应 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 阶跃响应、冲激响应、状态跳变 | impulse_response_error, impulse_from_step_error, impulse_state_jump_error, impulse_sampling_error |
| CT08-T13 | 卷积积分 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 冲激响应、零状态响应、卷积上限、分段输入 | convolution_integral_error, zero_state_response_confusion |
| CT08-T14 | 工程暂态应用 | 第8章 一阶电路的暂态分析 | 08_first_order_transient_analysis.md | 时间常数设计、阈值穿越、工程参数检查 | time_constant_error, threshold_crossing_error, logarithm_sign_error, engineering_parameter_check_missing |
| CT09-T01 | 二阶电路识别与状态变量选择 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 二阶系统、独立储能变量、状态变量 | second_order_identification_error, second_order_state_variable_error, storage_equivalence_error |
| CT09-T02 | RLC 串联零输入响应 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 串联 RLC、零输入响应、特征方程 | second_order_equation_setup_error, characteristic_root_error, second_order_initial_condition_error |
| CT09-T03 | RLC 并联零输入响应 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 并联 RLC、零输入响应、电导参数 | second_order_equation_setup_error, conductance_resistance_confusion, characteristic_root_error |
| CT09-T04 | 过阻尼响应判断与计算 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 过阻尼、两个实根、指数项 | damping_case_judgment_error, characteristic_root_error |
| CT09-T05 | 临界阻尼响应判断与计算 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 临界阻尼、重根、边界条件 | damping_case_judgment_error |
| CT09-T06 | 欠阻尼响应判断与计算 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 欠阻尼、阻尼振荡、阻尼频率 | damping_case_judgment_error, natural_frequency_error |
| CT09-T07 | 特征根与固有频率计算 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 特征根、阻尼系数、固有频率 | characteristic_root_error, damping_coefficient_error, natural_frequency_error |
| CT09-T08 | 初始条件与导数初值计算 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 初始状态、导数初值、状态连续性 | second_order_initial_condition_error, initial_derivative_error, initial_slope_error |
| CT09-T09 | 直流激励下二阶响应 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 直流强迫响应、全响应、稳态值 | second_order_forced_response_error, response_component_confusion |
| CT09-T10 | 一般二阶电路方程建立 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 状态变量、微分方程、元件约束 | second_order_equation_setup_error, response_component_confusion |
| CT09-T11 | 方波激励下二阶响应 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 分段激励、区间初值、振铃 | piecewise_switching_error, damping_design_error |
| CT09-T12 | 冲激响应与状态跳变 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 冲激输入、状态跳变、面积约束 | impulse_response_error, impulse_state_jump_error |
| CT09-T13 | RLC 串并联对偶关系 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 串并联对偶、电压电流对偶、参数映射 | rlc_duality_confusion |
| CT09-T14 | 二阶暂态工程应用 | 第9章 二阶电路的暂态分析 | 09_second_order_transient_analysis.md | 响应峰值、振铃、阻尼设计 | damping_design_error |
| CT10-T01 | 正弦量三要素识别 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 幅值、角频率、初相位 | sinusoidal_three_elements_error |
| CT10-T02 | 正弦量相位关系判断 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 相位差、参考相位、超前滞后 | phase_reference_error, phase_lead_lag_error |
| CT10-T03 | 有效值与平均值计算 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 有效值、平均值、周期积分 | rms_value_error |
| CT10-T04 | 正弦量与相量互换 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 相量定义、频率一致、时域还原 | phasor_conversion_error |
| CT10-T05 | 相量图绘制与相位判断 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 相量图、参考相量、相位差 | locus_phasor_error, phase_reference_error |
| CT10-T06 | 微分积分的相量对应 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 微分相量、积分相量、jω 因子 | phasor_conversion_error |
| CT10-T07 | R/L/C 相量模型 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 电阻、电感、电容、阻抗符号 | impedance_model_error, reactance_sign_error |
| CT10-T08 | 阻抗与导纳计算 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 复阻抗、复导纳、幅角 | admittance_model_error, impedance_model_error, complex_impedance_simplification_error |
| CT10-T09 | 串联正弦稳态电路分析 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 串联阻抗、交流分压、相量求和 | divider_ratio_error, complex_impedance_simplification_error, phasor_kcl_kvl_error |
| CT10-T10 | 并联正弦稳态电路分析 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 并联导纳、交流分流、支路相量 | divider_ratio_error, admittance_model_error, ac_node_analysis_error |
| CT10-T11 | 复阻抗网络化简 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 复数化简、串并联等效、幅角 | complex_impedance_simplification_error |
| CT10-T12 | 正弦稳态节点法 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 相量节点电压、导纳矩阵、KCL | ac_node_analysis_error, phasor_kcl_kvl_error |
| CT10-T13 | 正弦稳态网孔法 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 相量网孔电流、互阻抗、KVL | ac_mesh_analysis_error, reference_direction_error |
| CT10-T14 | 相量形式 KCL/KVL | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 相量 KCL、相量 KVL、同频条件 | phasor_kcl_kvl_error, same_frequency_condition_error |
| CT10-T15 | 正弦稳态定理应用 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 叠加、戴维南等效、测试源 | ac_theorem_application_error |
| CT10-T16 | 位形相量图与轨迹分析 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 位形相量、轨迹、相量端点 | locus_phasor_error |
| CT10-T17 | 交流电桥平衡 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 电桥平衡、复数条件、频率条件 | ac_bridge_balance_error |
| CT10-T18 | 正弦振荡器与移相器基础 | 第10章 正弦稳态分析 | 10_sinusoidal_steady_state_analysis.md | 振荡相位、增益条件、RC 移相 | oscillator_phase_condition_error, phase_shift_circuit_error |
| CT11-T01 | 瞬时功率表达式分析 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 瞬时功率、二倍频项、平均值 | instantaneous_power_expression_error, double_frequency_term_missing, active_power_error |
| CT11-T02 | 有功功率计算 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 有功功率、有效值、相位差 | active_power_error, rms_peak_confusion |
| CT11-T03 | 无功功率计算 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 无功功率、感容性、符号约定 | reactive_power_sign_error, power_factor_error |
| CT11-T04 | 视在功率与功率三角形 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 视在功率、功率三角形、量纲 | apparent_power_error, power_triangle_error |
| CT11-T05 | 功率因数计算 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 功率因数、超前滞后、相角 | power_factor_error, phase_lead_lag_error |
| CT11-T06 | 复功率计算 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 复功率、共轭、P/Q 分量 | complex_power_conjugate_error |
| CT11-T07 | 多负载复功率合成 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 复功率相加、无功抵消、负载合成 | complex_power_addition_error |
| CT11-T08 | 功率因数校正 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 目标功率因数、补偿无功、负载功率 | power_factor_correction_error, capacitor_compensation_error |
| CT11-T09 | 并联电容补偿计算 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 电容补偿、无功容量、电压等级 | capacitor_compensation_error |
| CT11-T10 | 最大有功功率传输 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 共轭匹配、负载阻抗、最大功率 | max_ac_power_transfer_error |
| CT11-T11 | 有功功率测量 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 功率表接线、读数、仪表损耗 | wattmeter_connection_error |
| CT11-T12 | 电能计量与交流参数测量 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | 电能表、伏安法、阻抗参数 | energy_meter_reading_error, ac_measurement_error |
| CT11-T13 | 功率单位与符号判断 | 第11章 正弦稳态电路的功率 | 11_sinusoidal_steady_state_power.md | W、var、V·A、功率正负 | power_unit_confusion, passive_sign_convention_error |
| CT12-T01 | 三相电源与相序判断 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | 三相对称、相序、相量组 | phase_sequence_error, balanced_three_phase_condition_error |
| CT12-T02 | 对称三相电压相量关系 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | 相电压、线电压、相量夹角 | phase_line_quantity_confusion, line_voltage_phase_voltage_error |
| CT12-T03 | Y 接电源与 Δ 接电源转换 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | 电源连接、线相量、等效转换 | star_delta_connection_error, phase_line_quantity_confusion, phase_sequence_error |
| CT12-T04 | Y 接负载线相量关系 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | Y 形负载、相电压、线电流 | line_voltage_phase_voltage_error, line_current_phase_current_error |
| CT12-T05 | Δ 接负载线相量关系 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | Δ 形负载、相电流、线电流 | line_current_phase_current_error |
| CT12-T06 | 对称三相电路分相计算 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | 一相等效、对称条件、相量还原 | per_phase_method_error, balanced_three_phase_condition_error, line_current_phase_current_error |
| CT12-T07 | Y-Y 对称三相电路计算 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | Y-Y 连接、中线、电流相量 | per_phase_method_error, neutral_current_error, line_voltage_phase_voltage_error |
| CT12-T08 | Y-Δ 对称三相电路计算 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | Y 电源、Δ 负载、线相转换 | star_delta_connection_error, line_current_phase_current_error, per_phase_method_error |
| CT12-T09 | Δ-Y/Δ-Δ 对称电路计算 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | Δ 电源、Δ 负载、等效转换 | star_delta_connection_error, line_current_phase_current_error |
| CT12-T10 | 三相功率计算 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | 三相有功、无功、功率因数 | three_phase_power_formula_error, power_factor_error |
| CT12-T11 | 单相供电与三相供电对比 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | 单相三相、线制、负载容量 | phase_line_quantity_confusion, distribution_safety_check_missing |
| CT12-T12 | 三相功率因数校正 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | 三相补偿、无功功率、电容接法 | power_factor_correction_error, capacitor_compensation_error |
| CT12-T13 | 不对称三相电路 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | 不对称负载、相电压、支路电流 | unbalanced_three_phase_error, neutral_shift_error, admittance_model_error |
| CT12-T14 | 中性点位移 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | 中性点、电位位移、中线 | neutral_point_error, neutral_shift_error |
| CT12-T15 | 三相功率测量 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | 二表法、读数符号、功率因数 | three_phase_power_measurement_error |
| CT12-T16 | 三相配电工程应用 | 第12章 三相正弦稳态电路 | 12_three_phase_sinusoidal_circuits.md | 配电安全、负载平衡、中性线 | distribution_safety_check_missing |
| CT13-T01 | 耦合电感与互感识别 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 自感、互感、磁耦合 | mutual_inductance_definition_error |
| CT13-T02 | 同名端判断 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 同名端、绕向、参考方向 | dot_convention_error |
| CT13-T03 | 互感电压符号判断 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 互感电压、极性、同名端 | mutual_voltage_polarity_error |
| CT13-T04 | 耦合系数计算 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 耦合系数、参数可行性、互感 | coupling_coefficient_error, coupled_inductor_energy_error |
| CT13-T05 | 耦合电感储能 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 储能公式、互感项、非负约束 | coupled_inductor_energy_error |
| CT13-T06 | 含耦合电感暂态分析 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 联立微分方程、初始电流、互感项 | coupled_inductor_kvl_error, mutual_inductance_definition_error, dynamic_initial_condition_error |
| CT13-T07 | 含耦合电感正弦稳态分析 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 相量模型、互阻抗、符号约定 | coupled_inductor_phasor_error, mutual_voltage_polarity_error |
| CT13-T08 | 网孔法分析耦合电感电路 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 网孔方程、互感电压、方向一致性 | coupled_inductor_mesh_error, reference_direction_error |
| CT13-T09 | 去耦等效电路 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 去耦等效、等效端口、符号保留 | decoupling_equivalent_error, mutual_voltage_polarity_error, port_definition_error |
| CT13-T10 | 反映阻抗计算 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 反映阻抗、输入阻抗、折算侧 | reflected_impedance_error, complex_impedance_simplification_error |
| CT13-T11 | 线性变压器等效分析 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 线性变压器、励磁支路、漏感 | linear_transformer_model_error |
| CT13-T12 | 理想变压器电压电流关系 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 匝数比、电压比、电流方向 | ideal_transformer_ratio_error, ideal_transformer_current_direction_error |
| CT13-T13 | 理想变压器阻抗变换 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 阻抗折算、匝比平方、端口侧 | ideal_transformer_impedance_transform_error |
| CT13-T14 | 三相变压器基础 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 三相连接、线相电压、相序 | three_phase_transformer_connection_error, phase_line_quantity_confusion |
| CT13-T15 | 磁耦合工程应用 | 第13章 含磁耦合的电路 | 13_magnetically_coupled_circuits.md | 阻抗匹配、隔离、工程约束 | transformer_power_relation_error |
