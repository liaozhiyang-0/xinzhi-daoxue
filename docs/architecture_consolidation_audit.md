# 架构融合审计（历史记录）

> 本文记录迁移前的审计结论。星辰工作流及其 Provider 后续已废止并从活动代码移除；当前运行事实以 `docs/repository_architecture_guide.md` 和代码为准。

## 审计范围与结论

本次检查了 `apps/api/app` 的 API、contracts、orchestrator、agents、providers、services、RAG、multimodal、tools 与配置/测试引用。合并采用增量方式，没有删除旧 API、Provider、RAG 入口或用户未提交代码。

| 类别 | 审计发现 | 处理 |
|---|---|---|
| 主状态 | Pydantic WorkflowState 与 CT 专用执行状态并存 | 主状态收敛为 `orchestrator/state.py::XZDGraphState`；API 仍用 Pydantic |
| Agent/Model Registry | 各只有一套 | 原位扩展 Agent task family、graph、required capabilities 字段；不新增 Model Registry |
| Router | 一套 TaskRouter，曾将 solve_problem 固定到 CT | 原位改为 ACADEMIC_PROBLEM_SOLVER，课程与任务族分离 |
| Provider/RAG | 已有共享 Provider；Runtime capability 统一检索 | 全部复用，CoursePack 不调用 Provider，求解器不二次检索 |
| 文件解析 | file parser 与 material extraction 职责不同 | 均保留：模态识别与业务字段提取 |
| Trace | TraceStore 与 ModelTracer 职责不同 | 均保留：流程摘要与模型调用摘要 |
| CT 专用实现 | local_graph 曾包含专用求解核心 | 改为 deprecated 兼容适配器，内部调用通用图 |

## 保留的适配器与 deprecated 模块

- `SOLVER_CT_V1`：CT CoursePack 的已发布云端基线、回退目标和旧效果对照。
- `LocalCircuitSolverGraph`、`CircuitProblem`、`SolverExecution`：保留旧调用签名，字段映射到 AcademicProblem 后进入通用图。
- `POST /api/v1/tasks`、`POST /api/v1/chat` 与旧前端：保持现有非阻塞任务创建链。
- 旧 `services/course_pack.py`、`CoursePack` Pydantic 模型与 YAML loader：已删除；新运行时唯一 Course Registry 位于 `app/courses/registry.py`。

## 删除评估

本轮完成一次引用审计并删除两条无生产入口的旧分支：旧 CoursePack YAML loader 与迁移前 request policies；Redis Worker 保留但改为依赖新的 `TaskExecutor` 协议，避免破坏多进程部署。保留的 `TaskQueue`、`TaskExecutor`、CourseRegistry 与场景审查服务均有当前 API/Runtime 入口或独立脚本入口。

## 合并后的唯一职责边界

- XZDGraphState：唯一图状态，仅保存引用、摘要、结构化结果与轨迹。
- API Pydantic contracts：外部输入输出校验。
- AgentRegistry：任务执行单元和兼容工作流注册。
- CourseRegistry：课程规则、题型、模板、能力声明和回退配置。
- CapabilityRegistry：跨课程能力到工具的声明映射。
- ToolRegistry：确定性工具元数据、启用策略和 handler。
- GraphFactory：从共享依赖创建任务图。
- AcademicProblemSolverGraph：通用、有限、可追踪的求解编排。
- TaskExecutionCoordinator + RuntimeTaskEngine：异步生命周期、租约、Runtime 节点、事件与结果治理。

## 暂不能删除

- SOLVER_CT_V1 及其历史输入：按冻结规则只读保留，不作为当前 Runtime 依赖。
- AgentRequest/AgentResult：`POST /api/v1/tasks` 和 RuntimeTaskEngine 稳定协议。
- AgentRequestV2/AgentResponse：对话 API 边界，不是图状态。
- WorkflowContextBundle：真实执行链的 RAG 证据复用协议。
