# 新 Agent 接入指南

## 标准流程

定义本地 Runtime handler → 在 `agent_configs/registry.yaml` 增加 AgentDefinition → 配置输入/输出映射 → 选择 Parser → 选择 RetrievalPolicy → 选择 fallback → validate → dry-run → Mock/契约测试 → 设置 `enabled: true` 与 `publication_status: local`。

不要把密钥写入 YAML、日志、截图或测试 fixture。新增 Agent 不创建旁路 HTTP Client、Provider、RAG Service 或正式 API。

```powershell
.\.venv\Scripts\python.exe scripts\agent_cli.py validate
.\.venv\Scripts\python.exe scripts\agent_cli.py show TEACH_01_LESSON_PREP_V1
.\.venv\Scripts\python.exe scripts\agent_cli.py dry-run TEACH_01_LESSON_PREP_V1 --course CT --intent explain_concept
.\.venv\Scripts\python.exe scripts\agent_cli.py test-contract TEACH_01_LESSON_PREP_V1
```

开发环境需要显式预热时调用 `POST /api/v1/debug/rag/prewarm`，请求体例如 `{"models":["text"]}`；只有确实需要多模态或重排时才加入 `image`/`reranker`。该接口在生产环境禁用，启动健康检查不会触发模型加载。

## 最小配置示例

无 RAG Agent：设置 `retrieval_policy.enabled: false`、`mode: no_rag`，只映射用户输入，fallback 可选 `planned_response` 或 `manual_review`。

文本 RAG Agent：设置 `mode: text_rag`、`text_top_k: 3`、`image_top_k: 0`、`reranker: off`，映射 `retrieved_context`。

教学类 Agent：参考 `TEACH_01_LESSON_PREP_V1`，限制 `user_roles: [teacher]`，使用 `multimodal_rag`，只在备课确需图示时启用图片，业务输出放入 `business_data.lesson_flow`。

科研类 Agent：默认 `external_source_context`，不查询课程知识库；只接收用户提供的可信来源，fallback 使用 `manual_review`，不要把课程 RAG 当作论文事实来源。

## 发布检查

1. required 输入均有映射且可转为 String。
2. Parser 能把 Fake 响应封装为统一结果。
3. `local_ready=true` 且 Debug 不显示敏感配置。
4. 不支持的课程、角色和输入模态在 Runtime 执行前被阻断。
5. 本地边界与降级测试覆盖真实任务合同。
6. 通过 Ruff、Mypy、Pytest、RAG、配置和敏感文件检查后再发布。
