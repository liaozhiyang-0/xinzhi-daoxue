# “揭榜挂帅”项目阶段一现状审计

审计日期：2026-08-03
审计范围：当前工作树的 FastAPI、任务执行、CoursePack、AgentRegistry、Provider、RAG、多模态解析、学习闭环、评测与前端入口。
审计原则：只记录仓库中可复核的实现和测试；Mock、离线评测和待运行案例不代表真实用户效果。

## 1. 项目当前定位

当前仓库已经不是“多 Agent 原型”，而是一个以 `ACADEMIC_PROBLEM_SOLVER` 为统一专业求解入口、以 `TaskRunner` 为执行中枢、以 CoursePack 和本地 RAG 为领域扩展层的电子信息课程群教学平台。CT 的 `SOLVER_CT_V1` 保持为冻结云端基线和回退路径，不能作为本轮改造对象。

公开信息只足以确认题号 `XH-202620` 和“面向一流学科建设的学科垂类大模型与创新应用开发”这一题目方向；附件中要求阅读的原始赛题 PDF 未在当前工作区、`.local_inputs/` 或桌面按给定路径找到，因此本审计不补造赛题正文、指标或验收数据。

## 2. 已有能力盘点

| 领域 | 已发现的实现 | 可复核入口 | 阶段判断 |
|---|---|---|---|
| API 与任务 | FastAPI、SQLAlchemy、Alembic、HTTP 202、TaskRouter、TaskExecutor、TaskRunner、SSE 事件与重连 | `apps/api/app/main.py`、`apps/api/app/api/v1/tasks.py`、`apps/api/app/services/task_runner.py` | 已形成统一任务链 |
| Agent 与课程 | `AgentRegistry`、`TaskRouter`、`ACADEMIC_PROBLEM_SOLVER`、CT/AE/DE/SS 等 CoursePack | `agent_configs/registry.yaml`、`agent_configs/course_packs/`、`apps/api/app/orchestrator/` | 可扩展骨架已具备 |
| Provider | 本地模型 Provider、统一 ModelService、开发 Mock、受控星辰回退 | `apps/api/app/providers/`、`apps/api/app/services/model_service.py` | 真实凭据仍由环境变量提供 |
| RAG | BM25/dense/visual/Qdrant/RRF/reranker 适配、检索上下文、引用校验、健康检查 | `apps/api/app/services/rag_retrieval.py`、`rag_index.py`、`knowledge_index.py`、`apps/api/app/api/v1/knowledge.py` | 已具备检索链，但教师上传资料尚未成为正式课程资产 |
| 多模态 | 图片批处理、PDF 页面解析、DOCX 段落解析、附件边界、OCR 缺失页状态 | `apps/api/app/multimodal/`、`apps/api/app/services/document_ingestion.py` | 文档解析已落库，OCR/复杂表格仍有边界 |
| 教学闭环 | `direct_answer`、`guided_learning`、`check_my_work`，学生尝试版本、验证报告、提示、反馈采纳、mastery 证据、重测计划 | `apps/api/app/contracts/learning.py`、`learning_loop.py`、`learning_outcome.py` | P1/P2/P3 已有基础，需统一演示和管理视图 |
| 证据与可观测性 | citations、evidence packet、trace、运行指标、人工复核标识 | `apps/api/app/contracts/agent.py`、`runtime.py`、`task_presentation.py` | 结果治理边界较清晰 |
| 评测 | YAML/JSON 案例、离线 runner、课程/边界/教学闭环测试、真实数据集目录 | `evaluation/`、`apps/api/tests/`、`scripts/run_evaluation.py` | 结构完整；真实用户试用数据仍为空缺 |
| 前端 | `/student`、`/workspace`、`/demo`、`/debug`、管理员页面与浏览器冒烟脚本 | `apps/api/app/static/`、`scripts/*browser*` | 已有入口；教师课程资产管理尚未闭合 |

## 3. 对七个评分维度的当前判断

