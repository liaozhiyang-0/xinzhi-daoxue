# 统一 Execution Debug 使用指南

访问 `/debug/execution`，输入已完成任务 ID；页面也会读取当前浏览器最近一次 Workspace 任务。旧 `/debug/rag` 保持可访问，并打开同一控制台的检索标签。

六个标签：

1. 任务概览：任务边界与简化步骤。
2. 路由与计划：真实 RouteDecision 与 ExecutionPlan。
3. 检索与证据：策略、候选 Trace、进入工作流与实际引用对照。
4. 工作流调用：Provider、云端状态、Parser、request_id 与 Mock 状态。
5. 引用与结果：CitationValidator、最终来源、fallback 和回答。
6. 性能：路由、检索、上下文、云端、引用和总耗时瀑布。

页面只调用一次 `/api/v1/debug/execution/{task_id}`；标签切换不再请求 Trace，大 JSON 只在载入任务后出现。接口过滤 Authorization、API Key、Secret、Token、UID、完整 Flow ID 和原始 Prompt 键。
