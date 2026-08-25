# 六业务场景运行矩阵（修复后基线）

## 统一链路

workspace.html / workspace.js 卡片 → data-capability、data-intent、data-course、data-image-src → materialManager → buildStudentTaskPayload → POST /api/v1/tasks → scenario catalog / TaskRouter → AgentRegistry / AgentDefinition → Runtime → ToolRegistry、Skill、本地 RAG 或外部 Research Provider → Result Validator / 场景契约 → TaskCompletion 与 TaskEvent 持久化 → SSE / polling 对账 → workspace.js 结果展示。

修复后，卡片点击会把 data-intent 和 data-course 写入 state.intentOverride、state.activeCourse；提交时显式带入任务 payload。用户修改示例题目后会清除卡片 wiring，避免普通问题继承示例路由。

## 六场景定义

| scenario_id | 标题 / intent | course_id | options / 附件 | 预期 Agent | workflow / Tool / Skill / RAG | 修复后验证 |
|---|---|---|---|---|---|---|
| faculty_course_copilot_v1 | 教师智能备课 / lesson_prep | CT | 文本，无附件 | TEACH_01_LESSON_PREP_V1 | LessonPrepRuntimeService；teach_lesson_prep；课程证据检索；CT.NODAL、CT.KCL | 5/5 路由正确，5/5 waiting_review，审批控件可见 |
| assessment_diagnosis_v1 | 作业批改与首错诊断 / assignment_review | CT | 文本内含作答步骤，无附件 | TEACH_02_ASSIGNMENT_REVIEW_V1 | AssignmentReviewRuntimeService；teach_assignment_review；文本 RAG；首错、错误传播、分层提示、验证题 | 5/5 completed，诊断结果可见 |
| student_learning_path_v1 | 学生个性化学习路径 / learning_advice | CT | use_local_rag=true，无附件 | LEARN_01_LOCAL_RETRIEVAL_V1 | KnowledgeQARuntimeService；local_retrieval；本地 RAG；知识检索和依据约束 | 5/5 completed，RAG hit=4、calls=1 |
| research_frontier_radar_v1 | 科研前沿检索与证据简报 / academic_search | AUTO → backend UNKNOWN | 文本，无附件 | RESEARCH_01_ACADEMIC_SEARCH_V1 | ResearchFrontierService；external_academic_search；OpenAlex、Crossref、arXiv 等；研究查询规划、证据审核、综合 | 5/5 可见终态；外部失败进入证据审核 |
| department_knowledge_governance_v1 | 学院知识库治理 / summarize_knowledge | CT | 资产记录来自 prompt，无附件 | LEARN_01_KNOWLEDGE_QA_V1 | KnowledgeQARuntimeService；governed_knowledge；知识 RAG；版本、来源、审批、权限、回滚审查 | 5/5 completed；RAG hit=4 |
| 无 catalog id：solve_problem | 模电图像解题 / solve_problem | AE | 必须上传示例图；1 张图片 | ACADEMIC_PROBLEM_SOLVER | AcademicSolverRuntimeService；academic_solver_domain_context；method_only_rag；图片/文本边界校验 | 5/5 completed；图片预览和复核边界可见 |

第六个入口仍是通用 Solver 合同，没有虚构的 config/scenarios.yaml 场景 ID；本次修复确保它显式携带 intent=solve_problem、course_id=AE 并按 local_solver_contract 路由。这是非阻塞的静态契约缺口，不是 Agent 未找到。

## 注册与运行时核对

| 层 | 核对结果 |
|---|---|
| Scenario wiring | 前五个 catalog id 继续由后端绑定；卡片 intent/course 已显式传递；Solver 保持 generic contract |
| TaskRouter | 六场景回归均进入预期 Agent，无 ROUTER 失败 |
| AgentRegistry / AgentDefinition | 六个预期 Agent 均存在且启用 |
| Runtime | lesson.verify、assignment.verify、knowledge.verify、research.verify、solver.verify 均有完成或业务检查点 |
| RAG / Tool / Provider | 本地 RAG 命中、外部检索成功和外部证据失败均在事件中区分 |
| Result Validator / TaskCompletion | 无 completed-without-result；全部任务有可见结果或检查点 |

完整修复前逐任务记录见 scenario_e2e_results.md。
