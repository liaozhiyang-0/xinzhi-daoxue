from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from normalize_dataset import DEFAULT_OUTPUT, natural_key, write_json, write_jsonl

COURSE_ORDER = ("CT", "AE", "DE", "SS", "DSP", "COMM")
CURATED_ROOT_NAME = "curated_answer_sets"


def answer(final: str, *steps: str) -> dict[str, Any]:
    return {"final_answer": final, "steps": list(steps)}


STANDARD_ANSWERS: dict[str, dict[str, Any]] = {
    "KB-CT-1-9": answer(
        "充满还需 4 s。",
        "电池尚缺的能量为 (1-20%)×60 J=48 J。",
        "恒流充电功率为 P=UI=12 V×1 A=12 W。",
        "所需时间 t=48 J/12 W=4 s。",
    ),
    "KB-CT-1-10": answer(
        "电能为 12 Wh=43.2 kJ；可工作 48 h；负载电流约 20.83 mA。",
        "1000 mA·h=1 A·h，因此电池能量 E=12 V×1 A·h=12 Wh。",
        "换算为焦耳：12 Wh×3600=43.2 kJ。",
        "工作时间 t=12 Wh/0.25 W=48 h。",
        "负载电流 I=P/U=0.25/12 A≈20.83 mA。",
    ),
    "KB-CT-7-7": answer(
        "释放能量 84 J；平均功率 8.4 W；平均放电电流大小 0.12 A。",
        "C=20 mF=0.02 F，释放能量为 C(U1²-U2²)/2。",
        "代入 100 V 和 40 V，得到 ΔW=84 J。",
        "平均功率为 84 J/10 s=8.4 W。",
        "放出电荷量 C(U1-U2)=1.2 C，平均电流大小为 1.2/10=0.12 A。",
    ),
    "KB-CT-10-4": answer(
        "电流 i 超前电压 u 70°。",
        "将电流改写为余弦：i=3cos(100t+10°) A。",
        "电压相位为 -60°，电流相位为 +10°。",
        "相位差 φi-φu=10°-(-60°)=70°。",
    ),
    "KB-AE-1-5-6": answer(
        "输出电压是中频区输出电压的 10^(-3/20)≈0.708 倍。",
        "电压增益的分贝变化满足 20lg(UH/UM)=-3 dB。",
        "因此 UH/UM=10^(-3/20)≈0.7079。",
    ),
    "KB-AE-1-5-2": answer(
        "输出电阻 R0=250 Ω。",
        "把放大器输出端等效为戴维南源，负载比值为 UL/Uoc=RL/(R0+RL)。",
        "题给输出下降 20%，故 UL/Uoc=0.8。",
        "由 0.8=1000/(R0+1000) 解得 R0=250 Ω。",
    ),
    "KB-AE-2-3-5": answer(
        "vo/vi=Avv/(1+Avv)；为使误差不超过 0.01%，Avv 至少为 9999。",
        "电压跟随器满足 vo=Avv(vi-vo)。",
        "整理得 vo/vi=Avv/(1+Avv)。",
        "相对跟随误差为 1/(1+Avv)。",
        "令 1/(1+Avv)≤10^-4，得到 Avv≥9999。",
    ),
    "KB-AE-1-2-1": answer(
        "三式分别为 5sin(20000πt) V、220√2sin(100πt) V、"
        "50sin(2000πt) mV。",
        "峰峰值 10 V 对应幅值 5 V，10 kHz 对应角频率 20000π rad/s。",
        "有效值 220 V 对应幅值 220√2 V，50 Hz 对应角频率 100π rad/s。",
        "峰峰值 100 mV 对应幅值 50 mV，周期 1 ms 对应角频率 2000π rad/s。",
    ),
    "KB-DE-2-5-2": answer(
        "4 种基本逻辑值是 0、1、x（未知）和 z（高阻）。",
        "0 和 1 表示确定的低、高逻辑值。",
        "x 表示未知或冲突状态，z 表示高阻态。",
    ),
    "KB-DE-3-1-3": answer(
        "数字逻辑变量通常取 0 或 1；作为开关使用的三极管工作在截止区或饱和区。",
        "逻辑 0、1 对应两个离散逻辑状态。",
        "三极管截止时近似断开，饱和时近似导通。",
    ),
    "KB-DE-7-2-3": answer(
        "芯片需要 10 根复用地址线。",
        "1M=2^20，因此完整地址共有 20 位。",
        "DRAM 将行、列地址分时送入，通常各占 10 位。",
        "同一组 10 根引脚先送行地址、再送列地址。",
    ),
    "KB-DE-4-2-3": answer(
        "Y=¬(A⊕B⊕C⊕D)，可用三级异或后接一级非门实现。",
        "A⊕B⊕C⊕D 在 1 的个数为奇数时等于 1。",
        "偶校验要求偶数个 1 时输出 1，因此对异或结果取反。",
    ),
    "KB-SS-7-30": answer(
        "第 5 次约为 2.373 m，第 8 次约为 1.001 m。",
        "第 n 次弹起高度 hn=10(3/4)^n m。",
        "h5=10(3/4)^5=2.373046875 m。",
        "h8=10(3/4)^8=1.001129150390625 m。",
    ),
    "KB-SS-7-31": answer(
        "y(k)=k(k+1)/2，k≥0。",
        "建立差分方程 y(k)-y(k-1)=k，并取 y(-1)=0。",
        "累加得到 y(k)=Σ(j=0…k)j=k(k+1)/2。",
    ),
    "KB-SS-8-5": answer(
        "当 aT>0 时，终值为 b；若 aT≤0，不能直接得到该有限终值。",
        "对 aT>0，有 exp(-akT) 随 k→∞ 趋于 0。",
        "因此 f(k)=b[1-exp(-akT)] 的极限为 b。",
        "终值定理还要求相关极点满足收敛条件。",
    ),
    "KB-SS-10-23": answer(
        "输出序号为 0,16,8,24,4,20,12,28,2,18,10,26,6,22,14,30,"
        "1,17,9,25,5,21,13,29,3,19,11,27,7,23,15,31。",
        "32=2^5，把输入自然序号写成 5 位二进制。",
        "将每个序号的 5 位二进制倒序，再换回十进制。",
    ),
    "KB-DSP-2-11": answer(
        "y(n)=[φ^(n+1)-ψ^(n+1)]/√5，其中 φ=(1+√5)/2，ψ=(1-√5)/2。",
        "特征方程 r²-r-1=0，根为 φ、ψ。",
        "通解为 y(n)=C1φ^n+C2ψ^n。",
        "代入 y(0)=1、y(1)=1，得到斐波那契形式 y(n)=F(n+1)。",
    ),
    "KB-DSP-2-24": answer(
        "x(0)=2；n≠0 时 x(n)=1/|n|!，收敛域为 0<|z|<∞。",
        "展开 e^z=Σ(k≥0)z^k/k!，对应负时间项 x(-k)=1/k!。",
        "展开 e^(1/z)=Σ(k≥0)z^(-k)/k!，对应正时间项 x(k)=1/k!。",
        "两个展开在 k=0 处各贡献 1，所以 x(0)=2。",
    ),
    "KB-DSP-2-28": answer(
        "a≠1 时 w(n)=[1-a^(n+1)]/(1-a)·u(n)；a=1 时 w(n)=(n+1)u(n)。",
        "两个右边序列卷积后，n≥0 时 w(n)=Σ(k=0…n)a^(n-k)。",
        "该有限几何级数在 a≠1 时等于 [1-a^(n+1)]/(1-a)。",
        "a=1 时共有 n+1 项。",
    ),
    "KB-DSP-3-14": answer(
        "直接 DFT 约 125.80864 s；基 2 FFT 约 0.7168 s。",
        "直接 DFT 需 N²=1,048,576 次复乘和 N(N-1)=1,047,552 次复加。",
        "直接计算时间为 104.8576 s+20.95104 s=125.80864 s。",
        "基 2 FFT 需 (N/2)log2N=5120 次复乘和 Nlog2N=10240 次复加。",
        "FFT 时间为 0.512 s+0.2048 s=0.7168 s。",
    ),
    "KB-COMM-1-1": answer(
        "I(e)≈3.252 bit，I(x)≈8.966 bit。",
        "单个符号的信息量 I=-log2p。",
        "I(e)=-log2(0.105)≈3.2515 bit。",
        "I(x)=-log2(0.002)≈8.9658 bit。",
    ),
    "KB-COMM-1-2": answer(
        "该符号集的平均信息量为 1.75 bit/符号。",
        "第四个符号概率为 1-1/4-1/8-1/8=1/2。",
        "熵 H=-Σpi log2pi。",
        "代入 1/4、1/8、1/8、1/2，得到 H=1.75 bit/符号。",
    ),
    "KB-COMM-1-6": answer(
        "二进制信息速率为 2500 bit/s；十六进制时为 10000 bit/s。",
        "码元间隔 0.4 ms，所以码元速率为 1/0.0004=2500 Baud。",
        "二进制每码元携带 1 bit，因此 Rb=2500 bit/s。",
        "十六进制每码元携带 log2(16)=4 bit，因此 Rb=10000 bit/s。",
    ),
    "KB-COMM-1-8": answer(
        "码元错误率为 1.0×10^-4。",
        "四进制每码元含 2 bit，码元速率为 2400/2=1200 Baud。",
        "0.5 h=1800 s，共接收 1200×1800=2.16×10^6 个码元。",
        "错误率为 216/(2.16×10^6)=1.0×10^-4。",
    ),
}


