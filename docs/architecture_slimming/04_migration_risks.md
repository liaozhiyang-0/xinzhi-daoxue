# 收缩后的迁移风险与验证边界

| 风险 | 受影响文件/目录 | 必须验证 |
|---|---|---|
| 页面资源断链 | `workspace.html`、`workspace.js`、`static/debug/ts/` | `/student`、`/workspace`、静态资源 200；Legacy 工作区提交任务 |
| Chat/Tasks 分叉 | `api/v1/orchestration.py`、`api/v1/tasks.py` | 两入口都返回非阻塞 202；任务、Planner 快照、SSE 和结果合同一致 |
| 冻结能力误执行 | `runtime_task_engine.py`、`tasks.py`、`orchestration.py` | capability 显示 frozen；新数据分析任务 409；Runtime 注册表无分析服务 |
| 旧历史文档误导 | `docs/history/` 与现行 `docs/` | 现行文档不指向已删除的 React/旧 CT 路径；历史资料明确标记仅供审计 |
| 评测证据误删 | `evaluation/cache`、`evaluation/reports`、`真实测试题` | 先完成用途、所有者、再生方式和引用清单，未经确认不删除 |
| 数据库状态破坏 | `apps/api/alembic/`、本地 DB | 只增量 migration；`alembic heads` 与配置校验通过 |
| 运行时外部依赖误触发 | Provider、`.env`、`scripts/` | Mock/dry-run 优先；不打印密钥；真实调用只在已发布且 Flow ID 完整时执行 |
| CSS/字体不完整 | `static/debug/*.css`、`vendor/katex` | 浏览器冒烟和截图检查文字、公式、移动宽度，无裁切/404 |
| Unicode 数学文本告警 | KaTeX 渲染课程回答中的 `①` 等字符 | 后续统一文本规范化或配置 strict-mode 边界；本轮未改数学渲染器 |

本轮未做 Docker build/up、真实 Provider 调用或全量 Pytest；这些不是静态删除可以推导的结论，需在
专门验收轮次执行并单独记录日志。
