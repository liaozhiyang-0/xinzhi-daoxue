# 商业案例打磨包

本目录按场景逐案维护商业计划书、路演和演示材料。每份案例文档只描述一个 `scenario_id`，不复用其他案例的检索结果、记忆或答案。

## 当前盘点

| 场景 | 状态 | 主 Agent | 交付物 |
| --- | --- | --- | --- |
| 教师智能备课与课程资源生成 | 待闭环 → 已完成 | `TEACH_01_LESSON_PREP_V1` | [案例文档](faculty_course_copilot_v1.md) |
| 作业批改与首错定位 | 待闭环 | `TEACH_02_ASSIGNMENT_REVIEW_V1` | [案例文档](assessment_diagnosis_v1.md) |
| 学情诊断与个性化学习路径 | 待闭环 | `LEARN_01_LOCAL_RETRIEVAL_V1` | [案例文档](student_learning_path_v1.md) |
| 科研前沿检索与证据简报 | 已完成基线 | `RESEARCH_01_ACADEMIC_SEARCH_V1` | 运行时接入见 `apps/api/app/services/research_frontier_service.py` |
| 科研数据分析与可复现解释 | 待闭环 | `RESEARCH_03_DATA_ANALYSIS_V1` | [案例文档](research_data_workbench_v1.md) |
| 学院知识库治理与课程资产发布 | 待闭环 | `LEARN_01_KNOWLEDGE_QA_V1`（未配置时安全降级到本地 Agent） | [案例文档](department_knowledge_governance_v1.md) |

## 证据边界

- 已核验的工程事实引用仓库路径；合成评测材料明确标为 synthetic，不能当成真实用户结果。
- 市场规模、采购预算、客户名单、客单价、准确率、节省时长和续费率没有本地证据时统一写为“待补证据”。
- 竞品名称只用于替代方案分类；未做外部核验的品牌、份额和性能不写入案例。
- 真实 Provider、外部检索和用户试点需由负责人另行授权；本目录不写入密钥、Flow ID 或学生隐私。

## 统一验证

```powershell
$env:PYTHONPATH = "apps/api"
.venv\Scripts\python.exe scripts\validate_scenarios.py
.venv\Scripts\python.exe scripts\validate_commercial_scenarios.py
.venv\Scripts\python.exe scripts\run_commercial_scenario_preflight.py
.venv\Scripts\python.exe -m pytest apps\api\tests\test_scenario_catalog.py apps\api\tests\test_scenarios_api.py apps\api\tests\test_scenario_preflight.py -q --no-cov
```

其中 preflight 只验证路由、能力、证据策略和本地演示可用性，不生成真实商业效果指标。
