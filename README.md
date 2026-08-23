# 芯智导学：电子信息课程群多智能体平台

芯智导学当前是一个本地可运行的电子信息课程群多智能体编排中枢。本地负责协议、路由、状态、RAG 与专业工具；讯飞 Spark-X2 与阿里云百炼千问提供统一文本/多模态模型服务；既有本地 Runtime工作流继续作为已验证能力、基线与故障回退。所有扩展复用现有 FastAPI、TaskRouter、TaskExecutionCoordinator、durable Agent Runtime、数据库、SSE 与上传链路。

需要继续修改代码时，先阅读 [代码级开发手册](docs/developer_code_navigation.md)。它按 API、任务执行、路由、Solver、RAG、模型、学习闭环、数据库、前端、评测和测试梳理了真实调用链，并提供常见微调任务的入口索引。逐个文件的职责见 [仓库逐文件目录](docs/repository_file_catalog.md)。

专业求解入口现统一为 `ACADEMIC_PROBLEM_SOLVER`：Supervisor 先识别任务族与课程，再由同一个 AcademicProblemSolverGraph 加载 CT/AE/DE/SS CoursePack、共享 CapabilityPack 与确定性工具。`SOLVER_CT_V1` 仅作为冻结历史基线只读保留，不参与当前本地 Runtime 路由。详细设计见 `docs/universal_academic_solver.md` 与 `docs/architecture_consolidation_audit.md`。

教学闭环在同一任务链上支持 `direct_answer`、`guided_learning` 和 `check_my_work`：后台复用 `SolutionPacketV1`，以有限规则生成 `VerificationReportV1`、H0—H2 提示和单个理解检查，并由后端强制过滤学习模式的完整答案；`review` 仍为 `foundation_only`。刷新可恢复当前提示与问题，主动切换完整解答不会重复运行 Solver。它不是全题型首错系统，复杂推导明确进入 `manual_review`，也不会自动更新 mastery。详见 [第一阶段基础能力](docs/architecture/teaching_foundation_phase1.md) 与 [第二阶段有限诊断和分级辅导](docs/architecture/teaching_loop_phase2.md)。

## 组员统一启动（Windows）

只需要安装 **Python 3.11-3.13、Git 和 Docker Desktop**。克隆仓库、启动 Docker Desktop 后，在仓库根目录执行：

```powershell
.\xzd.cmd doctor
.\xzd.cmd start
```

如果遇到“数据库自动关闭”、旧进程残留、虚拟环境无法启动或 API 端口冲突，先运行：

```powershell
.\xzd.cmd doctor
.\xzd.cmd repair -Port 8031
```

`doctor` 只读检查 Python 虚拟环境、Docker、固定命名的 PostgreSQL/Redis/MinIO/Qdrant、端口占用和 API 状态；`repair` 只启动本项目自有容器、执行增量迁移并恢复单实例 API。它不会执行 `docker compose down`、删除数据卷、接管未知端口进程或打印密钥。若 `.venv` 损坏，旧环境会先保存在 `.codex-tmp/venv-backups/`，再尝试重建。

日常使用无需重复输入命令：双击仓库根目录的 `打开芯智导学.cmd` 即可。它会复用统一启动器，在服务就绪后自动打开 `http://127.0.0.1:8000/workspace`；如果服务已经运行，则只打开工作台，不会再启动一套重复进程。这个入口默认不执行本地 Runtime外部服务 Preflight。

`start` 会自动创建 `.venv` 和本机 `.env`、安装缺少的依赖、启动 PostgreSQL/Redis/MinIO/Qdrant、执行增量迁移并启动 Web。它不会覆盖已有 `.env`，也不会打印 Key 或 Secret。

所有新任务统一通过 durable Agent Runtime 执行。active 模式的生产控制面由
`Unified Ingress → GoalContract → Planner → CanonicalPlan → Runtime` 负责；旧
`IntentPlanCompiler`、Overall Router 和 `legacy-runtime:*` 只保留 shadow/旧 checkpoint
兼容边界，active 任务缺少有效 CanonicalPlan 时失败关闭，不回退到旧 workflow。

业务请求统一通过本地 Runtime 执行：本地 RAG、课程知识、学科求解、备课、作业复核和科研能力共享同一套可观测执行边界。请求中的历史 `allow_cloud` 字段会在入口被丢弃，不会触发远程工作流。

