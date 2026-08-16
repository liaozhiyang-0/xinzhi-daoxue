# 学习质量闭环实现说明

## 1. 边界

本实现是现有统一任务链的增量扩展。所有模型、内部 Agent、RAG 和本地 Runtime 只能从 `POST /api/v1/tasks` 进入；学习服务不创建第二个 TaskRunner，也不直接调用 Provider。`SOLVER_CT_V1` 保持冻结。

### 1.1 模块与数据流

新增合同、质量门、学习循环、答案检查、变式生成和 TaskExecutor 服务。主数据流为：题目进入原任务 API → 共享 Solver → HIGH_RISK 校验 → 质量门 → TaskPresentation → Workspace；学习动作的数据流为：Workspace → `/api/v1/learning/actions` → 学习记录/确定性检查 → 必要时返回 follow-up prompt → 原任务 API。

数据库通过 `20260722_0005_learning_reliability.py` 新增学习表和任务可靠性字段。API 新增学习动作与掌握状态查询；页面只在现有结果区增加六个按钮，没有引入新框架。配置新增 `config/learning_mastery.yaml`。

## 2. 求解与质量门

`SolverResult` 保留旧响应字段，并新增：

- `final_answer_detail`：值、单位、结论和置信度；
- `verification`：校验状态、检查项和问题；
- `knowledge_evidence`：引用状态、chunk id 和未获支持结论；
- `quality_gate`：确定性检查、阻断原因和课程规则。

共享 Solver 图在 HIGH_RISK 校验之后执行质量门。HIGH_RISK 没有通过确定性校验时，成功结果会降为 partial；质量门不启动无界反思，也不调用第二模型“自我认可”。CT、AE、DE、SS 的差异只通过 CoursePack 的 `verification_rules` 声明。

## 3. 学习状态与错题

新增四类持久化记录：

- `learner_knowledge_states`：用户、课程、知识点的掌握度、置信度和计数；
- `wrong_answer_records`：来源任务、题目摘要、学生答案、错误类型和掌握度变化；
- `practice_attempts`：变式题、参考答案、学生答案和审查结果；
- `learning_interactions`：六类学习动作及幂等结果。

掌握度参数集中在 `config/learning_mastery.yaml`。配置中的增减幅度是启发式产品状态，不等同于教育测量结论或真实能力分数。

## 4. 答案检查

`StudentAnswerReviewService` 先按公式 token 和参考步骤对齐，再检查数值、单位及参考方向，返回 `first_error`、错误类型和局部反馈。它不会仅比较整段字符串。当前检查器是保守的确定性基线；复杂符号等价和多解题仍需后续接入受控工具或人工 rubric。

## 5. 变式题

`PracticeGenerationService` 只对能够用本地规则生成唯一参考答案的题型返回 ready，并记录条件完整、可解、单位一致和唯一答案检查。无法确定性验证的题型返回 unsupported，由前端把请求交回统一任务链；不会把未校验题目伪装为可用练习。

## 6. Workspace 动作

结果区提供：加入错题本、给我提示、检查我的答案、生成变式题、讲解关联知识、标记已掌握。每次动作携带 `source_task_id` 和幂等键。需要进一步生成时，学习 API 返回 `follow_up_prompt`，前端随即通过原 `/api/v1/tasks` 提交。

## 7. 验证

```powershell
.\.venv\Scripts\python.exe -m pytest apps/api/tests/test_solver_quality_gate.py apps/api/tests/test_learning_loop.py -q
```

测试只证明本地合同、确定性规则、持久化和幂等行为；不证明真实模型回答质量。

## 8. 完成状态

已完成合同、数据库、API、页面最小入口、幂等记录、确定性答案检查和受控变式生成。未完成项包括：复杂符号等价、多解题自动判定、基于真实学习数据校准掌握度、真实模型质量验收和用户可用性测试。真实课程资料仍只能由授权只读数据源提供；仓库中的 synthetic 测试不是真实测评数据。
