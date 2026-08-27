# 剩余复杂度与服务候选

本表是静态审计候选，不表示已经确认可以删除。判断标准是：是否有活动调用方、是否承载持久化/协议
边界、是否有测试覆盖，以及合并后能否保持非阻塞任务创建和 SSE 顺序。

| 候选 | 当前关联 | 建议 | 风险 |
|---|---|---|---|
| `TaskCreationService` | `/tasks`、`/chat`、场景绑定、Planner 快照、持久化 | 保留为唯一创建边界；继续拆小函数 | 改动会影响所有入口和任务状态 |
| `TaskRuntimeLifecycle` / `RuntimeTaskEngine` | Worker、任务租约、Runtime Boundary、失败/完成提交 | 保留外观，内部按准备/执行/提交继续收敛 | 影响恢复、取消、重试和跨进程租约 |
| `RuntimeExecutionBoundary` | Runtime 业务注册表、CanonicalPlan、Manifest、Legacy fail-closed | 保留为唯一执行所有权边界 | 删除会重新引入 Provider/Runtime 分叉 |
| `InternalAgentExecutionService` | 学科求解、通用问答、教学 Agent、学术写作、冻结数据分析 | 保留；将分析分支继续隔离到独立模块 | 共享内部 Hub 和结果格式，贸然拆分会复制 Provider 链 |
| `ResearchAnalysis*` | 冻结能力的契约、测试和显式 409 | 当前保留为冻结开发包，不进入默认注册；解冻时单独验收 | 删除会破坏已有任务数据解释和边界测试 |
| `TaskPresentationService` / `TaskResultPresentationService` | Legacy 工作区、Chat 结果、历史兼容字段、证据与公式 | 保留单一展示投影，后续消除重复映射 | 改动可能导致旧结果不可读或误显示证据 |
| `RAGRetrievalService` / `KnowledgeBaseService` | 课程索引、图片检索、证据包、Debug 与 Runtime | 保留共享 RAG；只清理已证明无调用的适配器 | 课程素材和多模态结果存在隐含依赖 |
| `PlannerService` / `TaskRouter` | 输入预检、CanonicalPlan、兼容路由、路由测试 | 保留职责分界，禁止再增加第二套 Planner | 路由、计划和 Runtime 的顺序是协议的一部分 |
| `TaskProgressService` / `TaskQueryService` | 轻量兼容导出与 API 查询 | 候选合并，但先做调用图和公共导出检查 | 可能是外部脚本或旧测试的导入入口 |
| `task_executor.py` 与 `application/tasks/coordinator.py` | 本地执行器、队列执行器、Worker 共享协调器 | 保留薄外观；后续只合并重复代理函数 | 任务创建必须保持非阻塞 |
| `overall_routing.py` / `intent_plan.py` | Shadow 或历史兼容路径 | 继续限定为 shadow/compat；确认生产零调用后再归档 | 可能仍被诊断脚本或旧快照读取 |
| `services/` 中的专项审计/报告模块 | 评测、知识审计、质量门、发布门禁 | 不按低覆盖率删除；按 API/脚本/测试反向证明后再处理 | 低覆盖率不等于无调用 |

## 结论

当前最有价值的下一步不是继续删除大目录，而是为 `TaskCreationService`、Runtime Boundary、结果投影
和 RAG 建立稳定的边界测试，然后逐项消除薄兼容层。目录、类名和低覆盖率只能产生候选，不能单独
证明文件无用。