PostgreSQL、Redis、MinIO 和 Qdrant 使用固定命名数据卷；重启 Docker、更新代码或重新克隆仓库不会重新创建数据库。`stop` 只停止容器，不删除数据。启动成功后打开：

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
.\xzd.cmd preflight                      # 会议前检查，不消耗外部服务额度
.\xzd.cmd index -Course CT -TextOnly     # 为本机 CT 教材构建文本索引
.\xzd.cmd index -Course SS               # 增量构建 SS 文本与图片索引
.\xzd.cmd start -Reload                  # 开发热重载
```

模型凭据只填写在各自机器的 `.env` 中；Git 只保存空值模板 [.env.example](.env.example)。本地教材、向量索引、上传文件和模型缓存均被 Git 忽略。完整组员说明见 [团队快速使用指南](docs/deployment/team_quick_start.md)；服务器说明见 [生产服务器部署](docs/deployment/server_production.md)。

## 当前技术栈

```text
API 与任务编排：Python 3.11+ / FastAPI / 非阻塞 TaskExecutionCoordinator / durable Agent Runtime
数据库：PostgreSQL（测试使用 SQLite）
缓存：Redis
文件存储：MinIO（开发环境允许本地回退）
迁移：SQLAlchemy 2 / Alembic
调试界面：FastAPI 静态 HTML / CSS / JavaScript
部署：Docker Compose（本地使用 `docker-compose.yml`，服务器使用 `docker-compose.server.yml` 覆盖）
检索：BGE dense + BM25 sparse + SigLIP2 visual + Qdrant + RRF + BGE reranker
```

## Phase N v2：当前生产控制面

```text
React / chat / tasks
  → UnifiedRequestPreparationService
  → GoalContract
  → TaskRouter deterministic preflight
  → PlannerService(active)
  → Capability + Skill binding
  → CanonicalPlan
  → RuntimeTaskEngine / PlanExecutor
  → RAG / Tool / Model / Verification
  → Governance / Result / SSE / React
```

`TaskRouter` 只负责输入和可用性预检；`scenario_catalog` 只提供案例 metadata、约束和证据策略。六案例仍通过统一展示合同渲染，不新增固定 Agent 页面。收口证据见
[Phase N 控制面收口](docs/architecture/phase_n_control_plane_closeout.md) 和
[N8 takeover 评估](docs/architecture/phase_n8_takeover_evaluation.md)。

早期 Spring Boot、MySQL、Vue3 和 MaaS 微调方案已经移除。仓库只保留当前 FastAPI 多智能体平台、检索评测、运行文档与本地课程资料入口。

## 数学公式渲染

任务结果保留兼容 `answer`/`answer_text`，并可携带结构化 `math_content`。后端在最终输出阶段统一规范化 `$...$` 与 `$$...$$`，优先使用结构化公式字段；前端复用唯一的本地 KaTeX 渲染链，非法公式会降级显示原始 LaTeX，代码、URL、日期和 JSON 不参与转换。协议、安全边界、扩展方式与验收样本见 [数学公式渲染链路](docs/math_rendering_pipeline.md)。

## 渐进式本地编排

```text
Web -> FastAPI -> XZD_SUPERVISOR -> TaskExecutionCoordinator -> RuntimeTaskEngine
                              |-> Model Registry -> Model Service
                              |                    |-> Spark-X2
                              |                    `-> Qwen text/vision
                              |-> local RAG
                              |-> calculator / SymPy / unit checker
                              `-> local Runtime handlers
