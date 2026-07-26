# Debug 控制台 UI 指南

## RAG 调试

`/debug/rag` 首屏保留请求输入、轻量索引状态和最近链路概要。检索过程、上下文、云端调用、引用校验和评测使用标签页分层。通道结果支持 BM25、Dense、RRF、Rerank、Final 和 Images；空通道显示 EmptyState。JSON 使用统一代码查看器，凭据和完整 Flow ID 不返回前端。

允许云端时会在运行前确认；评测达到 20 条或允许云端时也会确认。`/debug/rag?scenario=fallback` 载入受控本地降级场景，不修改 `.env`。

## Agent 管理

`/debug/agents` 以表格显示名称、生命周期、Provider、Flow 配置布尔值、课程、RAG 策略和最近测试。详情分为概览、输入输出协议、RAG/Fallback、契约测试与执行计划。

“验证配置”和“Dry Run”是主要动作；“运行 Mock”和结构比较是次要开发动作；允许真实 Cloud 时需要二次确认。生产或关闭 Debug 动作时按钮保持禁用。Mock 输出始终带开发模拟标识。