ERROR_CASES: dict[str, dict[str, Any]] = {
    "KB-CT-7-24": {
        "solution": answer(
            "释放能量 0.192 J；按电流关联参考方向，电感电压为 -320 V，"
            "其大小为 320 V。",
            "释放能量为 L(I1²-I2²)/2=0.192 J。",
            "di/dt=(0.2-1)/1 ms=-800 A/s。",
            "关联参考方向下 u=L·di/dt=0.4×(-800)=-320 V。",
        ),
        "error_type": "sign_error",
        "attempt": {
            "raw_text": "先算能量为0.192 J。电流变化率为800 A/s，"
            "所以电感电压 u=L·di/dt=320 V。",
            "final_answer": "0.192 J，320 V",
            "steps": [
                {
                    "step_id": "energy",
                    "sequence": 1,
                    "content": "用磁场能量差算得释放能量0.192 J。",
                    "claimed_result": "0.192 J",
                    "unit": "J",
                },
                {
                    "step_id": "voltage-sign",
                    "sequence": 2,
                    "content": "把下降的电流变化率写成+800 A/s。",
                    "expression": "u=0.4×800",
                    "claimed_result": "320 V",
                    "unit": "V",
                },
            ],
        },
        "error_step": "voltage-sign",
    },
    "KB-CT-8-6": {
        "solution": answer(
            "再经过 4 s 后电流约 4.98 A；R=0.5 Ω。",
            "由 36.8/100≈e^-1 得时间常数 τ=2 s。",
            "题目的“再经过4 s”表示总时间为6 s，所以 i=100e^(-6/2)=4.98 A。",
            "RL 放电的 τ=L/R，因此 R=L/τ=1/2=0.5 Ω。",
        ),
        "error_type": "numeric_error",
        "attempt": {
            "raw_text": "τ=2 s。再经过4 s时直接取t=4 s，"
            "所以i=100e^-2=13.5 A，R=0.5 Ω。",
            "final_answer": "13.5 A，0.5 Ω",
            "steps": [
                {
                    "step_id": "tau",
                    "sequence": 1,
                    "content": "由2 s后剩36.8%得到τ=2 s。",
                    "claimed_result": "τ=2 s",
                },
                {
                    "step_id": "elapsed-time",
                    "sequence": 2,
                    "content": "把“再经过4 s”误当成从初始时刻起4 s。",
                    "expression": "i=100e^(-4/2)",
                    "claimed_result": "13.5 A",
                    "unit": "A",
                },
            ],
        },
        "error_step": "elapsed-time",
    },
    "KB-AE-3-2-2": {
        "solution": answer(
            "取 VT≈25.9 mV 时，IS≈1.74×10^-15 A；电流增大10倍后电压约0.760 V。",
            "正向区近似 I=IS exp(V/VT)。",
            "IS=1 mA/exp(0.7/0.0259)≈1.74×10^-15 A。",
            "电流增大10倍只使电压增加 VT ln10≈59.6 mV。",
        ),
        "error_type": "formula_mismatch",
        "attempt": {
            "raw_text": "二极管电流增大10倍，因此电压也增大10倍，"
            "新电压为7 V。",
            "final_answer": "7 V",
            "steps": [
                {
                    "step_id": "linear-assumption",
                    "sequence": 1,
                    "content": "把二极管错误地当成线性电阻。",
                    "expression": "V2=10V1",
                    "claimed_result": "7 V",
                    "unit": "V",
                }
            ],
        },
        "error_step": "linear-assumption",
    },
    "KB-AE-8-3-9": {
        "solution": answer(
            "闭环中频增益约3.297，带宽约910 kHz。",
            "环路增益 A0F=300×0.3=90。",
            "闭环增益 A0/(1+A0F)=300/91≈3.297。",
            "单极点负反馈带宽扩大为(1+A0F)×10 kHz=910 kHz。",
        ),
        "error_type": "formula_mismatch",
        "attempt": {
            "raw_text": "闭环增益用A/(1+F)，得到300/1.3=230.77；"
            "带宽仍为10 kHz。",
            "final_answer": "230.77，10 kHz",
            "steps": [
                {
                    "step_id": "loop-gain",
                    "sequence": 1,
                    "content": "反馈分母漏掉开环增益与反馈系数的乘积。",
                    "expression": "Af=A/(1+F)",
                    "claimed_result": "230.77",
                }
            ],
        },
        "error_step": "loop-gain",
    },
    "KB-DE-4-2-2": {
        "solution": answer(
            "若ABC为三位二进制数且A为最高位，则F=A+BC；"
            "两级与非实现为 F=NAND(NAND(A,A),NAND(B,C))。",
            "输出为1的最小项是3、4、5、6、7。",
            "化简 Σm(3,4,5,6,7)=A+BC。",
            "利用德摩根律把或表达式改写为两输入与非门网络。",
        ),
        "error_type": "boolean_inequivalence",
        "attempt": {
            "raw_text": "只要任意输入为1，数值就大于等于3，所以F=A+B+C。",
            "final_answer": "F=A+B+C",
            "steps": [
                {
                    "step_id": "truth-condition",
                    "sequence": 1,
                    "content": "把001和010也误判为大于等于3。",
                    "expression": "F=A+B+C",
                    "claimed_result": "F=A+B+C",
                }
            ],
        },
        "error_step": "truth-condition",
    },
    "KB-DE-3-3-13": {
        "solution": answer(
            "在频率和等效电容不变、以动态功耗为主时，功耗约下降56.44%。",
            "CMOS动态功耗 P∝CV²f。",
            "功耗比 P2/P1=(3.3/5)²=0.4356。",
            "下降比例为1-0.4356=56.44%。",
        ),
        "error_type": "numeric_error",
        "attempt": {
            "raw_text": "功耗与电压成正比，所以下降(5-3.3)/5=34%。",
            "final_answer": "下降34%",
            "steps": [
                {
                    "step_id": "power-law",
                    "sequence": 1,
                    "content": "把CMOS动态功耗错误地按电压一次方缩放。",
                    "expression": "P2/P1=3.3/5",
                    "claimed_result": "下降34%",
                }
            ],
        },
        "error_step": "power-law",
    },
    "KB-SS-12-12": {
        "solution": answer(
            "输出平均值 E[Y]=45 V。",
            "Y=5V²，所以E[Y]=5E[V²]。",
            "E[V²]=Var(V)+E[V]²=9+0=9。",
            "故E[Y]=5×9=45 V。",
        ),
        "error_type": "formula_mismatch",
        "attempt": {
            "raw_text": "输入均值为0，所以输出均值E[Y]=5(E[V])²=0。",
            "final_answer": "0 V",
            "steps": [
                {
                    "step_id": "expectation-square",
                    "sequence": 1,
                    "content": "错误地把E[V²]替换成(E[V])²。",
                    "expression": "E[Y]=5(E[V])²",
                    "claimed_result": "0 V",
                    "unit": "V",
                }
            ],
        },
        "error_step": "expectation-square",
    },
    "KB-SS-10-19": {
        "solution": answer(
            "抽样频率和离散频谱周期均为125 Hz；为避免混叠，"
            "连续信号最高频率必须小于62.5 Hz。",
            "抽样间隔 Ts=2.048/256=0.008 s。",
            "抽样频率 fs=1/Ts=125 Hz，离散频谱以fs为周期。",
            "奈奎斯特条件要求信号带宽小于fs/2=62.5 Hz。",
        ),
        "error_type": "numeric_error",
        "attempt": {
            "raw_text": "fs=125 Hz，因此只要信号最高频率不超过125 Hz就不会混叠。",
            "final_answer": "频谱周期125 Hz，最高频率≤125 Hz",
            "steps": [
                {
                    "step_id": "nyquist-limit",
                    "sequence": 1,
                    "content": "把奈奎斯特频率误写成抽样频率本身。",
                    "expression": "fmax≤fs",
                    "claimed_result": "fmax≤125 Hz",
                    "unit": "Hz",
                }
            ],
        },
        "error_step": "nyquist-limit",
    },
    "KB-DSP-2-25": {
        "solution": answer(
            "一般不能。z* 依赖z的共轭，在任何二维开环域内都不是解析函数，"
            "而序列的双边z变换在其收敛环域内必须解析。",
            "z变换 X(z)=Σx(n)z^-n 在收敛环域内是z的解析函数。",
            "z* 不满足复解析条件，不能在一个环形开域内作为序列的z变换。",
            "只在实轴上令z*=z不能替代复平面上的z变换定义。",
        ),
        "error_type": "formula_mismatch",
        "attempt": {
            "raw_text": "因为z取实数时z*=z，而z是δ(n+1)的z变换，"
            "所以X(z)=z*也代表δ(n+1)。",
            "final_answer": "可以，对应δ(n+1)",
            "steps": [
                {
                    "step_id": "real-axis-only",
                    "sequence": 1,
                    "content": "只在实轴比较，忽略z变换必须在复平面收敛域内解析。",
                    "expression": "z*=z",
                    "claimed_result": "x(n)=δ(n+1)",
                }
            ],
        },
        "error_step": "real-axis-only",
    },
    "KB-DSP-5-6": {
        "solution": answer(
            "在教材通常采用的定义下，遍历过程以平稳性为前提；"
            "但平稳过程不一定遍历。",
            "遍历性要求时间平均能代表相应的集合平均。",
            "平稳只保证统计量不随时间平移改变，并不保证单条样本函数能遍历集合。",
            "例如X(n)=A且A为非退化随机常量时过程平稳，"
            "但单条样本的时间均值为A，不等于固定的集合均值，故不遍历。",
        ),
        "error_type": "condition_missing",
        "attempt": {
            "raw_text": "平稳就表示时间统计特性不变，所以任何平稳过程都一定遍历。",
            "final_answer": "两个论断都正确",
            "steps": [
                {
                    "step_id": "stationary-implies-ergodic",
                    "sequence": 1,
                    "content": "把平稳性直接等同于遍历性，遗漏样本时间平均条件。",
                    "claimed_result": "平稳过程一定遍历",
                }
            ],
        },
        "error_step": "stationary-implies-ergodic",
    },
    "KB-COMM-4-1": {
        "solution": answer(
            "最远视距通信距离约45.2 km。",
            "不计大气折射时，单端地平线距离近似3.57√h km，h以m计。",
            "两端高度均为40 m，总距离为3.57(√40+√40)≈45.16 km。",
        ),
        "error_type": "unit_incompatible",
        "attempt": {
            "raw_text": "d=3.57(√40+√40)=45.16，因此最远距离为45.16 m。",
            "final_answer": "45.16 m",
            "steps": [
                {
                    "step_id": "distance-unit",
                    "sequence": 1,
                    "content": "数值计算正确，但把公式输出单位km写成m。",
                    "claimed_result": "45.16 m",
                    "unit": "m",
                }
            ],
        },
        "error_step": "distance-unit",
    },
    "KB-COMM-12-4": {
        "solution": answer(
            "一个周期内：长度1至7的游程数依次为128、64、32、16、8、4、2；"
            "另有1个长度8的全0游程和1个长度9的全1游程。",
            "9级m序列周期为2^9-1=511，总游程数为2^8=256。",
            "长度r=1…7的游程数为2^(9-r-1)。",
            "最长还包含一个8连0游程和一个9连1游程。",
        ),
        "error_type": "numeric_error",
        "attempt": {
            "raw_text": "可能的游程长度是1到9，所以每种长度各有1个，共9个游程。",
            "final_answer": "各长度1个，共9个",
            "steps": [
                {
                    "step_id": "run-count",
                    "sequence": 1,
                    "content": "把游程长度的种类数误当成每种长度的实际游程个数。",
                    "claimed_result": "9个游程",
                }
            ],
        },
        "error_step": "run-count",
    },
}