```

新版 `POST /api/v1/chat` 会创建原有非阻塞任务，不会建立第二套任务队列。`GET /api/v1/capabilities` 与 `GET /api/v1/workflows` 可查看本地 Runtime 状态；开发态可通过 `GET /api/v1/debug/traces/{trace_id}` 查看脱敏节点摘要。

## 国产模型配置

首次配置可复制模板；Windows PowerShell 使用：

```powershell
Copy-Item .env.example .env
```

Linux/macOS 使用：

```bash
cp .env.example .env
```

基础调用只需在本机 `.env` 填写两个字段，不能提交该文件：

```env
IFLYTEK_SPARK_API_KEY=
DASHSCOPE_API_KEY=
```

`IFLYTEK_SPARK_API_KEY` 填写讯飞 Spark-X2 HTTP APIPassword（或控制台要求的 AK:SK 形式）；`DASHSCOPE_API_KEY` 填写阿里云百炼 API Key。使用百炼业务空间专属地址时才需要额外设置 `DASHSCOPE_WORKSPACE_ID`，并可显式覆盖 `DASHSCOPE_BASE_URL`。

模型角色：`spark-x` 负责复杂推理与 RAG 答案生成；`qwen3.7-plus` 负责复杂图片/电路图；`qwen3.6-flash` 负责快速视觉任务；`qwen3.5-flash` 负责分类、改写与结构化任务。配置与真实连通性检查：

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test_models.py --config-only
.\.venv\Scripts\python.exe scripts\smoke_test_models.py --provider iflytek
.\.venv\Scripts\python.exe scripts\smoke_test_models.py --provider dashscope
.\.venv\Scripts\python.exe scripts\smoke_test_models.py --vision .\path\to\test.png
```

服务启动后也可访问 `GET /api/v1/models` 和 `GET /api/v1/models/health?live=false`；只有显式使用 `live=true` 才产生极短真实调用。Key 为空不会阻止 FastAPI 启动，本地 RAG 与本地 Runtime 仍保持独立运行。401 应检查 Key/地域，404 应检查模型名、Base URL 与业务空间；图片超限和模型超时会返回统一、脱敏错误。完整说明见 [模型 API 配置](docs/model_api_configuration.md)。

模型层已注册 9 个从属内部 Agent，覆盖课程/意图分类、RAG 查询改写、电路规划与图片提取、备课、作业初审、学术写作和数据分析。它们复用统一 ModelService，并保持 `subordinate_only`，不会建立第二套顶层任务路由。已通过专项测试的备课、作业初审、学术写作和数据分析 Agent 已接入原有 `POST /api/v1/tasks`；备课复用同一次任务的本地 RAG 上下文。`/student` 与 `/workspace` 采用单输入自动路由，只展示能力和知识增强状态，不显示底层 Provider 或原始 Agent ID。`GET /api/v1/internal-agents` 只查看本地注册和配置状态；真实批量评测使用 `scripts/evaluate_model_agents.py`，先以 `--dry-run` 检查，再用 `--agent` 或 `--case` 小批量执行以控制 Token。

开发态真实 Embedding 不可用时可显式启用旧哈希兼容层；生产环境不会静默回退。

## 已完成阶段

- 阶段 0：冻结 `SOLVER_CT_V1` 基线、节点清单、发布检查和回归评测结构。
- 阶段 1：建立 FastAPI、统一 Agent 合同、Mock Provider、数据库、文件存储和 Docker Compose。
- 阶段 1.5：实现 HTTP 202、非阻塞任务协调、递增事件 sequence、SSE 重连、取消、重试和本地调试页。
- 阶段 1.6：增加配置驱动的 AgentRegistry/TaskRouter、路由持久化、三课程检索元数据、v1/v2 评测闭环、RetrievalContextPacket 和 `LEARN_01_KNOWLEDGE_QA_V1`。
- 阶段 2.1：固化 `SOLVER_CT_V1` 的讯飞本地 Runtime `stream=false` 文字/单图片调用、统一回答字段，并将 `/debug` 更新为一页式演示界面。
- 阶段 2.2：统一注册 dispatch、learning、teaching、research、infrastructure 场景；所有本地 Runtime Agent 复用一个 Provider 和注册表输入映射，计划态工作流不阻塞启动。

## 当前能力边界

