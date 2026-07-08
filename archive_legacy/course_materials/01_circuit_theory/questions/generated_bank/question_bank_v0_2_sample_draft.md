# 电路理论原创题库样例草稿 v0.2

> 本文件为 v0.2 方向样例，不替代完整正式题库。
> 设计目标：每题都包含可还原的电路结构表达，并强化多步骤分析、参考方向和错因诊断。
> 覆盖范围：第8章至第13章，每章 2 道，共 12 道。

---

## 第8章 一阶电路的暂态分析

### QCT2-08-001 含受控源的一阶 RC 暂态时间常数

- 所属章节：第8章 一阶电路的暂态分析
- 对应题型：CT08-T09
- 难度：综合
- 主要知识点：
  - 一阶电路时间常数
  - 含受控源等效电阻
  - 测试源法
- 关联错因标签：
  - time_constant_error
  - dependent_source_zeroed_error
  - test_source_direction_error
- 推荐复习文件：chapters/08_first_order_transient_analysis.md

#### 电路结构

```text
t >= 0 时求电容 C 端口看入等效电阻。

节点 x：电容上端，电压 v_x，相对参考地 0。
节点 0：参考地。

支路：
R1 = 6Ω：x -> 0，电流参考方向 x -> 0，控制量 u1 = v_x
R2 = 3Ω：x -> 0
Gm 受控电流源：x -> 0，i_g = 0.2u1 A
C = 0.5F：x -> 0，求 τ
```

#### 题目

换路后电容接在节点 x 与参考地之间。求换路后电路的时间常数 τ。要求说明求等效电阻时受控源如何处理。

#### 标准答案

受控源不能置零。断开电容，在 x-0 端口加测试电压 `v_t`。

端口电流为：

```text
i_t = v_t/R1 + v_t/R2 + 0.2v_t
    = v_t/6 + v_t/3 + 0.2v_t
    = 0.7v_t
```

所以：

```text
R_eq = v_t / i_t = 1/0.7 = 1.429Ω
τ = R_eq C = 1.429 × 0.5 = 0.714s
```

#### 解题思路

1. 求时间常数时，从电容端口看入求 `R_eq`。
2. 独立源置零，受控源保留。
3. 用测试源列 KCL 得到端口电流。
4. 用 `τ = R_eq C` 求时间常数。

#### 易错点

* 把受控电流源也置零，得到 `R1 || R2 = 2Ω`；
* 忘记测试源电流方向，导致等效电阻符号异常；
* 直接套 `τ = RC`，但没有求端口等效电阻。

#### 可用于诊断的学生错误表现

* 若学生写 `R_eq = R1 || R2 = 2Ω`，判断为 `dependent_source_zeroed_error`；
* 若学生写出负的 `R_eq` 但没有解释有源等效，判断为 `test_source_direction_error`；
* 若学生只写 `τ = 6 × 0.5` 或 `3 × 0.5`，判断为 `time_constant_error`。

#### 推荐反馈语

你这里主要问题是把受控源当成独立源关掉了。求含受控源电路的时间常数时，受控源必须保留，需要在电容端口加测试源并列 KCL 求 `R_eq`。

---

### QCT2-08-002 分段换路 RC 电路的初值继承

- 所属章节：第8章 一阶电路的暂态分析
- 对应题型：CT08-T08
- 难度：综合
- 主要知识点：
  - 分段换路
  - 电容电压连续
  - 时间原点平移
- 关联错因标签：
  - piecewise_switching_error
  - time_origin_shift_error
  - dynamic_initial_condition_error
- 推荐复习文件：chapters/08_first_order_transient_analysis.md

#### 电路结构

```text
            S
  +12V o---o/ o---R1=2kΩ---o x
             |              |
             o---R2=8kΩ-----+
                            |
                         C=100uF
                            |
                           0

0 <= t < 0.1s：S 接 +12V，C 经 R1 充电。
t >= 0.1s：S 接参考地，C 经 R1+R2 放电。
vC(t) = v_x(t)，参考方向 x -> 0。
```

#### 题目

已知 `vC(0-) = 0`。求 `vC(t)` 在 `0 <= t < 0.1s` 和 `t >= 0.1s` 两段的表达式。

