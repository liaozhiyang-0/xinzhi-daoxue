# 芯智导学：电子信息课程群多智能体平台

芯智导学当前是一个本地可运行的多智能体教学平台。阶段 2.1 已打通 `SOLVER_CT_V1` 到讯飞星辰工作流 API 的同步文字与单图片调用，并提供一页式演示界面。

## 当前技术栈

```text
API 与任务编排：Python 3.11+ / FastAPI / 进程内非阻塞 TaskRunner
数据库：PostgreSQL（测试使用 SQLite）
缓存：Redis
文件存储：MinIO（开发环境允许本地回退）
迁移：SQLAlchemy 2 / Alembic
调试界面：FastAPI 静态 HTML / CSS / JavaScript
部署：Docker Compose
检索：进程内 local_lexical_v2 词项检索
```

早期 Spring Boot、MySQL、Vue3 和 MaaS 微调方案已经移除。仓库只保留当前 FastAPI 多智能体平台、检索评测、运行文档与本地课程资料入口。

## 已完成阶段

- 阶段 0：冻结 `SOLVER_CT_V1` 基线、节点清单、发布检查和回归评测结构。
- 阶段 1：建立 FastAPI、统一 Agent 合同、Mock Provider、数据库、文件存储和 Docker Compose。
- 阶段 1.5：实现 HTTP 202、TaskRunner、递增事件 sequence、SSE 重连、取消、重试和本地调试页。
- 阶段 1.6：增加配置驱动的 AgentRegistry/TaskRouter、路由持久化、三课程检索元数据、v1/v2 评测闭环、RetrievalContextPacket 和 `LEARN_01_KNOWLEDGE_QA_V1`。
- 阶段 2.1：固化 `SOLVER_CT_V1` 的讯飞星辰 `stream=false` 文字/单图片调用、统一回答字段，并将 `/debug` 更新为一页式演示界面。

## 当前能力边界

- CT `solve_problem` 路由到 `SOLVER_CT_V1`；`XINGCHEN_ENABLED=true` 且配置完整时调用真实星辰，否则在未启用时使用明确标识的 Mock。
- 星辰上游当前支持同步文字和单图片调用，不支持多图片、PDF 或上游流式调用。
- CT/AE/DE 的 `general_qa` 与 `explain_concept` 路由到 `LEARN_01_KNOWLEDGE_QA_V1`。
- `LEARN_01` 当前为 `retrieval_only`：整理命中章节、摘要、建议阅读与 `kb://` 来源，不伪装成完整智能问答或星辰模型正式答案。
- AE/DE 的 `solve_problem` 明确返回 `unsupported`，不会回退到电路理论解题 Agent。

## 本地知识库

本地只读输入为：

```text
电路理论/  -> CT
模电/      -> AE
数电/      -> DE
```

当前索引只读取 UTF-8 Markdown，不解析 PDF、不读取图片像素、不解压 ZIP。原始教材目录被 Git 与 Docker build context 排除，不随 PR 提交。

`local_lexical_v2` 支持 Unicode/大小写归一、课程同义词、精确短语、标题/章节/文件名加权、单字与短片段降权、相邻重复片段去重、单文档数量限制、来源多样性、最低分阈值、低置信度和无结果提示。这仍是词项检索，不是 semantic、Embedding 或 vector 检索。

元数据覆盖层位于 `knowledge_config/`；自动发现的 OCR 清洗项保持 `review_status: draft`，运行时只应用人工批准项，不修改原始 Markdown。

## 任务路由

| course_id | intent | agent_id | 状态 |
|---|---|---|---|
| CT | `solve_problem` | `SOLVER_CT_V1` | selected / Xingchen 或 Mock |
| CT、AE、DE | `general_qa`、`explain_concept` | `LEARN_01_KNOWLEDGE_QA_V1` | selected / retrieval_only |
| AE、DE | `solve_problem` | `UNSUPPORTED` | unsupported |
| 其他组合 | `UNSUPPORTED` | `UNSUPPORTED` | unsupported |

路由定义在 `agent_configs/registry.yaml`。任务表保存 `agent_id`、`route_status`、`route_reason`，TaskRunner 使用已保存的 `agent_id`，不自行硬编码 Agent。

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

打开 `http://localhost:8000/debug`，切换文字题或图片题后从同一个按钮提交。页面显示图片预览、当前步骤、耗时、Provider、完整解答、结构化字段、风险和 `kb://` 来源。纯文字 `SOLVER_CT` 题默认检索最多 3 条方法参考，参考正文合计不超过 2000 字；图片题完全跳过本地检索，直接上传并调用星辰工作流。检索失败不会阻塞文字求解。

`XINGCHEN_TIMEOUT_SECONDS` 默认 300 秒，允许范围为 30～600 秒。超过 600 秒的配置会在服务启动时被拒绝，避免同步请求无限占用本地任务执行器。

图片输入要求：

- 当前只支持单张 PNG/JPG/JPEG，仍不支持 PDF 和多图。
- 星辰工作流开始节点必须存在名称完全一致、类型为 `Image` 的 `USER_INPUT_image` 参数。
- `USER_INPUT_image` 必须连接到 OCR 或图像理解节点；修改工作流后需要重新发布 API，并在绑定页面点击“更新绑定”。
- 图片上传成功后，任务结果的 `structured_result.input_type` 为 `image`。

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
GET  /api/v1/knowledge/benchmark-summary
POST /api/v1/knowledge/reload
GET  /debug
```

`http://localhost:8000/debug` 是原生 HTML/CSS/JavaScript 一页式演示界面。文字和图片共用 `POST /api/v1/tasks`，并通过 SSE 展示“正在识别、正在求解、正在整理答案”等步骤；真实星辰、Mock 和本地结果使用不同标识。

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