- CT `solve_problem` 路由到 `SOLVER_CT_V1` 的本地 Runtime；只有显式选择 Mock Provider 的开发配置才会产生 Mock 结果。
- 本地 Runtime上游当前支持同步文字和单图片调用，不支持多图片、PDF 或上游流式调用。
- CT 的 `check_user_solution` 和 `verify_answer` 直接复用冻结的 `SOLVER_CT_V1`；已移除从未发布的中间计划态 Agent，避免无效降级和额外配置。
- CT/AE/DE/SS/DSP/COMM 的学习类意图统一进入带本地 RAG 的 `LEARN_01_KNOWLEDGE_QA_V1`；本地检索失败时返回明确的降级状态，不伪装成已完成答案。
- 模糊、UNKNOWN、低置信或未匹配输入仅允许进入一次受验证的本地调度兜底；兜底不可用时返回 `unresolved`，不会自动送入 `SOLVER_CT_V1`。
- 本地 `ACADEMIC_PROBLEM_SOLVER` 支持有序多图：简单图片批次先拼接为一张组合图，复杂批次逐图识别、汇总后再解题；PDF、空输入及 Agent 未声明的输入组合仍返回明确错误。

## 本地知识库

本地只读输入为：

```text
电路理论/  -> CT
模电/      -> AE
数电/      -> DE
信号与系统版本一/ -> SS
数字信号处理/     -> DSP
通信原理/         -> COMM
```

当前文本索引读取 UTF-8 Markdown；图片索引读取 JPG/JPEG/PNG/WEBP 原始像素。PDF、DOCX 和 ZIP 只登记元数据，不直接解析。原始教材、模型缓存和 Qdrant 数据目录均不提交 Git。

正式 RAG 使用真实 BGE 文本 Embedding、SigLIP2 视觉 Embedding、Qdrant 命名向量、原有 BM25 分支、RRF 融合和可配置 BGE reranker。生产链路不再包含哈希或随机伪 Embedding；模型失败会明确进入 degraded/failed。完整配置与实测结果见 `docs/knowledge/multimodal_rag_integration_guide.md` 和 `docs/reviews/multimodal_rag_implementation_report.md`。

元数据覆盖层位于 `knowledge_config/`；自动发现的 OCR 清洗项保持 `review_status: draft`，运行时只应用人工批准项，不修改原始 Markdown。

## 任务路由

| course_id | intent | agent_id | 状态 |
|---|---|---|---|
| CT | `solve_problem` | `SOLVER_CT_V1` | selected / local Runtime 或 Mock |
| CT | `check_user_solution`、`verify_answer` | `SOLVER_CT_V1` | selected / local Runtime 或明确 Mock |
| CT、AE、DE、SS、DSP、COMM | 学习类意图 | `LEARN_01_KNOWLEDGE_QA_V1` | selected / local RAG + Runtime |
| AE、DE | `solve_problem` | `UNRESOLVED` | unresolved，不使用 CT Solver |
| 其他组合 | `ROUTER_01_FALLBACK_V1` 或 `UNRESOLVED` | local_fallback / unresolved |

路由定义在 `agent_configs/registry.yaml`。路由场景、来源、置信度、目标 Agent、降级关系和原始 Agent 写入现有任务输入、结果与事件 JSON，不新增数据库迁移。路由置信度只表示路由判断，不表示答案正确率。

## 快速开始

### 启动本地服务\n\n```powershell\n.\\scripts\\docker_dev.ps1\n```\n\n### Windows PowerShell

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
GET  /api/v1/knowledge/images/{course_id}/{relative_path}  # 认证开启时需登录
GET  /api/v1/knowledge/documents/{course_id}/{relative_path}  # 认证开启时需登录
GET  /api/v1/knowledge/benchmark-summary
POST /api/v1/knowledge/reload
GET  /api/v1/agents/status
GET  /api/v1/agents
POST /api/v1/chat
POST /api/v1/chat/stream
GET  /api/v1/chat/{task_id}
GET  /api/v1/capabilities
GET  /api/v1/workflows
GET  /api/v1/internal-agents
GET  /api/v1/debug/traces/{trace_id}
GET  /api/v1/observability/summary
GET  /api/v1/observability/metrics
GET  /metrics
GET  /debug
GET  /debug/rag
GET  /debug/agents
GET  /student
```

`/api/v1/observability/summary`、`/api/v1/observability/metrics` 和 `/metrics` 属于运维观测面；认证开启时需要管理员身份。生产环境还应在反向代理或 Prometheus 抓取配置中使用最小权限凭据。

`http://localhost:8000/debug` 是原生 HTML/CSS/JavaScript 一页式演示界面。文字和图片共用 `POST /api/v1/tasks`，并通过 SSE 展示“正在识别、正在求解、正在整理答案”等步骤；真实本地 Runtime、Mock 和本地结果使用不同标识。