#### 标准答案

第一段：

```text
τ1 = R1 C = 2kΩ × 100uF = 0.2s
vC(t) = 12(1 - e^{-t/0.2}) V
```

在 `t1 = 0.1s`：

```text
vC(0.1-) = 12(1 - e^{-0.5}) = 4.72V
vC(0.1+) = 4.72V
```

第二段：

```text
τ2 = (R1 + R2)C = 10kΩ × 100uF = 1s
vC(t) = 4.72e^{-(t-0.1)/1} V, t >= 0.1s
```

#### 解题思路

1. 每次换路后单独确定初值、终值和时间常数。
2. 第一段末值作为第二段初值。
3. 第二段指数项使用 `t - 0.1`，不能直接使用全局 `t`。

#### 易错点

* 第二段重新从 0V 开始；
* 第二段指数写成 `e^{-t/τ2}`，漏掉时间平移；
* 放电路径只取 R2，漏掉 R1。

#### 可用于诊断的学生错误表现

* 若第二段初值写 0V，判断为 `piecewise_switching_error`；
* 若第二段写 `4.72e^{-t}`，判断为 `time_origin_shift_error`；
* 若 `τ2 = R2C`，判断为 `time_constant_error`。

#### 推荐反馈语

分段换路题的关键是“上一段末值就是下一段初值”。第二段不是重新开始，而是从 `t=0.1s` 时电容已经具有的电压继续变化。

---

## 第9章 二阶电路的暂态分析

### QCT2-09-001 RLC 串联欠阻尼响应系数求解

- 所属章节：第9章 二阶电路的暂态分析
- 对应题型：CT09-T06
- 难度：综合
- 主要知识点：
  - RLC 串联欠阻尼
  - 初始值与导数初值
  - 响应系数求解
- 关联错因标签：
  - damping_case_judgment_error
  - initial_derivative_error
  - second_order_initial_condition_error
- 推荐复习文件：chapters/09_second_order_transient_analysis.md

#### 电路结构

```text
       R=1Ω       L=1H
  +---/\/\/\---ooooooo---o x
  |                      |
  |                    C=1F
  |                      |
  +----------------------+

零输入响应。vC(t)=v_x(t)，参考方向 x -> 0。
已知 vC(0-) = 10V，iL(0-) = 0A，iL 参考方向从左到右。
```

#### 题目

判断阻尼类型，并求 `t >= 0` 时 `vC(t)`。

#### 标准答案

```text
α = R/(2L) = 0.5
ω0 = 1/sqrt(LC) = 1
α < ω0，欠阻尼
ωd = sqrt(ω0^2 - α^2) = sqrt(0.75) = 0.866
```

响应形式：

```text
vC(t) = e^{-0.5t}(A cos0.866t + B sin0.866t)
```

初值：

```text
vC(0+) = 10V => A = 10
dvC/dt(0+) = iC(0+)/C
```

串联回路中 `iC(0+) = iL(0+) = 0`，所以 `dvC/dt(0+) = 0`。

对表达式求导并代入 `t=0`：

```text
0 = -0.5A + 0.866B
B = 0.5A/0.866 = 5.77
```

最终：

```text
vC(t) = e^{-0.5t}(10cos0.866t + 5.77sin0.866t) V
```

#### 解题思路

1. 根据 `α` 与 `ω0` 判断阻尼类型。
2. 写出欠阻尼通解。
3. 用 `vC(0+)` 和 `dvC/dt(0+)` 求两个系数。
4. 导数初值必须由电容电流确定。

#### 易错点

* 将 `ω0` 当作实际振荡角频率；
* 漏写 `e^{-αt}`；
* 只用 `vC(0+)` 一个条件求两个系数。

#### 可用于诊断的学生错误表现

* 若写成 `10cos(t)`，判断为 `damping_case_judgment_error` 或 `natural_frequency_error`；
* 若没有计算 `dvC/dt(0+)`，判断为 `initial_derivative_error`；
* 若只给一个系数，判断为 `second_order_initial_condition_error`。

#### 推荐反馈语

你只用了电容电压初值，但二阶响应有两个待定系数，还必须用导数初值。这里 `dvC/dt(0+)` 来自电容电流，而不是随意设定。