BOUNDARY_CASES = [
    {
        "case_id": "CUR-BND-CT-001",
        "course": "CT",
        "title": "电路图缺失时不得编造参数",
        "message": "题8-14所示电路在开关闭合前处于稳态，求t>0时的iL。"
        "当前输入没有提供题8-14电路图，也没有R、L、电源和开关连接信息。",
        "category": "missing_figure",
        "expected": "应指出缺少电路图和参数，不能给出唯一的iL(t)，并请求补充题图。",
        "required_keywords": ["缺少", "电路图"],
        "forbidden_claims": ["iL(t)=0", "时间常数为"],
    },
    {
        "case_id": "CUR-BND-CT-002",
        "course": "CT",
        "title": "互相矛盾的功率结论",
        "message": "电压10 V、电流2 A，电流流入元件电压正端。"
        "请证明该元件在同一参考方向下既吸收20 W又发出20 W。",
        "category": "contradictory_request",
        "expected": (
            "应指出同一参考方向下两种结论互相矛盾；"
            "按关联参考方向只能判为吸收20 W。"
        ),
        "required_keywords": ["矛盾", "参考方向"],
        "forbidden_claims": ["既吸收20 W又发出20 W"],
    },
    {
        "case_id": "CUR-BND-AE-001",
        "course": "AE",
        "title": "引用上一题参数但上下文缺失",
        "message": "在题4.3.1所给电路参数条件下，求最大不失真输出电压幅值。"
        "本输入没有题4.3.1的电路和参数。",
        "category": "missing_prior_context",
        "expected": "应说明依赖的题4.3.1未提供，不能计算唯一数值。",
        "required_keywords": ["题4.3.1", "无法"],
        "forbidden_claims": ["最大幅值为10 V"],
    },
    {
        "case_id": "CUR-BND-AE-002",
        "course": "AE",
        "title": "理想运放条件不足",
        "message": "一个运放电路没有说明反馈极性、供电电压和输出是否饱和。"
        "仅凭“理想运放”四个字，直接令v+=v-并计算闭环增益。",
        "category": "condition_missing",
        "expected": "应指出虚短需要负反馈且运放在线性区，条件不足时不能直接使用。",
        "required_keywords": ["负反馈", "线性区"],
        "forbidden_claims": ["任何理想运放都有v+=v-"],
    },
    {
        "case_id": "CUR-BND-DE-001",
        "course": "DE",
        "title": "四值逻辑不得强行二值化",
        "message": "Verilog输入A=x、B=z。要求不说明门类型和驱动强度，"
        "直接给出唯一的二值输出0或1。",
        "category": "unknown_logic_state",
        "expected": "应指出x、z不能在缺少门类型和驱动条件时强制化成唯一0或1。",
        "required_keywords": ["x", "z", "无法"],
        "forbidden_claims": ["输出必为0", "输出必为1"],
    },
    {
        "case_id": "CUR-BND-DE-002",
        "course": "DE",
        "title": "时序电路缺少初态和触发沿",
        "message": "给出一个未附电路图的三位计数器，未说明初始状态和时钟触发沿，"
        "要求写出前8个输出状态。",
        "category": "missing_initial_condition",
        "expected": "应请求计数器结构、初态及触发沿，不能编造状态序列。",
        "required_keywords": ["初始状态", "触发沿"],
        "forbidden_claims": ["000,001,010,011,100,101,110,111"],
    },
    {
        "case_id": "CUR-BND-SS-001",
        "course": "SS",
        "title": "终值定理收敛条件边界",
        "message": "对f(k)=b[1-exp(-akT)]u(k)，未给a和T的符号，"
        "要求无条件断言终值一定为b。",
        "category": "theorem_precondition",
        "expected": "应区分aT>0、aT=0和aT<0，并说明终值定理的极点条件。",
        "required_keywords": ["aT", "条件"],
        "forbidden_claims": ["无论a和T为何终值都是b"],
    },
    {
        "case_id": "CUR-BND-SS-002",
        "course": "SS",
        "title": "引用缺失系统不得反推",
        "message": "“用z变换求7.16所示系统的零输入响应。”"
        "当前输入没有习题7.16、系统方程、初始条件或系统函数。",
        "category": "missing_prior_context",
        "expected": "应指出系统和初始条件缺失，不能反推出唯一零输入响应。",
        "required_keywords": ["系统", "初始条件", "缺失"],
        "forbidden_claims": ["零输入响应为0"],
    },
    {
        "case_id": "CUR-BND-DSP-001",
        "course": "DSP",
        "title": "只引用公式编号不能完成证明",
        "message": "请证明式(7.42)，但当前输入未给出式(7.42)的内容、"
        "变量定义和成立条件。",
        "category": "missing_equation",
        "expected": "应请求公式正文、变量和假设，而不是编造一个7.42公式。",
        "required_keywords": ["式(7.42)", "补充"],
        "forbidden_claims": ["由维纳-辛钦定理立即得证"],
    },
    {
        "case_id": "CUR-BND-DSP-002",
        "course": "DSP",
        "title": "缺少ROC时因果稳定性不唯一",
        "message": "只给H(z)=1/[(1-0.5z^-1)(1-2z^-1)]，"
        "没有给收敛域，要求唯一判断系统是否因果且稳定。",
        "category": "missing_roc",
        "expected": "应列出不同ROC对应的因果性和稳定性，指出缺少ROC不能唯一判断。",
        "required_keywords": ["收敛域", "不能唯一"],
        "forbidden_claims": ["该系统必然因果且稳定"],
    },
    {
        "case_id": "CUR-BND-COMM-001",
        "course": "COMM",
        "title": "非法概率分布不得计算熵",
        "message": "三个符号的概率分别为0.6、0.5和0.2。"
        "请把它们直接代入熵公式并给出合法信源熵。",
        "category": "invalid_probability",
        "expected": "应先指出概率和为1.3，不是合法概率分布，不能作为信源熵直接计算。",
        "required_keywords": ["1.3", "概率"],
        "forbidden_claims": ["这是合法信源"],
    },
    {
        "case_id": "CUR-BND-COMM-002",
        "course": "COMM",
        "title": "上题条件缺失时拒绝猜测",
        "message": "“在上题条件下，分别求假同步概率。”"
        "当前输入没有同步码长度、判决门限、误码率或所谓上题。",
        "category": "missing_prior_context",
        "expected": "应列出缺失的同步码和概率参数并请求补充，不能猜测数值。",
        "required_keywords": ["上题", "缺少"],
        "forbidden_claims": ["假同步概率为0"],
    },
]


