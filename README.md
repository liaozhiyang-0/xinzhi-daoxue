# 芯智导学：电子信息课程群多智能体平台

芯智导学当前是一个本地可运行的多智能体教学平台。阶段 2.2 在既有 FastAPI、TaskRouter、TaskRunner 和星辰 Provider 上增加统一工作流注册、确定性路由、受控降级与非敏感运行状态接口。

## 组员统一启动（Windows）

只需要安装 **Python 3.11-3.13、Git 和 Docker Desktop**。克隆仓库、启动 Docker Desktop 后，在仓库根目录执行：

```powershell
.\xzd.cmd doctor
.\xzd.cmd start
```

`start` 会自动创建 `.venv` 和本机 `.env`、安装缺少的依赖、启动 PostgreSQL/Redis/MinIO/Qdrant、执行增量迁移并启动 Web。它不会覆盖已有 `.env`，也不会打印 Key、Secret 或 Flow ID。启动成功后打开：

```text
统一首页  http://localhost:8000/
学生端    http://localhost:8000/student
演示中心  http://localhost:8000/demo?presentation=1
系统状态  http://localhost:8000/system
```

停止 Web 请在运行窗口按 `Ctrl+C`；再停止基础容器：

```powershell
.\xzd.cmd stop
```

常用命令：

```powershell
.\xzd.cmd status                         # 查看容器和 API 状态
.\xzd.cmd preflight                      # 会议前检查，不消耗云端额度
.\xzd.cmd preflight -WithCloud           # 显式执行真实云端检查
.\xzd.cmd index -Course CT -TextOnly     # 为本机 CT 教材构建文本索引
.\xzd.cmd start -Reload                  # 开发热重载
```

真实星辰凭据只填写在各自机器的 `.env` 中；Git 只保存空值模板 [.env.example](.env.example)。本地教材、向量索引、上传文件和模型缓存均被 Git 忽略。完整组员说明见 [团队快速使用指南](docs/deployment/team_quick_start.md)。

## 当前技术栈

```text
API 与任务编排：Python 3.11+ / FastAPI / 进程内非阻塞 TaskRunner
数据库：PostgreSQL（测试使用 SQLite）
缓存：Redis
文件存储：MinIO（开发环境允许本地回退）
迁移：SQLAlchemy 2 / Alembic
调试界面：FastAPI 静态 HTML / CSS / JavaScript
部署：Docker Compose
检索：BGE dense + BM25 sparse + SigLIP2 visual + Qdrant + RRF + BGE reranker
```

早期 Spring Boot、MySQL、Vue3 和 MaaS 微调方案已经移除。仓库只保留当前 FastAPI 多智能体平台、检索评测、运行文档与本地课程资料入口。

## 已完成阶段

- 阶段 0：冻结 `SOLVER_CT_V1` 基线、节点清单、发布检查和回归评测结构。
- 阶段 1：建立 FastAPI、统一 Agent 合同、Mock Provider、数据库、文件存储和 Docker Compose。
- 阶段 1.5：实现 HTTP 202、TaskRunner、递增事件 sequence、SSE 重连、取消、重试和本地调试页。
- 阶段 1.6：增加配置驱动的 AgentRegistry/TaskRouter、路由持久化、三课程检索元数据、v1/v2 评测闭环、RetrievalContextPacket 和 `LEARN_01_KNOWLEDGE_QA_V1`。
- 阶段 2.1：固化 `SOLVER_CT_V1` 的讯飞星辰 `stream=false` 文字/单图片调用、统一回答字段，并将 `/debug` 更新为一页式演示界面。
- 阶段 2.2：统一注册 dispatch、learning、teaching、research、infrastructure 场景；所有星辰 Agent 复用一个 Provider 和注册表输入映射，计划态工作流不阻塞启动。

## 当前能力边界

- CT `solve_problem` 路由到 `SOLVER_CT_V1`；`XINGCHEN_ENABLED=true` 且配置完整时调用真实星辰，否则在未启用时使用明确标识的 Mock。
- 星辰上游当前支持同步文字和单图片调用，不支持多图片、PDF 或上游流式调用。
- CT 的 `check_user_solution` 优先使用 `CHECK_01_ANSWER_REVIEW_V1`；当前计划态不可用时降级到 `SOLVER_CT_V1`，并注入“优先指出第一个错误”的检查指令。
- CT/AE/DE 的学习类意图优先使用云端 `LEARN_01_KNOWLEDGE_QA_V1`；未发布或未配置时降级到 `LEARN_01_LOCAL_RETRIEVAL_V1`。
- 模糊、UNKNOWN、低置信或未匹配输入仅允许进入一次受验证的云端调度兜底；兜底不可用时返回 `unresolved`，不会自动送入 `SOLVER_CT_V1`。
- 多图、PDF、空输入及 Agent 未声明的输入组合返回明确错误，不会静默丢弃附件。

