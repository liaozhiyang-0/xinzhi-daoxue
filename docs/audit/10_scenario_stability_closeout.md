# 六业务场景稳定性专项收口

## 回归结果

修复后从当前 /workspace 新建任务 30 次，六场景各 5 次：

数据库只读复核：total=30，completed=22，waiting_review=8，failed=0，missing_agent=0；六个预期 Agent 均各出现 5 次。

| 场景 | 结果 | Agent | 主要 Runtime / Provider |
|---|---:|---|---|
| 教师智能备课 | 5/5 waiting_review | TEACH_01_LESSON_PREP_V1 | lesson.verify；人工审批检查点 |
| 作业批改与首错诊断 | 5/5 completed | TEACH_02_ASSIGNMENT_REVIEW_V1 | assignment.verify；local_agent |
| 学生个性化学习路径 | 5/5 completed | LEARN_01_LOCAL_RETRIEVAL_V1 | knowledge.verify；dashscope；RAG hit=4 |
| 科研前沿检索 | 2/5 completed，3/5 waiting_review | RESEARCH_01_ACADEMIC_SEARCH_V1 | research.verify；外部检索或证据审核 |
| 学院知识库治理 | 5/5 completed | LEARN_01_KNOWLEDGE_QA_V1 | knowledge.verify；dashscope；RAG hit=4 |
| 图像电路解题 | 5/5 completed | ACADEMIC_PROBLEM_SOLVER | solver.verify；local_graph；1 张图片 |

## 稳定性门槛

| 门槛 | 结论 |
|---|---|
| 六个场景均进入预期 Agent | 通过，30/30 |
| Agent not found | 通过，修复后 0 次 |
| 配置导致的任务失败 | 通过，修复后 0 次；Solver 空 scenario_id 是 generic contract 残留 |
| completed 但前端无结果 | 通过，0 次 |
| failed 后无限加载 | 通过，0 次；修复后无 failed 任务 |
| 可自动完成的离线场景 | 通过，作业、学习、治理、图像解题 20/20 completed；备课按契约等待教师审批 |
| 外部检索失败与系统失败区分 | 通过；外部失败只进入 evidence review checkpoint |
| SSE / polling 终态对账 | 通过；每次都有可见工作台状态和持久化事件终态或检查点 |

## 残余风险

1. 备课和部分科研检索的 waiting_review 需要教师或管理员后续审批；本专项验证的是正确进入检查点和前端可见，不代替审批动作。
2. Solver 入口没有场景 catalog id。当前显式 intent=solve_problem、course_id=AE 已足以稳定路由，暂不新增虚构配置。
3. 研究 Provider 仍可能出现 HTTP 500、超时或无结果；这些属于外部证据质量/可用性边界。
4. 本次按要求只执行定向测试和 30 次 E2E，没有执行全量 Pytest、Ruff 或 Docker 重建。

## 结论

六业务场景 E2E 稳定性专项达到本阶段目标：知识治理 Agent handler 缺失和学习路径 Runtime 超时已消除，卡片场景 wiring 已固化，30 次修复后回归没有系统失败、前端空结果或无限加载。后续如继续工作，应优先处理审批闭环和 Solver 场景契约的产品决策，不进行全局架构重构。
