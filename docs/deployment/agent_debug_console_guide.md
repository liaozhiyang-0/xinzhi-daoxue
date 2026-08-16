# Agent 接入控制台指南

地址：`http://127.0.0.1:8000/debug/agents`。

页面显示 Agent 版本、发布状态、configured 布尔值、Parser、RetrievalPolicy、fallback、输入/输出映射、mock profile、最近一次进程内契约结果和 ExecutionPlan。页面永不返回 Key、Secret、Authorization、本地绝对资料路径或向量。

支持 Validate、Dry-run、Mock 和 fixture 契约测试。结构校验只比较字段、类型、缺失和额外字段，不判断答案语义优劣；所有动作均在本地 Runtime 边界内执行。

`RAG_DEBUG_ENABLED=false`时接口不可用；production默认禁止所有执行动作，页面仅可读取脱敏注册状态。页面不能修改`.env`或读取任意本地文件。
