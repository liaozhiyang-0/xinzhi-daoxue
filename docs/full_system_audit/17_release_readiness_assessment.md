# 发布就绪评估

## 结论

**NOT READY：不建议面向外部真实用户发布。**

### 可保留的受控能力

- 本地 `/health`、基础依赖和 RAG health 可用。
- 已知课程词的文本召回、文件抽取/chunk、SSE 重放、刷新恢复在样本中通过。
- 可展示受控 demo，但必须标明 local/demo、结果需人工复核，不能把 Agent readiness 当生产承诺。

### 发布阻塞

1. 修复 CONTEXT-001：多轮主题、意图和输出格式保持；至少覆盖同题追问、只要公式、只要提示、切换课程和新会话隔离。
2. 修复 UI-STATE-001：所有 answer/evidence/artifact 必须按 task/message owner 隔离；新任务不能显示旧产物。
3. 统一 `/api/v1/chat` 与 `/api/v1/tasks` 的 canonical execution contract，消除 E2E-001。
4. 统一 route/Planner/capability/validator 绑定，消除 ROUTER-001，并为普通问答建立成功、低证据和拒答契约。
5. 为知识和研究检索增加相关性阈值、去重、no-match/abstention 和证据候选标识，消除 RAG-001/RESEARCH-001。
6. 定义 cancel 的状态机和最大收敛时间；在取消未完成时不显示“已停止”。
7. 将实际入口、源码、构建和自动化测试统一到同一前端表面。

## 重新放行条件

- P0 清零；P1 全部有回归测试且通过。
- 每个对外场景明确 `production_ready`、fallback、人工复核边界和可见 UI 状态；未发布 Agent 不从自然语言入口伪装成可用。
- 新鲜测试矩阵：每个核心场景单轮≥10、多轮≥10、取消≥5、刷新恢复≥5、SSE 重连≥5、无匹配检索≥5；记录成功率、错误分类、终态收敛、证据相关性和 artifact ownership。
- 失败 trace 的 stage timing 完整；任务/模型/RAG/队列指标按 request/task/route 可关联。
- 冷启动在 UI 显示预热/排队状态，且不能让用户误认为服务不可用或重复提交。

## 本轮验证状态

配置、敏感文件、repo drift、Ruff、Mypy 和 Web TypeScript 已通过；全套 Pytest 为 2038 passed、15 skipped、15 warnings，耗时 29 分 21 秒。Docker 未启动或重建。警告主要来自依赖弃用提示和少量 SQLite ResourceWarning，需在后续维护中清理，但不改变本轮测试退出码为 0 的事实。
