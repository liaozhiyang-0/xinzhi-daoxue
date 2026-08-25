# 六业务场景稳定性修复报告

## 最小修复

| 文件 | 修改 | 原因 |
|---|---|---|
| apps/api/app/static/debug/workspace.js | 卡片点击保存 data-course / data-intent；提交使用 state.activeCourse / state.intentOverride；编辑示例题目时清除 wiring | 避免已声明场景降级为 unknown/AUTO，避免普通编辑题继承示例路由 |
| apps/api/app/bootstrap/runtime_task_engine.py | local Runtime allowlist 同时收集服务主 agent_id 与 supported_agent_ids；知识 Runtime 使用 AgentRegistry | 使知识治理 Agent 真正进入 Runtime，而不是落入不存在的旧 handler |
| agent_configs/registry.yaml | LEARN_01_LOCAL_RETRIEVAL_V1 provider timeout_seconds 从 30 调整为 60 | 避免 knowledge.execute 在 Provider 返回前超时 |
| apps/api/tests/test_unified_web_ui.py | 更新 wiring 断言并新增卡片 intent/course 与编辑清除测试 | 固化前端场景契约 |

没有新增 Agent，没有改造 Runtime 执行框架，没有引入 React，也没有新增外部 Provider。

## 定向验证

已执行定向 Pytest：apps/api/tests/test_unified_web_ui.py、apps/api/tests/test_knowledge_qa_runtime.py、apps/api/tests/test_runtime_launch_policy.py，结果 56 passed。

Ruff check、node --check apps/api/app/static/debug/workspace.js 和 git diff --check 均通过。按用户要求未执行全量测试。

Supervisor 重启后健康检查返回 status=ok，数据库、Redis、MinIO 和本地运行时均正常。

## 回归方法

修复后从当前 /workspace 新建 30 个会话，六个卡片各提交 5 次。每次检查工作台状态、Task API、持久化 TaskEvent、Runtime 节点、RAG/Provider 事件和前端结果。

收口结果见 10_scenario_stability_closeout.md。
