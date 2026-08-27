# 当前系统基线

## 版本与运行环境

| 项目 | 观测值 |
|---|---|
| 审计日期 | 2026-08-26 |
| 分支 | `feature/circuit-capability-v1` |
| HEAD | `021d6e3834d19b00d0ced4ca94ba04db8aceaa8c` |
| 工作区 | 审计开始前已 dirty；保留原有修改 |
| API | `uvicorn app.main:app --app-dir apps/api --host 0.0.0.0 --port 8000` |
| API 健康 | `GET /health` = 200；DB/Redis/MinIO 可达 |
| 已观察依赖 | Postgres、Redis、MinIO、Qdrant 已运行；未由本审计启动/重建 |
| 实际学生入口 | `GET /workspace` -> `apps/api/app/static/debug/workspace.html` |
| React 入口 | `/workspace-react` 检查 React 构建后重定向到 `/workspace`；未成为实际入口 |

## 结构与数据流

主入口 `apps/api/app/main.py` 组装 FastAPI、AgentRegistry、TaskRouter、ApplicationContainer、TaskExecutionCoordinator、Planner、RAG、Provider、Runtime 和可观测性组件。HTTP 路由集中在 `apps/api/app/api/v1/router.py`，覆盖 auth、sessions、tasks、files、scenarios、agents、knowledge、learning、memories、models、research、debug 和 evaluation。

用户工作台的主要链路是：浏览器身份/游客会话 -> `POST /api/v1/tasks` -> 任务排队和 SSE/轮询 -> Agent/Planner/Knowledge Runtime -> 结果契约验证 -> 会话消息、证据和可视化产物渲染。另有 `POST /api/v1/chat` 兼容链路，本次观察到它与 tasks 链路行为不同。

## 注册规模与配置概览

- 配置校验发现 13 个 Agent 定义；`SOLVER_CT_V1` 为 published，数据分析 Agent 被冻结，其他多为 local publication。
- `config/scenarios.yaml` 有 10 个目录条目，其中 1 个数据分析场景冻结/不在当前 readiness API 列表，当前 readiness API 返回 9 个场景。
- 当前工作台首页展示 6 个 showcase 场景；后端 readiness 可见的研究、频谱、文本诊断、评分量规等能力不全部有 UI 卡片入口。
- `config/skills` 有 CT、AE、DE、KNOWLEDGE、RESEARCH 五组 YAML；应用内存在 Skill Registry、binding、policy、evaluation 和 retriever。
- `apps/api/app/tools` 当前包含 calculator、sympy_solver、unit_checker 及 registry；电路可视化另有 circuit tool/renderer 链路。
- RAG health：文本模型 `BAAI/bge-small-zh-v1.5`、图像模型 `google/siglip2-base-patch16-224` 已加载，Qdrant 可达，文本向量 27101、图像向量 3309；reranker 未加载。

## 公开健康与 readiness 快照

- `/api/v1/models/health` 返回 `live=false`，但 Spark 与 DashScope 均显示 configured/available；该状态不能证明实际任务链可生成结果。
- `/api/v1/learning/runtime-readiness` blockers 为 `learning_runtime_authorized_paired_evidence_missing` 和 `canary_release_evidence_missing`；feedback loop enabled=false。
- `/api/v1/scenarios/readiness` 的 9 个场景全部 `production_ready=false`；知识治理是 `fallback_only`，其余主要是 `configured_unavailable`。
- Prometheus 快照（包含既有历史和本轮运行）：任务 completed 2520、failed 95、cancelled 62、waiting_review 85、waiting_user 2；最近任务 p95 65715 ms，队列 pending/dead-letter/attempts 均为 0。该快照不是本轮独立性能实验。

## 基线边界

本文件记录“当前可观察系统”，不把历史 `docs/audit` 中旧分支的 E2E 结果当作本轮结果；旧文档只作为背景参考。没有读取 `.env` 内容，也没有将任何凭据写入报告。