---

### QCT2-09-002 RLC 并联过阻尼节点电压响应

- 所属章节：第9章 二阶电路的暂态分析
- 对应题型：CT09-T03
- 难度：综合
- 主要知识点：
  - RLC 并联零输入
  - 电导形式阻尼系数
  - 初始导数
- 关联错因标签：
  - conductance_resistance_confusion
  - rlc_duality_confusion
  - second_order_initial_condition_error
- 推荐复习文件：chapters/09_second_order_transient_analysis.md

#### 电路结构

```text
节点 x 对地并联：
R = 0.25Ω
L = 1H，iL 参考方向 x -> 0
C = 0.5F，v(t)=v_x

初始条件：
v(0-) = 4V
iL(0-) = 0A
求零输入响应 v(t)。
```

#### 题目

写出并联 RLC 的特征方程，判断阻尼类型，并写出 `v(t)` 的响应形式与初始条件方程。

#### 标准答案

并联 RLC 节点电压方程：

```text
C d²v/dt² + G dv/dt + (1/L)v = 0
=> d²v/dt² + (G/C)dv/dt + (1/LC)v = 0
```

其中：

```text
G = 1/R = 4S
2α = G/C = 4/0.5 = 8 => α = 4
ω0 = 1/sqrt(LC) = 1/sqrt(0.5) = 1.414
```

因为 `α > ω0`，所以为过阻尼。

特征根：

```text
s1,2 = -α ± sqrt(α^2 - ω0^2)
     = -4 ± sqrt(16 - 2)
     = -4 ± 3.742
s1 = -0.258, s2 = -7.742
v(t) = A e^{-0.258t} + B e^{-7.742t}
```

初始条件：

```text
A + B = v(0+) = 4
KCL at 0+：C v'(0+) + Gv(0+) + iL(0+) = 0
0.5v'(0+) + 4×4 + 0 = 0
v'(0+) = -32V/s
```

代入导数条件：

```text
-0.258A - 7.742B = -32
A = -0.138, B = 4.138
v(t) = -0.138e^{-0.258t} + 4.138e^{-7.742t} V
```

#### 解题思路

1. 并联 RLC 使用 `G/(2C)`，不是 `R/(2L)`。
2. 先用题给参数判断阻尼类型，不能按标题预设。
3. 用 KCL 求导数初值。

#### 易错点

* 把串联公式 `R/(2L)` 用到并联电路；
* 没有检查参数是否真的过阻尼；
* 忘记由 KCL 求 `v'(0+)`。

#### 可用于诊断的学生错误表现

* 若写 `α=R/(2L)`，判断为 `conductance_resistance_confusion`；
* 若不列 KCL 求导数，判断为 `second_order_initial_condition_error`；
* 若标题说过阻尼就直接写两个实根，判断为 `damping_case_judgment_error`。

#### 推荐反馈语

并联 RLC 的阻尼公式与串联 RLC 是对偶关系，不能直接套 `R/(2L)`。先用题给参数算出 `α` 和 `ω0`，再判断阻尼类型。

---

## 第10章 正弦稳态分析

### QCT2-10-001 交流节点法求含 RLC 节点电压

- 所属章节：第10章 正弦稳态分析
- 对应题型：CT10-T12
- 难度：标准
- 主要知识点：
  - 相量域节点法
  - 阻抗与导纳
  - KCL
- 关联错因标签：
  - ac_node_analysis_error
  - admittance_model_error
  - phasor_kcl_kvl_error
- 推荐复习文件：chapters/10_sinusoidal_steady_state_analysis.md

#### 电路结构

```text
有效值相量，ω=1000rad/s。

节点 a 连接三条支路：
1. R=1kΩ：a -> 0
2. C=1uF：a -> 0
3. L=0.5H：a -> 节点 b

节点 b 由理想电压源固定：
Ub = 10∠0° V

求 Ua。
```

#### 题目

用交流节点法求节点 a 的电压相量 `Ua`。

#### 标准答案

```text
YR = 1/1000 = 0.001S
YC = jωC = j0.001S
ZL = jωL = j500Ω
YL = 1/ZL = -j0.002S
```