认证开启时，`/debug`、`/debug/rag`、`/debug/agents`、`/debug/execution`、`/system`、`/demo` 及题库调试图片均仅限管理员访问；`/student` 和 `/workspace` 为学生端入口。

`http://localhost:8000/debug/agents` 用于开发态Agent注册、映射预览、Mock和契约检查；`http://localhost:8000/workspace`（`/student` 同入口）是正式学生端，支持自然语言自动路由和本地学术求解器多图输入。

## 检索评测

CT、AE、DE 各有 5 条、合计 15 条真实章节查询草稿。它们仍需人工审核，不称为正式 benchmark。

```powershell
python evaluation/knowledge_retrieval/scripts/validate_cases.py
python evaluation/knowledge_retrieval/scripts/run_retrieval_benchmark.py --mode baseline_lexical_v1
python evaluation/knowledge_retrieval/scripts/run_retrieval_benchmark.py --mode local_lexical_v2
python evaluation/knowledge_retrieval/scripts/compare_runs.py evaluation/knowledge_retrieval/results/baseline_lexical_v1.json evaluation/knowledge_retrieval/results/local_lexical_v2.json
```

真实对比见 `docs/reports/retrieval_baseline_comparison.md`。

多学科正式执行链评测使用同一 Runtime 执行链，默认不发送付费请求：

```powershell
.\.venv\Scripts\python.exe scripts\run_evaluation.py --validate-only
.\.venv\Scripts\python.exe scripts\run_evaluation.py --offline
.\.venv\Scripts\python.exe scripts\run_evaluation.py --case-id CT_KCL_001 --offline
.\.venv\Scripts\python.exe scripts\run_evaluation.py --live --confirm-paid --course CT --max-cases 3
```

报告输出到 `evaluation/reports/latest.json` 和 `latest.md`。评测只读 API 默认由
`ENABLE_EVALUATION_API=false` 关闭，且不提供 HTTP 付费执行入口。

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

## 当前架构与历史隔离

- 当前本地编排架构：`docs/local_orchestration_architecture.md`
- 迁移审计：`docs/architecture_migration_audit.md`
- Agent 注册表：`docs/agent_registry.md`
- 模型 API 配置：`docs/model_api_configuration.md`
- 历史阶段快照：`archive_legacy/docs/`，不参与运行、测试或 Docker 构建。

## 下一阶段

1. 人工审核 15 条检索案例、3 条 OCR 清洗草稿和 AE 两条未召回案例。
2. 使用真实课程图片人工验收千问视觉回答质量与成本。
3. 依据人工审核后的评测集继续优化轻量词项/混合检索，保持 `KnowledgeHit` 与 `RetrievalContextPacket` 合同稳定。
4. 按规模需求将现有 coordinator 切换到 Redis Worker，并独立扩展检索服务，不改变统一任务入口。
# Agent Runtime Foundation v1

平台现已在原有 `POST /api/v1/tasks` 单一执行链上支持消息级历史、多轮上下文、
会话标题/搜索/归档、WorkingState、Token 预算、版本化摘要、Redis/内存上下文
缓存和显式长期记忆。自动记忆默认关闭，`SOLVER_CT_V1` 与本地 Runtime默认授权策略未变。

架构与部署说明：

- [Agent Runtime Foundation](docs/architecture/agent_runtime_foundation.md)
- [会话与长期记忆部署指南](docs/deployment/conversation_memory_guide.md)

## 教学闭环第三阶段

Workspace 现可在同一题目下保存不可覆盖的多版本学生尝试，使用本地有限规则记录
反馈采用，形成启发式 MasteryEvidence，更新现有唯一的
LearnerKnowledgeState，并按配置展示 1/7/28 天待复习项。系统不新增模型调用、
后台调度器或主动通知。

- 架构：[教学闭环第三阶段](docs/architecture/teaching_loop_phase3.md)
- 配置：[学习状态配置](docs/deployment/learning_state_configuration.md)
- 审计：[第三阶段实施前审计](docs/audits/teaching_loop_phase3_audit.md)

界面中的“学习进度估计”只是一项基于当前练习记录的辅助估计，不等同于考试成绩、
正式能力评价或真实掌握概率。
