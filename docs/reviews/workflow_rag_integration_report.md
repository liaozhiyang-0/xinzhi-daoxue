# 工作流与 RAG 融合实施报告

## 原割裂位置

原 TaskRunner 把 Packet 只用于 LEARN 的 `retrieved_context`，结果再独立拼装 `knowledge.hits`；学生端从 `knowledge.hits` 或 `citations` 猜测来源，RAG Debug 则维护另一套 Trace。云端失败时本地 fallback 会再次运行知识检索。

## 新执行链

TaskRunner 现在从唯一 RetrievalResult 构建 Packet 和 WorkflowContextBundle。LEARN 注入同一 `retrieved_context`，云端返回 S 编号后由 CitationValidator 对照同一 Bundle；TaskPresentationBuilder 再生成 presentation、TaskExecutionSummary 和 evidence_view。fallback 复用首次 RetrievalResult，不重复 RAG。

## Agent 模式

- LEARN_01：`grounded_generation`。证据进入云端；只有合法 S 编号标为“已引用”。
- SOLVER_CT：`method_reference`。检索公式/方法/易错点，但冻结 Flow 不接收独立知识上下文字段；界面只显示“方法参考”。
- TEACH：课程生成型可用 grounded；学情分析用 `data_context_only`。
- RESEARCH：外部/用户来源映射为 `user_sources_only`，不以课程库支撑科研结论。

## 展示与 fallback

后端 presentation 负责中文标题、状态、来源摘要、Provider 标签、fallback 信息、证据说明和简化步骤。Mock 显示“开发态 Mock”；云端失败显示本地降级原因；证据不足不生成虚假引用。

## 端到端验证范围

单元与集成测试覆盖 Bundle、模式映射、LEARN 合法引用、SOLVER 方法边界、fallback/Mock 文案、旧路由、脱敏与统一 Debug。全量结果为 178 passed、13 skipped，覆盖率 83%。浏览器截图使用真实本地任务 API 和持久化 Trace，但为避免模型冷启动，显式关闭重量 RAG 并使用 Mock/本地边界；17/17 场景通过且页面异常为 0。

60 条真实本地 RAG 评测为 60/60 用例通过、课程串扰 0、引用合法率 100%、Top-3 召回代理 96.7%；热路径检索 p50 878ms、p95 1467ms。首条冷启动为 61.8s，图片模型首次加载约 15.3s，因此 2120ms 平均值不代表热路径。真实星辰 LEARN/SOLVER 专项批次长时间无输出并超过外层限制，残留进程已终止，本轮没有可报告的真实云端通过结论。

## 未完成工作流适配

未来 Agent 只需在 AgentDefinition 配置 retrieval policy；Provider 和 TaskRunner 不复制。未发布 Agent 保持 planned/mock 标签。若新增真实输入字段，必须先发布并验证 Flow 合同，再允许 `grounded_generation`。