对节点 a 列 KCL：

```text
YR Ua + YC Ua + YL(Ua - Ub) = 0
(YR + YC + YL)Ua = YL Ub
(0.001 + j0.001 - j0.002)Ua = (-j0.002)10
(0.001 - j0.001)Ua = -j0.02
Ua = (-j0.02)/(0.001 - j0.001)
Ua = 10 - j10 V = 14.14∠-45° V
```

#### 解题思路

1. 统一使用有效值相量。
2. 先将支路换成导纳。
3. 对节点 a 写相量 KCL。
4. 用复数除法求节点电压。

#### 易错点

* 电感导纳写成 `j0.002S`；
* 把 `Ub` 当成电流源项直接相加；
* 在相量 KCL 中混入瞬时值。

#### 可用于诊断的学生错误表现

* 若 `YL` 符号写反，判断为 `admittance_model_error`；
* 若方程写成 `Ua/R + C dUa/dt + ...`，判断为 `phasor_kcl_kvl_error`；
* 若漏写 `(Ua - Ub)`，判断为 `ac_node_analysis_error`。

#### 推荐反馈语

你列节点方程时没有先统一到相量域。交流节点法中每条支路都要写成导纳形式，电感导纳是 `1/(jωL)`，符号为负虚数。

---

### QCT2-10-002 RC 移相电路输出相位判断

- 所属章节：第10章 正弦稳态分析
- 对应题型：CT10-T18
- 难度：标准
- 主要知识点：
  - RC 移相电路
  - 传递函数相角
  - 输出端口定义
- 关联错因标签：
  - phase_shift_circuit_error
  - phase_lead_lag_error
  - phasor_conversion_error
- 推荐复习文件：chapters/10_sinusoidal_steady_state_analysis.md

#### 电路结构

```text
         R=10kΩ
Ui o---/\/\/\---o Uo
                 |
              C=0.01uF
                 |
                0

输入 Ui 为有效值相量，f=1kHz。
输出 Uo 取电容两端电压，参考方向 Uo -> 0。
```

#### 题目

求 `H(jω)=Uo/Ui` 的幅值和相角，并判断输出相对输入超前还是滞后。

#### 标准答案

```text
ω = 2πf = 6283rad/s
ωRC = 6283 × 10kΩ × 0.01uF = 0.628
H(jω)= ZC/(R+ZC) = 1/(1+jωRC)
|H| = 1/sqrt(1+(ωRC)^2) = 0.847
∠H = -atan(ωRC) = -32.1°
```

输出电容电压相对输入滞后 `32.1°`。

#### 解题思路

1. 先确认输出取在电容上。
2. 写出电压分压形式。
3. 化为 `1/(1+jωRC)`。
4. 由相角判断滞后。

#### 易错点

* 把电容输出误判为超前；
* 将 `ωRC` 的单位或数量级算错；
* 忽略输出端口，套用了电阻输出的结论。

#### 可用于诊断的学生错误表现

* 若说电容电压超前输入，判断为 `phase_shift_circuit_error`；
* 若输出端口换成电阻仍给同一结论，判断为 `phase_lead_lag_error`；
* 若使用峰值相量和有效值相量混算，判断为 `phasor_conversion_error`。

#### 推荐反馈语

本题先看输出端口：输出取在电容两端，所以传递函数是 `1/(1+jωRC)`，相角为负，表示输出滞后输入。

---

## 第11章 正弦稳态电路的功率

### QCT2-11-001 多负载复功率相加与电流求解

- 所属章节：第11章 正弦稳态电路的功率
- 对应题型：CT11-T07
- 难度：综合
- 主要知识点：
  - 复功率相加
  - 电流共轭关系
  - 多负载并联
- 关联错因标签：
  - complex_power_addition_error
  - complex_power_conjugate_error
  - active_power_error
- 推荐复习文件：chapters/11_sinusoidal_steady_state_power.md

#### 电路结构

```text
有效值相量。

            Load 1：S1 = 3kW + j2kvar
U=220∠0°V o--------------------------o 0
            Load 2：S2 = 2kW - j1kvar

两个负载并联，均按吸收功率约定。
求总复功率和电源电流相量 I。
```

#### 题目

