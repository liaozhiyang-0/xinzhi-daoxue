# 芯智导学测试与验证报告

本轮按用户要求未执行全量测试，仅执行核心链路、文件/会话/检索定向测试和一次真实浏览器验收。

## 1. 通过的测试

| 命令/范围 | 结果 |
|---|---:|
| `test_agent_runtime.py` + `test_knowledge_qa_runtime.py` + `test_task_creation_is_non_blocking.py` + `test_sse_reconnect.py` + `test_student_web.py` + `test_multimodal_rag.py` | 39 passed，42.31s |
| `test_attachment_contract.py` + `test_file_upload.py` + `test_document_ingestion.py` + `test_task_session_commit.py` + `test_experience_memory.py` + `test_knowledge_api.py` + `test_external_search_and_fetch.py` | 48 passed，87.43s |
| `test_student_web.py::test_student_page_uses_unified_task_and_event_apis` | 1 passed，15.74s |
| `test_config_validation.py` | 13 passed，1.32s |
| `test_agent_runtime.py` + `test_knowledge_qa_runtime.py` 修复后回归 | 20 passed，19.81s |
| Knowledge QA timeout 定向用例 | 2 passed，1.42s |
| 学生 Runtime API E2E、Runtime handoff 合同 | 5 passed，22.99s |
| `ruff check`（本轮 Python 变更文件） | 通过 |
| `node --check ui-core.js`、`node --check workspace.js` | 通过 |
| `git diff --check` | 通过 |

## 2. 真实页面检查

浏览器读取 `/workspace` 的 DOM 并操作已有历史会话，没有发送新用户内容：

| 检查 | 结果 |
|---|---|
| 页面入口、输入框、发送按钮、会话列表 | 通过 |
| 历史输入恢复 | 通过 |
| 历史图片恢复 | 通过 |
| 论文资料卡片 | 6 条可见，摘要和元数据可见 |
| LaTeX/KaTeX | 5 个公式节点，0 个 `math-render-error` |
| 孤立闭合公式标记 | 0 个 |

## 3. 未执行/受环境限制

- 未执行全量 Pytest、全量 Ruff/Mypy、Docker 重建和并发压测。
- Mypy 定向检查被 NumPy stub 的 Python 3.12 语法阻断；项目当前 mypy 配置为 Python 3.11。
- 外部 provider 当前为 deferred/not_initialized，因此未把实时网络 provider 成功率写入稳定基线。

## 4. 关键警告

测试只有既有依赖警告：Starlette TestClient/httpx 弃用提示、LangChain `allowed_objects` 默认值变更提示；本轮没有新增测试失败。