## 本地知识库

本地只读输入为：

```text
电路理论/  -> CT
模电/      -> AE
数电/      -> DE
```

当前文本索引读取 UTF-8 Markdown；图片索引读取 JPG/JPEG/PNG/WEBP 原始像素。PDF、DOCX 和 ZIP 只登记元数据，不直接解析。原始教材、模型缓存和 Qdrant 数据目录均不提交 Git。

正式 RAG 使用真实 BGE 文本 Embedding、SigLIP2 视觉 Embedding、Qdrant 命名向量、原有 BM25 分支、RRF 融合和可配置 BGE reranker。生产链路不再包含哈希或随机伪 Embedding；模型失败会明确进入 degraded/failed。完整配置与实测结果见 `docs/knowledge/multimodal_rag_integration_guide.md` 和 `docs/reviews/multimodal_rag_implementation_report.md`。

元数据覆盖层位于 `knowledge_config/`；自动发现的 OCR 清洗项保持 `review_status: draft`，运行时只应用人工批准项，不修改原始 Markdown。

## 任务路由

| course_id | intent | agent_id | 状态 |
|---|---|---|---|
| CT | `solve_problem` | `SOLVER_CT_V1` | selected / Xingchen 或 Mock |
| CT | `check_user_solution` | `CHECK_01_ANSWER_REVIEW_V1` → `SOLVER_CT_V1` | planned → local_degraded |
| CT、AE、DE | 学习类意图 | `LEARN_01_KNOWLEDGE_QA_V1` → `LEARN_01_LOCAL_RETRIEVAL_V1` | planned → local_degraded |
| AE、DE | `solve_problem` | `UNRESOLVED` | unresolved，不使用 CT Solver |
| 其他组合 | `ROUTER_01_FALLBACK_V1` 或 `UNRESOLVED` | cloud_fallback / unresolved |

路由定义在 `agent_configs/registry.yaml`。路由场景、来源、置信度、目标 Agent、降级关系和原始 Agent 写入现有任务输入、结果与事件 JSON，不新增数据库迁移。路由置信度只表示路由判断，不表示答案正确率。

## 快速开始

### 配置并验证星辰同步调用

不要把 Key 或 Secret 发到聊天中。先复制配置文件，再仅在当前 worktree 的 `.env` 中填入新轮换的凭据：

```powershell
Copy-Item .env.example .env
notepad .env
```

至少设置：

```env
XINGCHEN_ENABLED=true
XINGCHEN_API_KEY=<API_KEY>
XINGCHEN_API_SECRET=<API_SECRET>
XINGCHEN_SOLVER_CT_FLOW_ID=<FLOW_ID>
# 其余计划工作流按需配置；空值不会阻止服务启动
# XINGCHEN_KNOWLEDGE_QA_FLOW_ID=<FLOW_ID>
# XINGCHEN_ANSWER_REVIEW_FLOW_ID=<FLOW_ID>
# XINGCHEN_FALLBACK_ROUTER_FLOW_ID=<FLOW_ID>
XINGCHEN_UID=local-demo-user
XINGCHEN_TIMEOUT_SECONDS=300
XINGCHEN_USE_LOCAL_KB_CONTEXT=true
```

先确认真实响应：

```powershell
python scripts/xingchen_smoke_test.py
```

成功后启动本地服务：

```powershell
.\scripts\docker_dev.ps1
```

打开 `http://localhost:8000/debug`，切换文字题或图片题后从同一个按钮提交。页面显示场景、课程、意图、路由来源、目标 Agent、Flow 是否配置、知识库命中、Provider、状态、耗时和完整回答。纯文字 `SOLVER_CT` 题检索最多 2 条方法参考；云端学习问答最多 3 条；图片题跳过本地检索。

`XINGCHEN_TIMEOUT_SECONDS` 默认 300 秒，允许范围为 30～600 秒。超过 600 秒的配置会在服务启动时被拒绝，避免同步请求无限占用本地任务执行器。

