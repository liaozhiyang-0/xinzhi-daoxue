# 服务候选清单

这是下一阶段的静态候选，不是删除清单。候选只有在活动调用方、公共导出、脚本和测试均完成反向证明后才可合并或删除。

| # | 候选 | 当前关联 | 建议动作 | 主要风险 |
|---:|---|---|---|---|
| 1 | `TaskCreationService` | `/tasks`、`/chat`、场景绑定、持久化 | 保留唯一创建边界，拆分内部函数 | 任务状态和幂等 |
| 2 | `UnifiedRequestPreparationService` | `/chat` 与 `/tasks` 共用输入合同 | 只消除重复规范化 | 附件/会话字段漂移 |
| 3 | `TaskRuntimePreparation` | task → Runtime 输入、plan 和上下文 | 建立单阶段 snapshot | 破坏 plan lineage |
| 4 | `RuntimeTaskEngine` | worker、租约、边界和恢复 | 保留外观，压缩重复适配 | 恢复/重试 |
| 5 | `RuntimeExecutionBoundary` | 唯一 Runtime 业务注册与执行所有权 | 保留并强化边界测试 | Provider 分叉 |
| 6 | `InternalAgentExecutionService` | Academic、Teaching、Knowledge、Research 内部 Agent | 保留共享 Hub，隔离专项分支 | 复制 Provider 链 |
| 7 | `TaskExecutionCoordinator` | Runtime 任务执行协调 | 与 executor 做调用图对照 | 非阻塞保证 |
| 8 | `task_executor.py` | 本地提交与 Worker 入口 | 保留薄外观 | 后台任务丢失 |
| 9 | `TaskResultCommitService` | 结果、事件、checkpoint 落库 | 测量重复写入后再合并 | 事务一致性 |
| 10 | `TaskPresentationService` | 页面/Chat 结果投影 | 统一兼容字段映射 | 旧结果不可读 |
| 11 | `TaskResultPresentationService` | 结构化结果与证据展示 | 与 Presentation 做边界审计 | 证据误展示 |
| 12 | `RAGRetrievalService` | 课程检索、图片检索、证据包 | 只清理无调用适配器 | 证据错配 |
| 13 | `KnowledgeBaseService` | 资料摄取、索引和审计 | 保留数据边界，减少重复查询 | 教材/索引依赖 |
| 14 | `PlannerService` | CanonicalPlan 与 shadow plan | 禁止新增第二 Planner | 计划顺序 |
| 15 | `TaskRouter` / `OverallRouting` | 可用目标选择与兼容 shadow | 证明生产零调用后再归档 | 诊断快照 |
| 16 | `TaskProgressService` | 轻量进度投影和兼容导出 | 核查公共 import 后合并 | API 兼容 |
| 17 | `TaskQueryService` | 任务查询兼容导出 | 与查询端点做最小合并 | 外部脚本 |
| 18 | `SessionContext` / `SessionService` | 会话、记忆、上下文预算 | 以字段预算为依据拆分 | 跨轮上下文 |
| 19 | `ResearchAnalysisRuntimeService` | 冻结数据分析契约和边界测试 | 保持冻结，不进入默认 Runtime | 解冻误执行 |
| 20 | 专项审计/报告服务 | 评测、知识和发布门禁 | 以脚本/API/测试反向证明后再处理 | 低覆盖率误删 |

详见 `02_remaining_complexity.md` 与 `03_runtime_graph.md`。