求总复功率 `S_total`，并求电源供给的电流相量 `I`。

#### 标准答案

```text
S_total = S1 + S2 = 5kW + j1kvar
S = U I^*
I^* = S/U = (5000 + j1000)/220 = 22.73 + j4.55 A
I = 22.73 - j4.55 A = 23.18∠-11.3° A
```

#### 解题思路

1. 并联负载的复功率可以直接代数相加。
2. 由 `S = U I^*` 求电流。
3. 注意最后要对 `I^*` 取共轭得到 `I`。

#### 易错点

* 把无功功率绝对值相加为 `j3kvar`；
* 用 `I = S/U`，漏掉共轭；
* 将 `VA`、`W`、`var` 单位混用。

#### 可用于诊断的学生错误表现

* 若总无功写成 `j3kvar`，判断为 `complex_power_addition_error`；
* 若电流相角写 `+11.3°`，判断为 `complex_power_conjugate_error`；
* 若把总功率写成 `6kVA` 且无 P/Q，判断为 `active_power_error`。

#### 推荐反馈语

你这里的复功率可以直接相加，但电流不能用 `I=S/U` 直接求。复功率定义是 `S=UI^*`，所以最后要对计算出的 `I^*` 取共轭。

---

### QCT2-11-002 功率因数校正并联电容计算

- 所属章节：第11章 正弦稳态电路的功率
- 对应题型：CT11-T08
- 难度：综合
- 主要知识点：
  - 功率因数校正
  - 无功补偿
  - 并联电容
- 关联错因标签：
  - power_factor_correction_error
  - capacitor_compensation_error
  - reactive_power_sign_error
- 推荐复习文件：chapters/11_sinusoidal_steady_state_power.md

#### 电路结构

```text
单相负载，U = 220V(rms), f = 50Hz。

电源 o-----+----- 感性负载：P=4kW, cosφ1=0.75 lagging -----o
           |
           +----- 并联补偿电容 C ---------------------------o

目标功率因数：cosφ2=0.95 lagging。
```

#### 题目

求需要并联的电容容量 C，并说明补偿后负载本身的有功功率是否改变。

#### 标准答案

```text
φ1 = arccos0.75 = 41.41°，tanφ1 = 0.882
φ2 = arccos0.95 = 18.19°，tanφ2 = 0.329
需要补偿的无功：
Qc = P(tanφ1 - tanφ2)
   = 4000(0.882 - 0.329)
   = 2212var
```

电容无功：

```text
Qc = ωCU^2
C = Qc/(ωU^2)
  = 2212/(2π×50×220^2)
  = 145.5uF
```

补偿后负载自身有功功率不变，变化的是电源侧提供的无功和总电流。

#### 解题思路

1. 由功率因数求 `tanφ`。
2. 用目标无功差求电容补偿量。
3. 单相并联电容用 `Qc=ωCU^2`。
4. 区分负载功率与电源侧总功率因数。

#### 易错点

* 将 `tanφ1 - tanφ2` 写反；
* 用线电压/相电压公式混入单相题；
* 认为电容改变了负载本身有功功率。

#### 可用于诊断的学生错误表现

* 若算出负电容，判断为 `reactive_power_sign_error`；
* 若用 `C=P/(ωU^2)` 不含 `tan` 差，判断为 `capacitor_compensation_error`；
* 若说负载 P 变小，判断为 `power_factor_correction_error`。

#### 推荐反馈语

并联电容只就地提供一部分容性无功，不改变原感性负载本身的有功功率。计算时要用补偿前后 `tanφ` 的差值。

---

## 第12章 三相正弦稳态电路

### QCT2-12-001 Y 接负载线电压与相电压计算

- 所属章节：第12章 三相正弦稳态电路
- 对应题型：CT12-T04
- 难度：标准
- 主要知识点：
  - Y 接负载
  - 线电压与相电压
  - 对称三相相量
- 关联错因标签：
  - line_voltage_phase_voltage_error
  - phase_line_quantity_confusion
  - per_phase_method_error
- 推荐复习文件：chapters/12_three_phase_sinusoidal_circuits.md

#### 电路结构

