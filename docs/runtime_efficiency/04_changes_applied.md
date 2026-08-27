# Changes applied

本轮只做了与稳定性、可观测性和浏览器验收直接相关的小改动：

1. Runtime diagnostics 补齐阶段失败状态、结果校验、任务提交和工具执行阶段。
2. 稳定性脚本保留 SSE 投影、上下文哈希、计数器和 fallback/retry 分层，避免把原始问答写入证据。
3. Playwright smoke 适配当前 Legacy Workspace 的六能力按钮和自然语言输入，不再操作已经隐藏的旧课程选择器；图片测试支持外部指定 fixture，并补充了 500/503/504、API 延迟、SSE 中断恢复、附件、会话恢复和快速连续提交故障场景。
4. 生成本目录的机器可读证据和 markdown 交接文档。

已知验证：runtime timing 相关测试与 Ruff/Mypy 目标文件检查通过；浏览器 acceptance 在本地 FastAPI 测试服务上通过，包含输入恢复、停止按钮终态、SSE、附件边界、移动/暗色视图和多轮路径。完整历史回归曾得到 `2048 passed, 15 skipped, 6 failed`；6 个失败属于已有契约/删除 React 旧路径/模型清单等问题，不能在本报告中伪称为全绿。
