# Agent 扩展指南

1. 注册新能力：先在 `CapabilityBindingRegistry`、`CapabilityRegistry` 和 `SkillRegistry` 声明稳定 capability/skill/handler binding；只有确实需要新的执行边界时，才在 `agent_configs/registry.yaml` 增加 Agent 条目。不得新建第二个 Registry。
2. 新任务族：先在 TaskFamily 增加稳定枚举，再更新 Supervisor 的 `_task_family`；只有复杂状态/循环才建图。
3. 新子图：在 `orchestrator/graphs` 实现，使用 XZDGraphState，并在 GraphFactory 注册；通过工厂注入 Provider/RAG/工具/注册表/checkpointer。
4. 新 CoursePack：向 CourseRegistry 注册；只添加题型、能力、模板、校验、格式与回退，不复制 AcademicProblemSolverGraph。
5. 新 Capability：向 CapabilityRegistry 注册跨课程能力及 tool IDs；不生成最终教学回答。
6. 新工具：向唯一 ToolRegistry 注册完整 ToolDefinition 与 handler；代码执行/文件副作用必须声明 sandbox 和 side effect。
7. 模型路由：在 `config/models.yaml` 注册模型，在 `config/model_routes.yaml` 配置 primary/fallback/verifier；代码只调用 ModelService。
8. 本地回退：复用统一 Runtime 与 ModelService。Agent 必须声明 local handler；CoursePack 只返回 fallback target，不直接绕过 Runtime。
9. 测试：覆盖注册、路由、输入边界、结果、失败/回退、RAG 复用、SSE 顺序和敏感信息。外部结果须标注真实云验证或本地/Mock。
10. 避免复制：新增前搜索 GoalContract、CanonicalPlan、GraphState、Registry、Router、Provider、RAG、file parser、Trace 和同名工具；兼容入口只转发到 Planner/Runtime 核心。

预留 Agent ID 通过 `/api/v1/capabilities` 返回，但本轮不实现自由对话式多 Agent 群。所有新任务由 Planner 依据已注册 capability/skill/handler 生成 CanonicalPlan；Agent ID 只是兼容别名和执行实现元数据。