```text
正序三相电源，线电压 UAB = 380∠30° V。
对称 Y 接负载，每相阻抗 ZY = 20∠30°Ω。
负载中性点 n 与电源中性点 N 相连。

A ---- ZA ---- n
B ---- ZB ---- n
C ---- ZC ---- n
```

#### 题目

求 A 相负载相电压 `UAN`、A 相电流 `IA` 和三相总有功功率。

#### 标准答案

正序 Y 接关系：

```text
UAB = sqrt(3) UAN ∠30°
UAN = 380/sqrt(3) ∠0° = 219.4∠0° V
IA = UAN/ZY = 219.4∠0° / 20∠30° = 10.97∠-30° A
P = 3 Uph Iph cos30°
  = 3 × 219.4 × 10.97 × 0.866
  = 6251W
```

#### 解题思路

1. 从线电压换成相电压。
2. 用一相等效求相电流。
3. 对称三相总功率为三倍单相有功。

#### 易错点

* 直接用 380V 除以相阻抗；
* 忘记线电压相对相电压超前 30°；
* 把线电流和相电流关系混到 Y 接中。

#### 可用于诊断的学生错误表现

* 若 `IA=380/20`，判断为 `line_voltage_phase_voltage_error`；
* 若 `UAN` 相角写 `30°`，判断为 `phase_line_quantity_confusion`；
* 若功率只算一相，判断为 `per_phase_method_error`。

#### 推荐反馈语

Y 接负载分相计算时要先把线电压换成相电压。正序时 `UAB` 比 `UAN` 超前 30°，所以本题 `UAN=220∠0°V`。

---

### QCT2-12-002 不对称三相无中线中性点位移

- 所属章节：第12章 三相正弦稳态电路
- 对应题型：CT12-T14
- 难度：综合
- 主要知识点：
  - 不对称三相
  - 中性点位移
  - 节点法
- 关联错因标签：
  - neutral_shift_error
  - unbalanced_three_phase_error
  - admittance_model_error
- 推荐复习文件：chapters/12_three_phase_sinusoidal_circuits.md

#### 电路结构

```text
正序三相相电压：
UA = 220∠0° V
UB = 220∠-120° V
UC = 220∠120° V

Y 接不对称负载，无中线：
ZA = 10Ω
ZB = 20Ω
ZC = 40Ω

负载中性点为 n，电源中性点为 N。
求 UnN。
```

#### 题目

用节点法求负载中性点位移电压 `UnN`，并说明为什么不能直接令各相负载电压均为 220V。

#### 标准答案

令：

```text
YA=0.1S, YB=0.05S, YC=0.025S
UnN = (UA YA + UB YB + UC YC)/(YA + YB + YC)
```

计算：

```text
UA YA = 22 + j0
UB YB = 11∠-120° = -5.5 - j9.526
UC YC = 5.5∠120° = -2.75 + j4.763
分子 = 13.75 - j4.763
分母 = 0.175
UnN = 78.57 - j27.22 V = 83.15∠-19.1° V
```

各相负载电压为：

```text
Uan = UA - UnN
Ubn = UB - UnN
Ucn = UC - UnN
```

因此无中线且负载不对称时，负载相电压不再等于电源相电压。

#### 解题思路

1. 判断无中线，不对称负载会产生中性点位移。
2. 对负载中性点 n 列节点方程。
3. 用相量计算位移电压。
4. 再由电源相电压减去位移电压得到负载相电压。

#### 易错点

* 仍把三相负载电压都当 220V；
* 把三相相量按标量相加；
* 漏掉导纳权重。

#### 可用于诊断的学生错误表现

* 若直接写 `IA=220/10, IB=220/20, IC=220/40`，判断为 `neutral_shift_error`；
* 若将 `UA+UB+UC=0` 后认为 `UnN=0`，判断为 `unbalanced_three_phase_error`；
* 若公式中使用阻抗加权而非导纳加权，判断为 `admittance_model_error`。

#### 推荐反馈语

无中线的不对称 Y 负载不能分相独立计算。负载中性点会漂移，必须先用节点法求 `UnN`，再求每相实际负载电压。

---

## 第13章 含磁耦合的电路

### QCT2-13-001 同名端判断耦合电感网孔方程

