# 架构融合审计

## 审计范围与结论

本次检查了 `apps/api/app` 的 API、contracts、orchestrator、agents、providers、services、RAG、multimodal、tools 与配置/测试引用。合并采用增量方式，没有删除旧 API、Provider、RAG 入口或用户未提交代码。

| 类别 | 审计发现 | 处理 |
|---|---|---|
| 主状态 | Pydantic WorkflowState 与 CT 专用执行状态并存 | 主状态收敛为 `orchestrator/state.py::XZDGraphState`；API 仍用 Pydantic |
| Agent/Model Registry | 各只有一套 | 原位扩展 Agent task family、graph、required capabilities 字段；不新增 Model Registry |
| Router | 一套 TaskRouter，曾将 solve_problem 固定到 CT | 原位改为 ACADEMIC_PROBLEM_SOLVER，课程与任务族分离 |
| Provider/RAG | 已有共享 Provider；TaskRunner 统一检索 | 全部复用，CoursePack 不调用 Provider，求解器不二次检索 |
| 文件解析 | file parser 与 material extraction 职责不同 | 均保留：模态识别与业务字段提取 |
| Trace | TraceStore 与 ModelTracer 职责不同 | 均保留：流程摘要与模型调用摘要 |
| CT 专用实现 | local_graph 曾包含专用求解核心 | 改为 deprecated 兼容适配器，内部调用通用图 |

## 保留的适配器与 deprecated 模块

- `SOLVER_CT_V1`：CT CoursePack 的已发布云端基线、回退目标和旧效果对照。
- `LocalCircuitSolverGraph`、`CircuitProblem`、`SolverExecution`：保留旧调用签名，字段映射到 AcademicProblem 后进入通用图。
- `POST /api/v1/tasks`、`POST /api/v1/chat` 与旧前端：保持现有非阻塞任务创建链。
- `services/course_pack.py` 与旧 CT YAML：暂保留旧加载兼容；新运行时唯一 Course Registry 位于 `app/courses/registry.py`。

## 删除评估

本轮没有安全删除业务文件。旧模块仍有测试、API、配置或前端引用，直接删除会破坏兼容。待旧接口有明确下线版本、所有调用迁移且完成引用扫描后，才能删除旧 CoursePack Pydantic 模型与旧 YAML loader。

## 合并后的唯一职责边界

- XZDGraphState：唯一图状态，仅保存引用、摘要、结构化结果与轨迹。
- API Pydantic contracts：外部输入输出校验。
- AgentRegistry：任务执行单元和兼容工作流注册。
- CourseRegistry：课程规则、题型、模板、能力声明和回退配置。
- CapabilityRegistry：跨课程能力到工具的声明映射。
- ToolRegistry：确定性工具元数据、启用策略和 handler。
- GraphFactory：从共享依赖创建任务图。
- AcademicProblemSolverGraph：通用、有限、可追踪的求解编排。
- TaskRunner：异步生命周期、单次 RAG、事件、Provider 与结果治理。

## 暂不能删除

- SOLVER_CT_V1 及星辰环境变量：CT 云端基线与回退仍依赖。
- AgentRequest/AgentResult：`POST /api/v1/tasks` 和 TaskRunner 稳定协议。
- AgentRequestV2/AgentResponse：对话 API 边界，不是图状态。
- WorkflowContextBundle：真实执行链的 RAG 证据复用协议。
