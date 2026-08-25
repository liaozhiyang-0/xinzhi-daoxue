# 六业务场景失败归因与共享根因

## 修复前失败

| 统一分类 | 次数 | 场景 | 证据 | 共享根因 |
|---|---:|---|---|---|
| AGENT_NOT_FOUND | 5 | 知识治理 | 路由已选 LEARN_01_KNOWLEDGE_QA_V1，随后 local_runtime_handler_missing；AgentDefinition 实际存在 | Runtime local-agent 启动白名单只读取主 agent_id，遗漏 supported_agent_ids，已注册 Agent 落入旧 Provider handler |
| RUNTIME_TIMEOUT | 2 | 学习路径 | knowledge.execute 约 30 秒处 runtime_node_timeout；无 knowledge.retrieved 事件 | Provider timeout 与实际模型调用延迟相同，Runtime 节点在返回前超时 |
| 业务检查点 | 2 | 科研检索 | external_retrieval.failed 后进入 external_evidence_review_required，状态 waiting_review | 外部 Provider 的 HTTP 500、timeout、no-records 需要人工审核，不是内部 Runtime 崩溃 |
| 非阻塞配置风险 | 5 | 图像解题 | submitted_scenario_id 为空，但成功进入 ACADEMIC_PROBLEM_SOLVER | 通用 Solver 没有 catalog 场景条目，不应虚构场景契约 |

初始 30 次未观察到 ROUTER、AGENT_DISABLED、TOOL_UNAVAILABLE、PERSISTENCE、SSE 或 FRONTEND_RENDER 失败。所有失败任务都有可见失败提示，所有等待任务都有审批控件。

## 修复后证据

- 知识治理 5/5 进入 LEARN_01_KNOWLEDGE_QA_V1 的 knowledge.execute → knowledge.verify，全部 completed。
- 学习路径 5/5 进入 LEARN_01_LOCAL_RETRIEVAL_V1，每次产生 knowledge.retrieved(hit_count=4,retrieval_calls=1)，全部 completed。
- 科研检索的外部失败仍被准确保留为 waiting_review；成功检索的任务 completed，未伪装为内部失败。
- 全部 30 次回归均有可见终态：completed 结果、人工审批检查点或图像解题复核提示。