- 所属章节：第13章 含磁耦合的电路
- 对应题型：CT13-T08
- 难度：综合
- 主要知识点：
  - 同名端
  - 互感电压符号
  - 耦合电感网孔方程
- 关联错因标签：
  - dot_convention_error
  - mutual_voltage_polarity_error
  - coupled_inductor_mesh_error
- 推荐复习文件：chapters/13_magnetically_coupled_circuits.md

#### 电路结构

```text
正弦稳态，ω=100rad/s，有效值相量。

       dot                  dot
   o---● L1=1H ---R1=10Ω---o
   |                        |
  Us=50∠0°V              R2=20Ω
   |                        |
   o---  L2=0.5H  ---●------o
       no dot            dot

M = 0.2H。
网孔电流 I1、I2 均取顺时针。
I1 从 L1 同名端流入，I2 从 L2 非同名端流入。
```

#### 题目

写出两个网孔的相量 KVL 方程，不要求求解数值。

#### 标准答案

```text
jωL1 = j100
jωL2 = j50
jωM = j20
```

由于 `I1` 从 L1 同名端流入，而 `I2` 从 L2 非同名端流入，互感项取负号：

```text
(10 + j100)I1 - j20 I2 = 50∠0°
-j20 I1 + (20 + j50)I2 = 0
```

#### 解题思路

1. 先标出两个电流是否从各自同名端流入。
2. 两个电流同时流入同名端或同时流出同名端时互感项同号；一个流入一个流出时互感项异号。
3. 将自感阻抗和互感阻抗写入网孔方程。

#### 易错点

* 只看同名端在图上同侧，不看电流参考方向；
* 漏写互感项；
* 将 `jωM` 写成 `ωM`。

#### 可用于诊断的学生错误表现

* 若互感项写 `+j20`，判断为 `mutual_voltage_polarity_error`；
* 若完全没有互感项，判断为 `coupled_inductor_mesh_error`；
* 若判断同名端时只凭位置，判断为 `dot_convention_error`。

#### 推荐反馈语

互感项符号不是只看点在不在同一侧，而是看网孔电流相对同名端的流入/流出关系。本题一个从同名端流入、一个从非同名端流入，所以互感项取负号。

---

### QCT2-13-002 理想变压器阻抗变换与端口侧判断

- 所属章节：第13章 含磁耦合的电路
- 对应题型：CT13-T13
- 难度：标准
- 主要知识点：
  - 理想变压器
  - 阻抗折算
  - 匝比平方
- 关联错因标签：
  - ideal_transformer_impedance_transform_error
  - ideal_transformer_ratio_error
  - port_definition_error
- 推荐复习文件：chapters/13_magnetically_coupled_circuits.md

#### 电路结构

```text
理想变压器，n = N1/N2 = 4。

原边端口 a-b：从原边看入等效阻抗 Zin。
副边接负载 ZL = 8 + j6Ω。

      a o---- N1 : N2 ----o c
                           |
                         ZL=8+j6Ω
      b o------------------o d
```

#### 题目

求从原边端口 a-b 看入的等效阻抗 `Zin`。若学生写成 `Zin = ZL/n^2`，错在哪里？

#### 标准答案

从副边折算到原边：

```text
Zin = n^2 ZL = 4^2(8 + j6) = 128 + j96Ω
```

`ZL/n^2` 是从原边折算到副边时的关系，方向反了。

#### 解题思路

1. 确认要求“从原边看入”。
2. `n=N1/N2`，副边阻抗折算到原边乘以 `n^2`。
3. 复阻抗整体乘以匝比平方。

#### 易错点

* 用 `n` 而不是 `n^2`；
* 折算方向反了；
* 只折算电阻不折算电抗。

#### 可用于诊断的学生错误表现

* 若写 `4(8+j6)`，判断为 `ideal_transformer_impedance_transform_error`；
* 若写 `(8+j6)/16`，判断为 `port_definition_error`；
* 若只算 `128Ω`，判断为 `ideal_transformer_ratio_error`。

#### 推荐反馈语

你把阻抗折算方向弄反了。题目问从原边看入，副边负载要乘以 `(N1/N2)^2` 折算到原边，而不是除以这个系数。
