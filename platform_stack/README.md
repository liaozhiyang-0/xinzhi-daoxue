# 平台工作栈说明

本文档描述“芯智导学：电子信息课程群垂类大模型系统”的新阶段平台工作栈。当前定位从“独立错题诊断 Agent”调整为以“识图解题 Agent”为核心能力，配合课程知识问答、学习规划和教师分析展示。

## 1. 新定位

```text
以“识图解题 Agent”为核心能力；
课程问答 Agent 保留，并整合简单纠错/错因提示；
学习规划 Agent 和教师分析 Agent 作为辅助展示功能；
错题诊断不再作为独立核心 Agent。
```

## 2. 工作栈架构

```text
┌──────────────────────────────────────────────┐
│              讯飞星辰 Agent 层                │
│                                              │
│  识图解题 Agent  ← 核心                       │
│  课程问答 Agent  ← 含简单纠错/错因提示         │
│  学习规划 Agent                              │
│  教师分析 Agent                              │
│                                              │
│  工作流编排 │ 知识库检索 │ 图片解析 │ API/H5 发布 │
└──────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────┐
│              讯飞星火 MaaS 层                 │
│                                              │
│  图文问答样例构造 │ 解题 Prompt 工程           │
│  批量推理 │ 模型评估 │ 数据增强 │ 服务发布       │
│  后续可选：多模态微调 / 文本解题微调           │
└──────────────────────────────────────────────┘
```

## 3. 当前阶段重点

1. 跑通识图解题 Agent。
2. 跑通课程知识库检索问答。
3. 支持学生对解题过程追问。
4. 简化错题诊断，只保留错因提示和学习建议。
5. 使用 MaaS 层做图文解题样例、批量推理和模型评估。
6. 微调放在后续阶段。

## 4. 目录说明

```text
platform_stack/
├── README.md
├── agent_layer/
│   ├── vision_solver_agent.md
│   ├── course_qa_agent.md
│   ├── learning_plan_agent.md
│   ├── teacher_analysis_agent.md
│   └── workflow_design.md
├── maas_layer/
│   ├── multimodal_evaluation_plan.md
│   ├── prompt_engineering.md
│   ├── batch_inference_plan.md
│   └── finetuning_later_plan.md
└── demo_cases/
    ├── vision_solver_cases.md
    ├── course_qa_cases.md
    └── teacher_analysis_mock_data.md
```

## 5. 与已有知识库的关系

已有课程知识库、章节 Markdown、题型索引、错因标签、诊断规则和错题样例继续保留。它们不再只服务独立错题诊断，而是同时用于：

- 识图解题后的章节定位和方法选择；
- 课程问答中的公式条件解释；
- 简单纠错和易错提醒；
- MaaS 图文解题评估样例构造；
- 教师端薄弱点统计和展示。

