# 赛题商业化场景目录与运行契约

## 目标

赛题要求至少落地一个真实教学或科研场景，并提供可追溯、可复现的效果验证。六个场景统一写入 `config/scenarios.yaml`，由 API 在启动时一次加载并校验，避免前端、Demo、评测脚本分别维护一套场景名称。

## 六个首批场景

| 场景 | 目标客户 | 复用能力 | 首要证据 |
| --- | --- | --- | --- |
| 教师智能备课与课程资源生成 | 高校教师与课程团队 | 备课 Agent、课程知识库、引用 | 目标对齐、来源页码、教师复核 |
| 作业批改与首错定位 | 教师、助教、智慧教学平台 | 作业审查、步骤诊断、验证题 | 评分规则、首错定位、抽检 |
| 学情诊断与个性化学习路径 | 学生、教务、在线教育平台 | 学习闭环、错误池、复测 | 作答证据、推荐理由、复测 |
| 科研前沿检索与证据简报 | 科研团队、研究院、企业研发 | 学术检索、引用与时间戳 | 文献标识、结论来源、检索边界 |
| 科研数据分析与可复现解释 | 实验室与产业研发部门 | 数据分析 Agent、代码/公式输出 | 数据质量、可执行产物、局限性 |
| 学院知识库治理与课程资产发布 | 学院、教务处、教育数字化服务商 | 资产审查、版本治理、RAG | 版本、审查、审批、访问控制 |

## API 使用

```text
GET /api/v1/scenarios
GET /api/v1/scenarios/{scenario_id}
POST /api/v1/chat  // 请求体增加 scenario_id
```

当请求带有 `scenario_id` 时，服务会校验课程和输入类型，并把场景版本、目标 Agent、检索画像写入任务选项；若未指定 `intent_hint`，使用场景的第一个意图作为默认值。场景绑定只复用现有 Supervisor、TaskRunner 和 Provider 链路，不绕过任务队列，也不包含密钥或私有知识库内容。

RAG 热路径继续复用现有的查询向量缓存和结果缓存；本阶段只增加索引版本文件的元数据缓存，索引文件的修改时间或大小变化时自动重新读取，避免每次检索都解析同一份状态 JSON。

## 快速验证

```powershell
.venv\Scripts\python.exe scripts\validate_scenarios.py
.venv\Scripts\python.exe -m pytest apps\api\tests\test_scenario_catalog.py apps\api\tests\test_scenarios_api.py -q --no-cov
```

本阶段不宣称真实用户效果或准确率；后续需为至少三个典型问题建立标准答案、权威来源和人工复核记录，再接入自动评测。

首批合成基线位于 `evaluation/cases/contest_scenarios/synthetic_contest.yaml`，覆盖备课、作业诊断和科研数据分析。使用以下命令做低成本结构审查：

```powershell
.venv\Scripts\python.exe scripts\validate_contest_cases.py
```

该审查只验证场景与 Agent 的绑定、证据字段、合成标记和人工复核门槛，不生成真实准确率，也不替代授权用户试用。
