# 识图解题演示案例

## 案例 1：RC 一阶换路题截图

- 输入形式：题目截图，包含 RC 电路、开关从电源切换到接地、给定 R、C 和初始电压。
- 期望输出：识别开关状态，输出节点表、支路表，使用三要素法求 `uC(t)`。
- 展示亮点：电路结构标准化、时间原点平移、易错提醒。
- 可能失败点：开关位置识别错误，放电路径漏掉电阻。
- 对应知识库文件：`course_materials/01_circuit_theory/chapters/08_first_order_transient_analysis.md`

## 案例 2：RLC 二阶暂态题截图

- 输入形式：RLC 串联电路截图，给定初始 `uC(0-)` 和 `iL(0-)`。
- 期望输出：判断阻尼类型，列特征方程，求响应形式。
- 展示亮点：初始值和导数初值分离。
- 可能失败点：把欠阻尼频率写成固有频率。
- 对应知识库文件：`course_materials/01_circuit_theory/chapters/09_second_order_transient_analysis.md`

## 案例 3：正弦稳态相量电路题截图

- 输入形式：含 R、L、C 的交流节点电路图，给定频率和电源相量。
- 期望输出：转换阻抗/导纳，列相量 KCL，求节点电压。
- 展示亮点：相量域方程和复数计算。
- 可能失败点：电感导纳符号写反。
- 对应知识库文件：`course_materials/01_circuit_theory/chapters/10_sinusoidal_steady_state_analysis.md`

## 案例 4：正弦功率题截图

- 输入形式：单相负载或多负载并联题图，给定电压、电流或复功率。
- 期望输出：计算有功、无功、视在功率和功率因数。
- 展示亮点：复功率共轭和单位区分。
- 可能失败点：漏掉电流共轭，混淆 W/var/VA。
- 对应知识库文件：`course_materials/01_circuit_theory/chapters/11_sinusoidal_steady_state_power.md`

## 案例 5：三相 Y 接负载题截图

- 输入形式：对称三相电源和 Y 接负载图，给定线电压和每相阻抗。
- 期望输出：线相量转换、分相计算、三相功率。
- 展示亮点：线电压与相电压关系。
- 可能失败点：直接用线电压除以相阻抗。
- 对应知识库文件：`course_materials/01_circuit_theory/chapters/12_three_phase_sinusoidal_circuits.md`

## 案例 6：磁耦合同名端题截图

- 输入形式：含两个耦合线圈、同名端和网孔电流方向的题图。
- 期望输出：判断互感项符号，列网孔方程。
- 展示亮点：同名端和电流参考方向共同决定符号。
- 可能失败点：只看同名端位置，不看电流方向。
- 对应知识库文件：`course_materials/01_circuit_theory/chapters/13_magnetically_coupled_circuits.md`