图片输入要求：

- 当前只支持单张 PNG/JPG/JPEG，仍不支持 PDF 和多图。
- 星辰工作流开始节点必须存在名称完全一致、类型为 `Image` 的 `USER_INPUT_image` 参数。
- `USER_INPUT_image` 必须连接到 OCR 或图像理解节点；修改工作流后需要重新发布 API，并在绑定页面点击“更新绑定”。
- 图片上传成功后，任务结果的 `structured_result.input_type` 为 `single_image` 或 `text_and_single_image`。

### Windows PowerShell

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Copy-Item .env.example .env
.\scripts\docker_dev.ps1
```

### 手动 API

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e "apps/api[dev]"
Copy-Item .env.example .env
Set-Location apps/api
..\..\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ../..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --reload
```

## API 与调试页

```text
POST /api/v1/sessions
POST /api/v1/tasks
GET  /api/v1/tasks/{task_id}
GET  /api/v1/tasks/{task_id}/events
GET  /api/v1/tasks/{task_id}/stream
POST /api/v1/tasks/{task_id}/cancel
POST /api/v1/tasks/{task_id}/retry
GET  /api/v1/knowledge/sources
POST /api/v1/knowledge/search
POST /api/v1/knowledge/evaluate-query
POST /api/v1/knowledge/rag-search
GET  /api/v1/knowledge/health
GET  /api/v1/knowledge/images/{course_id}/{relative_path}
GET  /api/v1/knowledge/documents/{course_id}/{relative_path}
GET  /api/v1/knowledge/benchmark-summary
POST /api/v1/knowledge/reload
GET  /api/v1/agents/status
GET  /api/v1/agents
GET  /debug
GET  /debug/rag
GET  /debug/agents
GET  /student
```

`http://localhost:8000/debug` 是原生 HTML/CSS/JavaScript 一页式演示界面。文字和图片共用 `POST /api/v1/tasks`，并通过 SSE 展示“正在识别、正在求解、正在整理答案”等步骤；真实星辰、Mock 和本地结果使用不同标识。

`http://localhost:8000/debug/agents` 用于开发态Agent注册、映射预览、Mock和契约检查；`http://localhost:8000/student` 是正式学生端首版，只开放三门课程知识问答与CT文字/单图片解题。

## 检索评测

CT、AE、DE 各有 5 条、合计 15 条真实章节查询草稿。它们仍需人工审核，不称为正式 benchmark。

```powershell
python evaluation/knowledge_retrieval/scripts/validate_cases.py
python evaluation/knowledge_retrieval/scripts/run_retrieval_benchmark.py --mode baseline_lexical_v1
python evaluation/knowledge_retrieval/scripts/run_retrieval_benchmark.py --mode local_lexical_v2
python evaluation/knowledge_retrieval/scripts/compare_runs.py evaluation/knowledge_retrieval/results/baseline_lexical_v1.json evaluation/knowledge_retrieval/results/local_lexical_v2.json
```

真实对比见 `docs/reports/retrieval_baseline_comparison.md`。

## 质量检查

```powershell
ruff check .
mypy apps/api/app
pytest
python evaluation/knowledge_retrieval/scripts/validate_cases.py
python evaluation/knowledge_retrieval/scripts/run_retrieval_benchmark.py
python scripts/export_openapi.py
python scripts/check_sensitive_files.py
docker compose config
git diff --check
```

## 架构与阶段报告

- 阶段范围：`docs/architecture/00_stage_0_1_scope.md`
- 当前总体架构基线：`docs/architecture/02_xinzhi_multi_agent_platform_plan_v1.0.md`
- 阶段 1.6 初始评估：`docs/reviews/stage_1_6_initial_assessment.md`
- 阶段 1.6 最终审查：`docs/reviews/stage_1_6_final_review.md`

用户所述“最终完整总体架构原文”没有包含在本轮附件中，因此仓库保留现有架构内容并明确缺口，没有缩写或虚构缺失正文。

## 下一阶段

1. 人工审核 15 条检索案例、3 条 OCR 清洗草稿和 AE 两条未召回案例。
2. 基于已跑通的文本链路增加单张图片调用。
3. 依据人工审核后的评测集继续优化轻量词项/混合检索，保持 `KnowledgeHit` 与 `RetrievalContextPacket` 合同稳定。
4. 将进程内 TaskRunner 和索引按规模需求迁移为独立 Worker/检索服务，不改变统一任务入口。
