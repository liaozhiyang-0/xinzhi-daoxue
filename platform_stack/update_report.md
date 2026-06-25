# 平台工作栈调整报告

## 1. 本次新增文件

- `platform_stack/README.md`
- `platform_stack/agent_layer/vision_solver_agent.md`
- `platform_stack/agent_layer/course_qa_agent.md`
- `platform_stack/agent_layer/learning_plan_agent.md`
- `platform_stack/agent_layer/teacher_analysis_agent.md`
- `platform_stack/agent_layer/workflow_design.md`
- `platform_stack/maas_layer/multimodal_evaluation_plan.md`
- `platform_stack/maas_layer/prompt_engineering.md`
- `platform_stack/maas_layer/batch_inference_plan.md`
- `platform_stack/maas_layer/finetuning_later_plan.md`
- `platform_stack/demo_cases/vision_solver_cases.md`
- `platform_stack/demo_cases/course_qa_cases.md`
- `platform_stack/demo_cases/teacher_analysis_mock_data.md`
- `platform_stack/update_report.md`

## 2. 本次修改文件

- `README.md`
- `course_materials/01_circuit_theory/README.md`
- `docs/01_project_positioning.md`
- `docs/02_first_version_scope.md`
- `docs/03_system_architecture.md`
- `docs/04_technical_route.md`
- `docs/05_demo_plan.md`
- `docs/06_team_task_plan.md`
- `backend/api_design.md`
- `backend/agent_api_client_design.md`
- `frontend/README.md`
- `frontend/prototype/student_page.md`

## 3. 本次删除文件

以下旧架构文件已被 `platform_stack/` 中的新工作栈文档替代：

- `agent_design/01_course_qa_agent.md`
- `agent_design/02_error_diagnosis_agent.md`
- `agent_design/03_study_planner_agent.md`
- `agent_design/04_teacher_analysis_agent.md`
- `maas_training/evaluation_plan.md`
- `maas_training/finetune_data_format.md`
- `maas_training/sample_qa_data.jsonl`

## 4. 项目定位变化

原定位为：

```text
课程问答 Agent + 错题诊断 Agent + 学习规划 Agent + 教师分析 Agent
```

新定位为：

```text
识图解题 Agent 为核心；
课程问答 Agent 保留，并整合简单纠错和错因提示；
学习规划 Agent 和教师分析 Agent 作为辅助展示功能；
错题诊断不再作为独立核心 Agent。
```

## 5. Agent 层变化

- 新增识图解题 Agent，负责题图识别、电路结构标准化、分步解题和教学解释。
- 课程问答 Agent 聚焦概念、公式条件、章节检索、简单纠错和复习建议。
- 学习规划 Agent 使用问答、识图解题和错因提示作为薄弱点信号。
- 教师分析 Agent 使用班级统计、知识点分布和错因标签做辅助展示。
- 新增工作流分流规则，优先将图片和电路图输入路由到识图解题 Agent。

## 6. MaaS 层变化

- MaaS 第一阶段重点调整为图文解题样例、批量推理和模型评估。
- 多模态评估重点包括 OCR、元件识别、节点/支路还原、参考方向、方程、计算结果和幻觉检测。
- 微调被放到后续阶段，前置条件是已有高质量样例和稳定评估集。

## 7. 错题诊断功能如何被简化整合

已有 `wrong_reason_tags.md`、`diagnosis_rules.md`、错题样例和题库草稿继续保留，不删除、不重写。它们的新用途是：

- 为课程问答 Agent 提供简单错因提示；
- 为识图解题 Agent 的易错提醒提供标签依据；
- 为教师分析 Agent 提供薄弱点统计维度；
- 为 MaaS 图文解题评估构造错误样例。

错题诊断不再作为独立核心 Agent 展示，不再要求每次输出完整诊断报告。

## 8. 后续建议

1. 优先准备 10 道电路理论题图，跑通识图解题 Agent 演示链路。
2. 将 v0.2 结构化题库样例转为图文解题评估样例。
3. 在课程问答 Agent 中接入错因标签做轻量纠错提示。
4. 教师端先使用 mock 数据展示高频章节和错因标签分布。
5. 暂缓微调，先用 Prompt 工程和批量评估验证效果。