| 评分维度 | 当前判断 | 主要证据 | 主要缺口 |
|---|---|---|---|
| 产品完成度 | 中上 | 任务、教学状态、证据和管理基础均存在 | 上传资料、版本、发布、课程索引与教师端未形成一条可演示链 |
| 创意实用度 | 中上 | 从解题扩展到提示、首错定位、重测和教师复核 | 还需要围绕 CT/AE 旗舰场景固化 3 个可复现案例 |
| 技术实现度 | 中上 | 统一 TaskRunner、CoursePack、RAG、工具验证、SSE | 文档结构化解析、OCR 置信度、上传资料入索引需增强 |
| 技术先进性 | 有基础 | 多模态 RAG、RRF、reranker、工具验证、LangGraph 边界 | 知识图谱/先修推理、可解释验证链尚未形成稳定产品能力 |
| 内容质量度 | 中等偏上 | 课程 YAML、技能、错误池、引用和证据包 | 课程资料质量问题仍有人工复核队列，题目/章节/页面级引用需继续补齐 |
| 商业化潜力 | 中等 | Docker、私有化配置、权限与管理基础存在 | 学校部署方案、课程复制流程、授权/删除/导出说明未打包为提交材料 |
| 用户认可度 | 未充分证明 | 有离线评测和 UI 冒烟/回归测试 | 没有可核验的真实试用记录、满意度和任务完成数据，不能宣称用户效果 |

## 4. 强项、短板、阻塞项和证据缺口

### 强项

- 已有唯一专业求解入口和统一 Provider 链，新增课程不需要复制第二套 Solver。
- 任务创建和 Provider 执行分离，保留取消、重试、SSE 顺序、断线重连和恢复机制。
- 结果已能携带证据、引用、trace、指标和人工复核状态，符合教学产品的可解释边界。
- 学生尝试、反馈采纳、mastery 与重测已经有持久化设计，具备形成学习闭环的条件。

### 短板

- `FileModel`/`DocumentChunkModel` 已能解析并保存上传文档，但缺少课程资产身份、版本、发布状态和教师可管理视图。
- PDF 空白页目前只会标记 OCR 需要；DOCX 主要抽取段落，表格、公式、图片题关联仍需结构化增强。
- 现有演示材料中包含历史真实调用描述或“待运行”案例，必须与 Mock/真实结果严格分开，不能直接作为赛事证明。
- RAG 和学习指标有工程级输出，但尚未形成至少 30 条可复现、带 provenance 的赛事评测样例报告。

### 当前阻塞项

- 原始赛题 PDF 不在指定路径，无法对具体赛题验收条款、隐私/授权条款和提交格式做逐条核验。
- 未提供真实教师资料授权记录、真实用户试用记录和人工评分表，不能计算真实用户认可度或准确率。
- Docker 是否可用尚未在本轮审计中执行验证，必须在阶段验收时单独报告。

### 证据缺口

- 教师上传资料 → 版本化课程资产 → 发布 → 可检索证据的闭环证据。
- PDF/DOCX 多模态解析的页面、章节、题号和图片关联样本。
- 三个旗舰演示案例的完整 task/event/evidence/trace/人工复核包。
- 用户反馈字段、管理统计和脱敏试用记录。

## 5. P0/P1/P2/P3 实施计划

| 优先级 | 范围 | 验收产物 |
|---|---|---|
| P0 | CT/AE 旗舰教学闭环：教师资料资产化、版本与发布边界、证据引用、学生文本/单图提交、工具验证、首错定位、人工初审、学习状态与重测、3 个 Demo | 可离线复现的端到端案例；每个结果标识 AI 生成/人工复核边界；不修改 `SOLVER_CT_V1` |
| P1 | PDF/DOCX/图片结构化质量、OCR 置信度、章节/题号/图片关联、跨课程污染检测、证据冲突提示 | 解析质量报告和至少 30 条可复现评测案例 |
| P2 | 用户反馈接口、管理统计、Base/Base+RAG/Base+RAG+Tools/Workflow 消融报告、知识图谱或先修关系 | 脱敏反馈格式、统计 API、消融报告；无真实数据时明确“待填” |
| P3 | 私有化部署、学校推广、课程复制/新增指南、竞赛材料目录和 3 分钟 Demo 脚本 | `submission/contest_package/` 与 Docker/部署验收记录 |

本轮先落地 P0 的第一块：课程资料资产的身份、版本和人工发布门槛。它复用现有上传、解析和 `DocumentChunkModel`，不新建 Provider，不调用 `SOLVER_CT_V1`，也不把未完成向量索引标记为已完成。

## 6. 阶段一结论

项目具备面向电子信息学科智能教学与科研协同平台的工程基础，当前最重要的不是继续增加 Agent 数量，而是把已有能力收敛为可审计、可演示、可复现的 CT/AE 教学闭环。P0 的第一项工作应优先补齐“课程资料资产生命周期”，再以该资产作为 RAG 证据入口串起三类演示案例。
