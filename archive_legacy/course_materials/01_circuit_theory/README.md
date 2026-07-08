# 电路理论

## 课程知识库概述

本目录是《电路理论》课程的子知识库，用于支撑“芯智导学”电子信息课程群垂类大模型系统中的识图解题、课程问答、简单纠错、学习路径推荐和教师端薄弱知识点分析。

主要用途包括：

- 题图识别后的章节定位、方法选择和易错提醒；
- 学生智能答疑；
- 简单纠错和错因提示；
- 学习路径推荐；
- 教师端薄弱知识点分析；
- 题库建设；
- 后续 MaaS 微调数据沉淀。

## 当前整理进度

当前已完成 13 个章节 Markdown 文件的结构化整理：

```text
chapters/
├── 01_circuit_models_and_laws.md
├── 02_equivalent_transform.md
├── 03_general_analysis_methods.md
├── 04_circuit_theorems.md
├── 05_operational_amplifier_circuits.md
├── 06_nonlinear_resistive_circuits.md
├── 07_capacitors_inductors_dynamic_circuits.md
├── 08_first_order_transient_analysis.md
├── 09_second_order_transient_analysis.md
├── 10_sinusoidal_steady_state_analysis.md
├── 11_sinusoidal_steady_state_power.md
├── 12_three_phase_sinusoidal_circuits.md
└── 13_magnetically_coupled_circuits.md
```

已覆盖的主要知识范围：

- 基础电路模型；
- 电阻电路分析；
- 电路定理；
- 运算放大器电路；
- 非线性电阻电路；
- 动态电路；
- 一阶、二阶暂态分析；
- 正弦稳态分析；
- 正弦稳态功率；
- 三相电路；
- 磁耦合与变压器。

配套索引与诊断文件：

- `questions/question_type_index.md`：题型索引；
- `wrong_cases/wrong_reason_tags.md`：全局错因标签字典；
- `wrong_cases/diagnosis_rules.md`：课程 Agent 错题诊断规则。

## 内容质量评估

1. **体系完整性较强**  
   本知识库从电路模型、基本定律、电阻电路、动态电路、正弦稳态、三相电路到磁耦合电路逐步展开，适合作为本科电子信息类《电路理论》课程的主干知识库。

2. **知识结构适合 Agent 检索**  
   章节内容已转化为定位、知识结构、核心概念、公式适用条件、典型题型、错因标签和 Agent 问答样例，适合识图解题后的知识检索、智能答疑和简单纠错，不是教材原文复制。

3. **工程应用覆盖较好**  
   内容包含运放电路、非线性电阻、功率因数校正、三相配电、变压器等应用主题，有助于衔接模拟电子技术、电力电子、信号与系统和通信相关课程。

4. **不足与风险**  
   原始材料可能来自扫描版资料，公式和图示经过人工或模型识别后仍可能存在符号、上下标、相位角、正负号和图中参考方向误差。因此关键公式、特殊电路图关系和题型结论仍需后续人工校验。

5. **版权与原创化说明**  
   当前 Markdown 文件是基于章节内容生成的原创化、结构化知识摘要，不应上传或公开传播原始扫描 PDF，也不应搬运教材例题全文和完整解析。

## 后续使用方式

1. **用于学生智能答疑**  
   Agent 可按章节检索核心概念、公式适用条件和问答样例，回答“为什么这样列方程”“公式什么时候能用”等问题。

2. **用于识图解题与简单纠错**  
   `question_type_index.md` 可辅助判断题图所属题型，`wrong_reason_tags.md` 和 `diagnosis_rules.md` 可用于生成易错提醒、简单错因提示和学习建议。

3. **用于题库建设**  
   `question_type_index.md` 可作为题型索引，后续可为每个题型补充原创练习题、标准答案、分步提示和错因映射。

4. **用于教师端分析**  
   学生错题可映射到错因标签，统计高频错因，形成班级薄弱知识点报告。

5. **用于后续图文解题评估和微调数据沉淀**  
   Agent 问答样例、错因提示、结构化题库样例和题型模板可进一步转化为图文解题评估样例、监督微调样本或 RAG 检索增强数据。

6. **后续扩展方向**  
   可继续补充原创题库、章节知识图谱、公式卡片、错题样例库，以及与模拟电子技术、信号与系统、通信原理等课程的跨课程关联。

## 推荐目录结构

```text
course_materials/01_circuit_theory/
├── README.md
├── 00_course_overview.md
├── chapters/
│   ├── README.md
│   ├── 01_circuit_models_and_laws.md
│   ├── 02_equivalent_transform.md
│   ├── 03_general_analysis_methods.md
│   ├── 04_circuit_theorems.md
│   ├── 05_operational_amplifier_circuits.md
│   ├── 06_nonlinear_resistive_circuits.md
│   ├── 07_capacitors_inductors_dynamic_circuits.md
│   ├── 08_first_order_transient_analysis.md
│   ├── 09_second_order_transient_analysis.md
│   ├── 10_sinusoidal_steady_state_analysis.md
│   ├── 11_sinusoidal_steady_state_power.md
│   ├── 12_three_phase_sinusoidal_circuits.md
│   └── 13_magnetically_coupled_circuits.md
├── questions/
│   ├── README.md
│   └── question_type_index.md
└── wrong_cases/
    ├── README.md
    ├── wrong_reason_tags.md
    └── diagnosis_rules.md
```

## 人工校验清单

- 公式上下标是否正确；
- 相量角度和正负号是否正确；
- KCL/KVL 参考方向是否一致；
- 受控源控制变量是否保留；
- 三相电路线电压/相电压关系是否准确；
- 磁耦合同名端和互感电压符号是否准确；
- 功率单位 W/var/V·A 是否区分；
- 章节题型编号是否与索引一致；
- 错因标签是否重复或过度细分；
- 诊断规则是否能真实触发 Agent 反馈；
- 是否避免引入扫描 PDF 页码、教材原题全文和完整例题解析。

## 当前建设状态

- [x] 13 个章节知识文件已完成结构化整理；
- [x] 题型索引已覆盖 CT01-CT13；
- [x] 全局错因标签字典已归并并补充第9-13章标签；
- [x] 诊断规则已覆盖第1-13章主要高频错因；
- [x] 已完成错因标签瘦身与诊断规则一致性校验；
- [ ] 关键公式、相量图关系和磁耦合同名端符号仍需人工复核；
- [ ] 原创练习题库、错题样例库和跨课程知识图谱待后续建设。
