# 下一阶段 Runtime 延迟目标

本轮只登记目标，不修改 Runtime、Provider、RAG 或 Prompt。每项必须先采集带 request/run/trace identity 的耗时，再决定是否优化。

| 优先级 | 目标 | 当前层 | 可能重复工作/影响 | 风险 | 下一步 |
|---:|---|---|---|---|---|
| 1 | 任务准备 | `UnifiedRequestPreparationService` / `TaskRuntimePreparation` | 会话、附件、场景和上下文可能多次规范化 | 改变输入合同 | 记录各阶段 span 与 payload fingerprint |
| 2 | 路由预检 | `TaskRouter` / `ScenarioPreflight` | 可用性、课程和 intent 可能重复读取 | 错路由或越权 | 合并只读快照，保持 fail-closed |
| 3 | Planner | `PlannerService` | shadow、canonical plan、兼容计划可能重复生成 | 破坏 plan lineage | 比较同一 run 的计划 hash |
| 4 | 上下文构建 | `SessionContext` / context assembly | 会话压缩、记忆、材料上下文重复拼接 | 泄露或丢当前轮 | 按字段统计字符预算和缓存命中 |
| 5 | RAG | `RAGRetrievalService` / `KnowledgeBaseService` | 查询改写、向量/词法检索、证据整形串行 | 证据错配 | 以 evidence id 验证并行化收益 |
| 6 | 模型调用 | Provider/`ModelService` | retry、fallback、summary 可能多次调用 | 费用和重复副作用 | 只在授权 Provider 上做 bounded replay |
| 7 | Reflection/质量门 | `AgentResultGovernance` / quality gates | 结果解析、校验、重规划可能重复遍历 | 把不确定结果误判成功 | 采集每次 gate 的输入输出 hash |
| 8 | 数学后处理 | math formatting / circuit tools | 公式解析、渲染和 SVG 可能重复转换 | 破坏公式/电路可读性 | 用固定 fixture 做前后对比 |
| 9 | Session commit | task/session commit services | 任务、消息、学习状态可能多次落库 | 事务一致性 | 按事务和索引等待拆分测量 |
| 10 | SSE | event service / `event_stream` | 事件持久化、重放和页面投影可能重复序列化 | sequence/reconnect 破坏 | 以 Last-Event-ID 做端到端测量 |

优化前置条件：先完成定向基准、保持任务创建非阻塞、保持事件 sequence 单调，并证明没有新增 Provider 或 Runtime 分叉。
