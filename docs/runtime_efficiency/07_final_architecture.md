# Final architecture

```text
Legacy Workspace (/workspace)
        |
sessions + POST /api/v1/tasks
        |
request preparation -> routing -> existing Runtime executor
        |
planner/capability -> context/RAG -> model/tool nodes
        |
reflection -> quality gate -> result validation -> task/session commit
        |
SSE projection + persisted structured result + RuntimeDiagnostics
```

诊断是横切能力，不是第二条执行链。Provider 选择仍复用既有 ModelService、Provider registry、环境变量和 HTTP 调用链；外部检索的备用 Provider 仍由既有 retrieval factory/execution 链按 tier 运行。Legacy Workspace 保持入口，未恢复已删除的 React 旧入口。仓库中没有为本任务新增第二个 Runtime、第二套 LangGraph、第二个 Planner 或第二套 Provider/Session/RAG runtime。

证据边界：local mock/deterministic 用于可重复回归，real_model 用于受控真实调用，Playwright 用于真实浏览器交互；三者在报告中分开，不互换结论。