def load_supplemental(output: Path) -> dict[str, dict[str, Any]]:
    path = output / "supplemental" / "all_questions.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    cases = payload.get("cases") if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError(f"{path} 顶层必须为 {{\"cases\": [...]}}")
    return {str(case["case_id"]): case for case in cases}


def reference_answer(solution: dict[str, Any]) -> str:
    lines = [
        *[
            f"{index}. {step}"
            for index, step in enumerate(solution["steps"], start=1)
        ],
        f"结论：{solution['final_answer']}",
    ]
    return "\n".join(lines)


def reference_solution(solution: dict[str, Any]) -> dict[str, Any]:
    return {
        "steps": [
            {
                "step_id": f"reference-{index}",
                "sequence": index,
                "content": step,
            }
            for index, step in enumerate(solution["steps"], start=1)
        ],
        "final_answer": solution["final_answer"],
        "answer_kind": "curated_reference",
        "official": False,
    }


def derived_case(
    base: dict[str, Any],
    *,
    case_id: str,
    solution: dict[str, Any],
    part: str,
) -> dict[str, Any]:
    case = copy.deepcopy(base)
    source_case_id = str(base["case_id"])
    case["case_id"] = case_id
    case["title"] = f"{base['title']}（{part}）"
    case["reference_answer"] = reference_answer(solution)
    case["reference_solution"] = reference_solution(solution)
    case["judge_type"] = "hybrid"
    case["requires_manual_review"] = False
    case["tags"] = [
        "curated_answer_set",
        part,
        str(base["course"]).casefold(),
    ]
    case["structured_input"] = {
        **copy.deepcopy(base.get("structured_input") or {}),
        "source_case_id": source_case_id,
        "answer_provenance": {
            "kind": "derived_and_curated",
            "official": False,
            "verification": "formula_and_numeric_cross_check",
        },
    }
    case["notes"] = (
        "参考答案由题面推导并按统一步骤结构整理，不代表教材官方答案。"
    )
    return case


def build_standard_cases(
    supplemental: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    counters: Counter[str] = Counter()
    cases: list[dict[str, Any]] = []
    for source_id, solution in STANDARD_ANSWERS.items():
        base = supplemental[source_id]
        course = str(base["course"])
        counters[course] += 1
        case = derived_case(
            base,
            case_id=f"CUR-STD-{course}-{counters[course]:03d}",
            solution=solution,
            part="part1_standard_answer",
        )
        case["task_options"] = {
            **copy.deepcopy(base.get("task_options") or {}),
            "teaching_mode": "direct_answer",
        }
        case["expected_teaching_execution_path"] = "direct"
        case["expected_disclosure_mode"] = "full"
        case["full_solution_disclosed"] = True
        cases.append(case)
    return cases


def build_error_cases(
    supplemental: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    counters: Counter[str] = Counter()
    cases: list[dict[str, Any]] = []
    for source_id, config in ERROR_CASES.items():
        base = supplemental[source_id]
        course = str(base["course"])
        counters[course] += 1
        case = derived_case(
            base,
            case_id=f"CUR-ERR-{course}-{counters[course]:03d}",
            solution=config["solution"],
            part="part2_error_detection",
        )
        case["task_options"] = {
            **copy.deepcopy(base.get("task_options") or {}),
            "teaching_mode": "check_my_work",
            "student_attempt": copy.deepcopy(config["attempt"]),
        }
        case["expected_teaching_execution_path"] = "check"
        case["verification_report_valid"] = True
        case["expected_verification_status"] = "verified_incorrect"
        case["expected_error_type"] = config["error_type"]
        case["expected_hint_level"] = "H1"
        case["expected_disclosure_mode"] = "withhold_final"
        case["first_confirmed_error_found"] = True
        case["full_solution_disclosed"] = False
        case["evidence_requirements"] = {
            "expected_first_error_step": config["error_step"],
            "student_attempt_is_synthetic": True,
            "standard_answer_available": True,
        }
        cases.append(case)
    return cases


def build_boundary_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for config in BOUNDARY_CASES:
        course = str(config["course"])
        cases.append(
            {
                "case_id": config["case_id"],
                "title": config["title"],
                "course": course,
                "task_family": "ACADEMIC_SOLVING",
                "intent": "solve_problem",
                "problem_type": None,
                "difficulty": "boundary",
                "input_type": "text",
                "message": config["message"],
                "file_refs": [],
                "structured_input": {
                    "boundary_category": config["category"],
                    "can_continue": False,
                    "expected_behavior": config["expected"],
                },
                "task_options": {
                    "prefer_internal_agents": True,
                    "use_local_rag": True,
                    "response_depth": "full",
                    "teaching_mode": "direct_answer",
                },
                "expected_agent": "ACADEMIC_PROBLEM_SOLVER",
                "expected_course_pack": course,
                "expected_execution_paths": ["CONDITIONAL"],
                "expected_statuses": ["partial", "failed"],
                "reference_answer": config["expected"],
                "required_keywords": config["required_keywords"],
                "forbidden_claims": config["forbidden_claims"],
                "tags": [
                    "curated_answer_set",
                    "part3_boundary",
                    config["category"],
                    course.casefold(),
                ],
                "source": None,
                "notes": "合成边界输入；目标是验证安全降级、澄清和不编造能力。",
                "input_source": "synthetic",
                "judge_type": "hybrid",
                "provenance": {
                    "source_type": "synthetic",
                    "source_name": "六课程真实题库边界能力扩展",
                    "license_or_authorization": "",
                    "publishable": False,
                },
                "official_scoring": False,
                "requires_manual_review": False,
            }
        )
    return cases


def build(output: Path) -> dict[str, Any]:
    supplemental = load_supplemental(output)
    parts = {
        "part1_standard_answers": build_standard_cases(supplemental),
        "part2_error_detection": build_error_cases(supplemental),
        "part3_boundary": build_boundary_cases(),
    }
    curated_root = output / CURATED_ROOT_NAME
    for name, cases in parts.items():
        write_json(curated_root / f"{name}.json", {"cases": cases})
        write_jsonl(curated_root / f"{name}.jsonl", cases)

    all_cases = [
        case
        for name in (
            "part1_standard_answers",
            "part2_error_detection",
            "part3_boundary",
        )
        for case in parts[name]
    ]
    write_json(curated_root / "all_selected_cases.json", {"cases": all_cases})
    write_jsonl(curated_root / "all_selected_cases.jsonl", all_cases)

    by_part_course = {
        name: dict(
            sorted(Counter(str(case["course"]) for case in cases).items())
        )
        for name, cases in parts.items()
    }
    source_ids = sorted(
        {
            str(
                (case.get("structured_input") or {}).get("source_case_id")
                or ""
            )
            for case in [
                *parts["part1_standard_answers"],
                *parts["part2_error_detection"],
            ]
        }
        - {""},
        key=natural_key,
    )
    manifest = {
        "schema_version": "1.0",
        "selection_policy": {
            "selected_total": len(all_cases),
            "reason": "控制答案生成和API批测耗时，同时均衡覆盖六门课程",
            "course_quota": 8,
            "part_ratios": {
                "part1_standard_answers": 0.50,
                "part2_error_detection": 0.25,
                "part3_boundary": 0.25,
            },
        },
        "part_counts": {name: len(cases) for name, cases in parts.items()},
        "part_course_counts": by_part_course,
        "course_counts": dict(
            sorted(Counter(str(case["course"]) for case in all_cases).items())
        ),
        "source_question_count": len(source_ids),
        "source_case_ids": source_ids,
        "reference_answer_count": sum(
            bool(str(case.get("reference_answer") or "").strip())
            for case in all_cases
        ),
        "synthetic_student_attempt_count": len(parts["part2_error_detection"]),
        "boundary_category_counts": dict(
            sorted(
                Counter(
                    str(
                        (case.get("structured_input") or {}).get(
                            "boundary_category"
                        )
                    )
                    for case in parts["part3_boundary"]
                ).items()
            )
        ),
        "official_scoring": False,
    }
    write_json(curated_root / "manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从无答案补充题中精选并生成标准答案、错误步骤和边界测试集"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="统一格式目录，默认：真实测试题/统一格式",
    )
    args = parser.parse_args()
    manifest = build(args.output.resolve())
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
