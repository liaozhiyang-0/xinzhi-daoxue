# 芯智导学问题审计报告

审计基线：`refactor/platform-modernization@3b017fb`
审计日期：2026-08-24
范围：API、Runtime、知识检索、资料卡片、会话历史、图片附件、SSE/polling；未执行全量测试。

## 1. 已确认问题

| 编号 | 等级 | 现象 | 根因 | 处理结论 |
|---|---|---|---|---|
| BUG-01 | P1 | 纯文本知识问答也可能预热/启用图片检索，增加启动耗时和内存 | 图片策略把 `explain/summarize` 意图当成图片检索条件 | 已修复：图片检索改为显式开关或真实图片输入才启用 |
| BUG-02 | P1 | Knowledge QA 节点超时远大于 Agent 定义，任务终态可能迟迟不收敛 | `knowledge_qa_runtime.py` 使用固定 900000ms，没有复用 `AgentDefinition.timeout_seconds` | 已修复：按注册 Agent 超时生成计划，并统一 `runtime_node_timeout` |
| BUG-03 | P1 | 资料卡片、论文摘要显示不完整 | `.evidence-summary` 固定 `max-height: 7.2em`；论文摘要固定 5 行 | 已修复：取消卡片截断，交由右侧面板滚动 |
| BUG-04 | P1 | 公式有 KaTeX 节点但会残留 `\]`、标题里的 `\(RC\)` 不编译 | 资料卡片使用 `preserveRaw`，绕过松散公式归一化；缺少行级孤立闭合符过滤 | 已修复：卡片使用统一数学渲染、标题支持行内公式、过滤孤立闭合符 |

## 2. 已验证但未发现生产缺陷

| 项目 | 证据 |
|---|---|
| 任务创建非阻塞 | `test_task_creation_is_non_blocking.py` 通过；创建接口与执行器边界分离 |
| SSE 重连与事件顺序 | `test_sse_reconnect.py`、Runtime 合同测试通过；使用事件 sequence/cursor |
| 会话历史恢复 | 浏览器刷新后可恢复历史输入；`loadSessionHistory` 同时读取消息与任务结果，并有 request sequence 防旧响应覆盖 |
| 图片输入恢复 | 历史电路题会话显示“题目原图 1”；图片任务 API 测试通过 |
| 记忆/上下文链路 | 会话提交、Experience Memory、上下文合同定向测试通过；真实登录用户的跨浏览器 E2E 未纳入本轮 |

## 3. 仍保留的风险

1. 当前本地配置为 `local_runtime`；健康接口显示外部检索 provider 为 deferred/not_initialized，因此本轮只验证了已有科研结果卡片和结构化展示，没有把“新鲜外部检索成功”当作稳定基线。
2. API 进程私有内存基线约 3422MB，属于 P2 观察项；本轮未做连续 10 次问答和并发压测，不据此贸然切换 Redis Worker。
3. Reranker 当前未加载；文本 RAG 与向量库可用，排序质量仍需单独评估。
4. Mypy 未能进入业务文件检查：环境中的 NumPy stub 使用 Python 3.12 `type` 语法，而项目配置为 Python 3.11。这是验证环境/依赖兼容问题，不是本轮代码错误。
