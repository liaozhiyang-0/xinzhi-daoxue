# 芯智导学稳定基线收口报告

## 1. 基线信息

- 分支：`refactor/platform-modernization`
- 基线提交：`3b017fb test(eval): expand benchmark coverage`
- 当前工作区：保留本轮未提交变更，未自动提交、合并或推送。
- 数据库：未新增或修改 migration；重启仅停止/启动容器，数据卷保留。
- 当前运行方式：Supervisor → team launcher → Uvicorn；Provider 为 `local_runtime`，Task executor 为 local。

## 2. 核心稳定性结论

核心链路的 P0 为 0，核心 P1 已清零：

```text
浏览器工作台
  → 非阻塞 POST /api/v1/tasks
  → Session/Task/Event 持久化
  → LocalTaskExecutor / TaskRuntimeLifecycle
  → AgentRegistry / TaskRouter
  → Knowledge QA / RAG / Local Provider
  → ResultCommit / SessionCommit
  → SSE 或 polling
  → 历史恢复、资料卡片、KaTeX 展示
```

已收口的核心边界：

1. 纯文本问题不会因解释/总结意图自动启用图片检索。
2. Knowledge QA 节点超时跟随注册 Agent 定义，超时后 Task、AgentRun、Node 和事件使用稳定错误码收敛。
3. 任务创建保持非阻塞；执行发生在后续 Runtime/Executor 路径。
4. 会话历史、图片附件、科研卡片和公式卡片在实际工作区可见。
5. 资料卡片和论文摘要不再被固定高度/行数截断。

## 3. A-F 验证矩阵

| 用例 | 当前结论 | 证据 |
|---|---|---|
| A 纯文本问答 | 通过 | 图片策略回归、Knowledge QA Runtime、核心回归组 |
| B 图片输入 | 通过 | 图片附件合同/文件上传/多模态测试；浏览器历史图片恢复 |
| C 课程知识问答 | 通过 | RAG/Knowledge API 与 Runtime 测试；右侧资料卡片浏览器验收 |
| D 数学/公式展示 | 通过 | KaTeX 浏览器验收：5 个公式节点、0 个渲染失败、0 个孤立闭合符 |
| E 论文/网络资料展示 | 部分通过 | 已有科研任务的 6 张论文卡片可见；实时外部 provider 仍 deferred |
| F 多轮会话/记忆 | 核心通过，登录跨端未测 | 会话提交、Experience Memory、历史恢复和图片消息通过；未做真实登录跨浏览器 E2E |

## 4. 后续建议

只保留三个后续事项，不阻塞当前稳定基线：

- 解决 Python 3.11 与当前 NumPy stub 的 Mypy 兼容后再补全静态类型门禁。
- 在外部 provider 实际初始化后，补实时检索成功/超时/无结果/来源校验矩阵。
- 对约 3422MB 私有内存基线做连续问答和并发观测，再决定是否启用 Redis Worker 隔离。

本轮不建议继续切换前端技术栈；当前静态工作台与后端统一任务链已恢复到可验证、可继续维护的状态。
