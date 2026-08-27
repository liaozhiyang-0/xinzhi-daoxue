# 仓库逐文件目录（自动生成）

> 本文档只覆盖 `git ls-files --cached --others --exclude-standard` 可见的可发布文件，
> 因而不会读取或列出 `.env`、教材原文、向量索引、上传文件、数据库、模型缓存和测试临时文件。
> 文件职责由路径、模块文档字符串、Markdown 标题和结构化文件顶层字段确定；它是导航清单，不替代源码。

- 可发布文件总数：**1995**
- 活动文件：**1861**
- 历史隔离文件：**134**
- 重新生成：`python scripts/generate_repository_catalog.py`
- 漂移检查：`python scripts/generate_repository_catalog.py --check`

## 顶层范围

| 路径 | 文件数 | 职责 |
|---|---:|---|
| `.dockerignore` | 1 | Docker 构建上下文排除规则。 |
| `.env.example` | 1 | 无密钥的环境变量模板；本机真实值写入被忽略的 `.env`。 |
| `.env.server.example` | 1 | 仓库根文件或项目组成部分。 |
| `.gitattributes` | 1 | Git 文本属性与跨平台换行规则。 |
| `.github` | 2 | GitHub Actions 持续集成。 |
| `.gitignore` | 1 | 本地密钥、教材、索引、缓存、上传物与运行数据排除规则。 |
| `agent_configs` | 2 | Agent 注册表、冻结工作流与课程包配置。 |
| `AGENTS.md` | 1 | 仓库工程、安全、验证和发布约束。 |
| `apps` | 743 | FastAPI 主应用、静态前端和 Worker 边界。 |
| `archive_legacy` | 14 | 退出活动架构的历史资料与代码隔离区。 |
| `ci-artifacts` | 6 | 仓库根文件或项目组成部分。 |
| `config` | 21 | 跨运行环境的基础配置。 |
| `conftest.py` | 1 | 仓库根文件或项目组成部分。 |
| `constraints` | 1 | 仓库根文件或项目组成部分。 |
| `docker-compose.server.yml` | 1 | 仓库根文件或项目组成部分。 |
| `docker-compose.tailscale.yml` | 1 | 仓库根文件或项目组成部分。 |
| `docker-compose.yml` | 1 | PostgreSQL、Redis、MinIO、Qdrant 与 API 的本地编排。 |
| `docs` | 667 | 现行架构、运行、评测、知识库与验收文档。 |
| `evaluation` | 92 | 可复现评测数据集、基线、模式与报告模板。 |
| `infra` | 4 | 仓库根文件或项目组成部分。 |
| `knowledge_config` | 20 | 课程资料元数据、OCR 覆盖和分块策略。 |
| `local_knowledge` | 7 | 可提交的小型示例知识与目录占位；非教材原文。 |
| `pytest.ini` | 1 | 根目录 Pytest 发现与运行配置。 |
| `README.md` | 1 | 项目入口说明、能力边界、配置和启动指引。 |
| `ruff.toml` | 1 | Ruff 静态检查和格式规则。 |
| `scripts` | 100 | 启动、诊断、迁移、索引、评测和发布辅助脚本。 |
| `submission` | 12 | 仓库根文件或项目组成部分。 |
| `tests` | 5 | 仓库级配置和静态边界测试。 |
| `xzd.cmd` | 1 | Windows CMD 统一启动器入口。 |
| `xzd.ps1` | 1 | Windows PowerShell 统一启动器入口。 |
| `xzd.sh` | 1 | Linux/macOS 统一启动器入口。 |
| `关闭芯智导学.cmd` | 1 | 仓库根文件或项目组成部分。 |
| `打开芯智导学.cmd` | 1 | Windows 双击启动并打开学生工作台的便捷入口。 |
| `真实测试题` | 16 | 仓库根文件或项目组成部分。 |
| `真实题库_已整理` | 249 | 仓库根文件或项目组成部分。 |
| `组员反馈` | 16 | 仓库根文件或项目组成部分。 |

## 文件类型统计

| 扩展名 | 数量 |
|---|---:|
| `.py` | 769 |
| `.md` | 756 |
| `.png` | 117 |
| `.jpg` | 79 |
| `.yaml` | 70 |
| `.json` | 57 |
| `.js` | 25 |
| `.woff2` | 20 |
| `[无扩展名]` | 16 |
| `.html` | 13 |
| `.ps1` | 12 |
| `.css` | 9 |
| `.sh` | 8 |
| `.txt` | 7 |
| `.yml` | 7 |
| `.csv` | 5 |
| `.pdf` | 5 |
| `.docx` | 4 |
| `.cmd` | 3 |
| `.example` | 3 |
| `.jsonl` | 3 |
| `.ini` | 2 |
| `.toml` | 2 |
| `.mako` | 1 |
| `.svg` | 1 |
| `.zip` | 1 |

## 逐目录文件清单

### `仓库根目录`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.dockerignore` | 活动 | Docker 构建上下文排除规则。 |
| `.env.example` | 活动 | 无密钥的环境变量模板；本机真实值写入被忽略的 `.env`。 |
| `.env.server.example` | 活动 | 仓库配置、资产或占位文件。 |
| `.gitattributes` | 活动 | Git 文本属性与跨平台换行规则。 |
| `.gitignore` | 活动 | 本地密钥、教材、索引、缓存、上传物与运行数据排除规则。 |
| `AGENTS.md` | 活动 | 仓库工程、安全、验证和发布约束。 |
| `conftest.py` | 活动 | Python 模块；定义 _ci_jpeg_bytes、_ensure_file、clean_checkout_fixtures。 |
| `docker-compose.server.yml` | 活动 | 结构化配置或数据文件（内容需由对应加载器校验）。 |
| `docker-compose.tailscale.yml` | 活动 | 结构化配置或数据文件（内容需由对应加载器校验）。 |
| `docker-compose.yml` | 活动 | PostgreSQL、Redis、MinIO、Qdrant 与 API 的本地编排。 |
| `pytest.ini` | 活动 | 根目录 Pytest 发现与运行配置。 |
| `README.md` | 活动 | 项目入口说明、能力边界、配置和启动指引。 |
| `ruff.toml` | 活动 | Ruff 静态检查和格式规则。 |
| `xzd.cmd` | 活动 | Windows CMD 统一启动器入口。 |
| `xzd.ps1` | 活动 | Windows PowerShell 统一启动器入口。 |
| `xzd.sh` | 活动 | Linux/macOS 统一启动器入口。 |
| `关闭芯智导学.cmd` | 活动 | 跨平台运行脚本：关闭芯智导学。 |
| `打开芯智导学.cmd` | 活动 | Windows 双击启动并打开学生工作台的便捷入口。 |

### `.github/workflows`

| 文件 | 状态 | 功能 |
|---|---|---|
| `backend-ci.yml` | 活动 | 结构化配置或数据；顶层字段：name、True、jobs。 |
| `model-evaluation.yml` | 活动 | 结构化配置或数据；顶层字段：name、True、concurrency、jobs。 |

### `agent_configs`

| 文件 | 状态 | 功能 |
|---|---|---|
| `mock_profiles.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、profiles。 |
| `registry.yaml` | 活动 | 结构化配置或数据；顶层字段：scenes、session_context、agents、routing。 |

### `apps/api`

| 文件 | 状态 | 功能 |
|---|---|---|
| `alembic.ini` | 活动 | 项目、工具或运行时配置。 |
| `Dockerfile` | 活动 | 仓库配置、资产或占位文件。 |
| `pyproject.toml` | 活动 | 项目、工具或运行时配置。 |

### `apps/api/alembic`

| 文件 | 状态 | 功能 |
|---|---|---|
| `env.py` | 活动 | Python 模块；定义 run_migrations_offline、do_run_migrations、run_async_migrations。 |
| `script.py.mako` | 活动 | Alembic 数据库迁移文件模板。 |

### `apps/api/alembic/versions`

| 文件 | 状态 | 功能 |
|---|---|---|
| `20260716_0001_initial_schema.py` | 活动 | 增量数据库迁移：20260716 0001 initial schema。 |
| `20260717_0002_task_lifecycle.py` | 活动 | 增量数据库迁移：20260717 0002 task lifecycle。 |
| `20260717_0003_task_routing.py` | 活动 | 增量数据库迁移：20260717 0003 task routing。 |
| `20260718_0004_student_context.py` | 活动 | 增量数据库迁移：20260718 0004 student context。 |
| `20260722_0005_learning_reliability.py` | 活动 | 增量数据库迁移：20260722 0005 learning reliability。 |
| `20260723_0006_agent_runtime_foundation.py` | 活动 | 增量数据库迁移：20260723 0006 agent runtime foundation。 |
| `20260726_0007_teaching_loop_phase3.py` | 活动 | 增量数据库迁移：20260726 0007 teaching loop phase3。 |
| `20260801_0008_auth_foundation.py` | 活动 | 增量数据库迁移：20260801 0008 auth foundation。 |
| `20260801_0009_management_audit.py` | 活动 | 增量数据库迁移：20260801 0009 management audit。 |
| `20260801_0010_document_ingestion.py` | 活动 | 增量数据库迁移：20260801 0010 document ingestion。 |
| `20260803_0011_course_material_lifecycle.py` | 活动 | 增量数据库迁移：20260803 0011 course material lifecycle。 |
| `20260804_0012_course_material_review.py` | 活动 | 增量数据库迁移：20260804 0012 course material review。 |
| `20260804_0013_task_feedback.py` | 活动 | 增量数据库迁移：20260804 0013 task feedback。 |
| `20260804_0014_system_settings.py` | 活动 | 增量数据库迁移：20260804 0014 system settings。 |
| `20260805_0015_research_evidence.py` | 活动 | 增量数据库迁移：20260805 0015 research evidence。 |
| `20260808_0016_agent_runtime_state.py` | 活动 | 增量数据库迁移：20260808 0016 agent runtime state。 |
| `20260808_0017_agent_runtime_controls.py` | 活动 | 增量数据库迁移：20260808 0017 agent runtime controls。 |
| `20260808_0018_agent_runtime_targets.py` | 活动 | 增量数据库迁移：20260808 0018 agent runtime targets。 |
| `20260808_0019_runtime_execution_safety.py` | 活动 | 增量数据库迁移：20260808 0019 runtime execution safety。 |
| `20260808_0020_runtime_run_lineage.py` | 活动 | 增量数据库迁移：20260808 0020 runtime run lineage。 |
| `20260808_0021_runtime_plan_proposals.py` | 活动 | 增量数据库迁移：20260808 0021 runtime plan proposals。 |
| `20260823_0022_experience_memory.py` | 活动 | 增量数据库迁移：20260823 0022 experience memory。 |

### `apps/api/app`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | 芯智导学 FastAPI application package. |
| `dependencies.py` | 活动 | Python 模块；定义 get_settings_from_app、get_provider、get_knowledge_base、get_rag_retrieval、get_db 等。 |
| `knowledge_catalog.py` | 活动 | Python 配置或执行模块。 |
| `main.py` | 活动 | Python 模块；定义 _create_graph_checkpointer、create_app。 |

### `apps/api/app/agents`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `registry.py` | 活动 | Python 模块；定义 UniqueKeyLoader、_construct_unique_mapping、ProviderDefinition、AgentCapabilities、InputContract 等。 |
| `router.py` | 活动 | Python 模块；定义 _ScoredRoute、TaskRouter。 |

### `apps/api/app/agents/internal`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `contracts.py` | 活动 | Python 模块；定义 CourseClassification、IntentClassification、OverallRouteDecision、AcademicPaperReviewDecision、AcademicPaperReview 等。 |
| `hub.py` | 活动 | Python 模块；定义 InternalAgentDefinition、InternalAgentHub。 |

### `apps/api/app/api`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | HTTP API package. |
| `http_app.py` | 活动 | Python 模块；定义 error_payload、configure_http_app、_register_page_routes、_register_request_middleware、_register_error_handlers。 |

### `apps/api/app/api/v1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Version 1 API routes. |
| `admin.py` | 活动 | Python 模块；定义 _service、_session_read、overview、list_feature_settings、update_feature_setting 等。 |
| `agents.py` | 活动 | Python 模块；定义 AgentDryRunRequest、_lifecycle_status、list_agent_status、list_runtime_readiness、show_agent 等。 |
| `analytics.py` | 活动 | Python 模块；定义 analytics_query、_report、overview、users、sessions 等。 |
| `artifacts.py` | 活动 | Python 模块；定义 get_artifact。 |
| `auth.py` | 活动 | Python 模块；定义 _service、_set_auth_cookies、_clear_auth_cookies、_set_guest_cookie、_session_response 等。 |
| `debug_agents.py` | 活动 | Python 模块；定义 AgentDebugRequest、_ensure_debug、_agent_request、_result_payload、validate_agent 等。 |
| `debug_execution.py` | 活动 | Python 模块；定义 _redact、_redact_dict、_order_runtime_nodes、_read_runtime_handoff、_checkpoint_summaries 等。 |
| `debug_rag.py` | 活动 | Python 模块；定义 DebugRunRequest、CompareRequest、EvalRequest、_default_prewarm_models、PrewarmRequest 等。 |
| `debug_traces.py` | 活动 | Python 模块；定义 get_trace。 |
| `evaluation.py` | 活动 | Python 模块；定义 _require_enabled、list_suites、latest_report、latest_report_summary、model_call_observability。 |
| `feedback.py` | 活动 | Python 模块；定义 _ensure_feedback_enabled、feedback_status、_require_metrics_manager、_bounded_float、_task_snapshot 等。 |
| `files.py` | 活动 | Python 模块；定义 _material_field、upload_file、get_file、get_file_chunks、get_file_content。 |
| `health.py` | 活动 | Python 模块；定义 health。 |
| `internal_agents.py` | 活动 | Python 模块；定义 list_internal_agents。 |
| `knowledge.py` | 活动 | Python 模块；定义 _published_material、_published_material_content、_material_quality_report、_material_requires_review、_require_material_manager 等。 |
| `learning.py` | 活动 | Python 模块；定义 _require_metrics_manager、learning_action、approve_learning_runtime、learning_runtime_controls、control_learning_runtime 等。 |
| `memories.py` | 活动 | Python 模块；定义 list_memories、create_memory、update_memory、delete_memory、restore_memory 等。 |
| `models.py` | 活动 | Python 模块；定义 list_models、model_health。 |
| `observability.py` | 活动 | Python 模块；定义 _resources、observability_summary、observability_metrics。 |
| `orchestration.py` | 活动 | Python 模块；定义 _local_handler_available、_attachments、_submit、create_chat、stream_chat 等。 |
| `research.py` | 活动 | Python 模块；定义 ResearchKnowledgeSearchRequest、get_research_knowledge、research_knowledge_status、research_knowledge_search、maintain_research_knowledge。 |
| `router.py` | 活动 | Python 配置或执行模块。 |
| `scenarios.py` | 活动 | Python 模块；定义 _preflight_for_scenario、list_scenarios、list_scenario_readiness、get_scenario、preflight_scenario 等。 |
| `sessions.py` | 活动 | Python 模块；定义 create_session、list_sessions、search_sessions、get_session、update_session 等。 |
| `tasks.py` | 活动 | Python 模块；定义 _bind_auto_scenario、task_read、_public_task_read、create_task、_hydrate_document_attachments 等。 |

### `apps/api/app/application`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Application-layer use cases. |
| `container.py` | 活动 | Python 模块；定义 ApplicationContainer。 |

### `apps/api/app/application/tasks`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `contracts.py` | 活动 | Python 模块；定义 TaskExecutionEngine。 |
| `coordinator.py` | 活动 | Python 模块；定义 TaskExecutionCoordinator。 |
| `leases.py` | 活动 | Python 模块；定义 _utc_now、TaskLeaseManager。 |
| `progress.py` | 活动 | Canonical application owner for public task progress events. |
| `query.py` | 活动 | Canonical application owner for task reads and event history. |

### `apps/api/app/bootstrap`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `lifespan.py` | 活动 | Python 模块；定义 ApplicationLifecycleResources、build_app_lifespan、_research_maintenance_loop、_recover_tasks、_warm_rag 等。 |
| `runtime_task_engine.py` | 活动 | Python 模块；定义 _runtime_service_agent_ids、build_runtime_task_engine。 |

### `apps/api/app/capabilities`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `base.py` | 活动 | Python 模块；定义 CapabilityResult、BaseCapability。 |
| `registry.py` | 活动 | Python 模块；定义 CapabilityRegistry、default_capability_registry。 |

### `apps/api/app/circuit`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `contracts.py` | 活动 | Python 模块；定义 CircuitComponent、CircuitNet、CircuitAnnotation、CircuitUncertainty、CircuitIR 等。 |
| `layout.py` | 活动 | Python 模块；定义 PortPoint、ComponentPlacement、CircuitLayout、classify_topology、build_schematic_layout 等。 |
| `layout_contracts.py` | 活动 | Python 模块；定义 SchematicPoint、SchematicBoundingBox、SchematicPlacement、SchematicPort、SchematicWire 等。 |
| `renderer.py` | 活动 | Python 模块；定义 render_circuit、_render_svg、_content_view_box、_try_schemdraw、_render_legacy_path 等。 |
| `semantic.py` | 活动 | Conservative semantic adapters for circuit rendering. |
| `tool.py` | 活动 | Python 模块；定义 circuit_render_tool。 |
| `validator.py` | 活动 | Python 模块；定义 validate_circuit、_duplicates。 |

### `apps/api/app/contracts`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `admin.py` | 活动 | Python 模块；定义 AdminAccountRead、AdminAccountCreate、AdminAccountUpdate、AdminPasswordReset、AdminFeatureSettingRead 等。 |
| `agent.py` | 活动 | Python 模块；定义 utc_now、new_id、UserRole、Scene、Intent 等。 |
| `analytics.py` | 活动 | Python 模块；定义 AnalyticsReportRead、AnalyticsQuery。 |
| `api.py` | 活动 | Python 模块；定义 SessionCreate、SessionRead、SessionUpdate、SessionTaskHistoryItem、TaskRead 等。 |
| `auth.py` | 活动 | Python 模块；定义 AccountRead、RegisterRequest、LoginRequest、RefreshRequest、AuthSessionRead 等。 |
| `conversation.py` | 活动 | Python 模块；定义 MessageRole、MessageStatus、MessageVisibility、ConversationMessage、TeachingStateV1 等。 |
| `experience.py` | 活动 | Python 模块；定义 _now、ExperienceType、ExperienceLifecycle、ExperienceScope、ExperienceEvidenceLevel 等。 |
| `external_retrieval.py` | 活动 | Python 模块；定义 ExternalSourceType、ExternalSourceScope、ExternalEvidenceSupport、ExternalRetrievalPolicy、ExternalEvidenceItem 等。 |
| `feedback.py` | 活动 | Python 模块；定义 FeedbackSatisfaction、FeedbackCreate、FeedbackRead、FeedbackMetricsRead、FeedbackFeatureStatusRead。 |
| `goal.py` | 活动 | Python 模块；定义 GoalContract。 |
| `intent.py` | 活动 | Python 模块；定义 IntentRecognition、PlanNode、IntentExecutionPlan。 |
| `knowledge.py` | 活动 | Python 模块；定义 KnowledgeCourseId、DocumentManifest、KnowledgeChunk、CitationSupport、KnowledgeSearchRequest 等。 |
| `learning.py` | 活动 | Python 模块；定义 TeachingMode、StudentAttemptStep、StudentAttempt、LearningPathDraft、StudentAttemptStatus 等。 |
| `math_content.py` | 活动 | Python 模块；定义 MathBlockType、MathSegmentType、MathExpression、RichTextSegment、MathRichContent。 |
| `memory.py` | 活动 | Python 模块；定义 MemoryType、MemoryStatus、MemoryScope、MemoryCreate、MemoryUpdate 等。 |
| `model.py` | 活动 | Python 模块；定义 ModelUsage、ModelResponse、ProviderHealth、ImageInput、ModelStreamEvent。 |
| `multimodal.py` | 活动 | Python 模块；定义 AttachmentRole、MultimodalCapabilityHint、MultimodalObservation、role_payload。 |
| `orchestration.py` | 活动 | Python 模块；定义 ExecutionStatus、InputType、ExecutionMode、TaskFamily、CourseCode 等。 |
| `planner.py` | 活动 | Python 模块；定义 PlannerLineage、PlannerBudget、CanonicalGoal、CanonicalPlanNode、PlannerSkillSelection 等。 |
| `reflection.py` | 活动 | Python 模块；定义 CriticResult、ReflectionDecision、RevisionRequest、RevisionProposal、ReflectionMetrics 等。 |
| `research.py` | 活动 | Python 模块；定义 ResearchIntentDecision、ResearchFinding、ResearchSourceGroup、ResearchTimelineItem、ResearchBriefDraft。 |
| `research_analysis.py` | 活动 | Python 模块；定义 ResearchVariable、ResearchDataManifest、ResearchDatasetProvenance、ResearchAnalysisProvenance、ResearchEvidenceReference 等。 |
| `routing.py` | 活动 | Python 模块；定义 RouteStatus、RouteCandidate、RouteDecision。 |
| `runtime.py` | 活动 | Python 模块；定义 RAGInteractionMode、RuntimeInputSubmission、RuntimeReconciliationSubmission、RuntimePlanProposalDecisionSubmission、RuntimeApprovalSubmission 等。 |
| `scenarios.py` | 活动 | Python 模块；定义 CommercializationPlan、KnowledgeEvidencePolicy、ScenarioDemoCase、ScenarioEvidenceSource、ScenarioEvidenceReviewRequest 等。 |
| `solver.py` | 活动 | Python 模块；定义 SolverTaskMode、ProblemComplexity、FallbackReason、AcademicProblem、ProfessionalConflict 等。 |

### `apps/api/app/core`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Core configuration, logging and errors. |
| `config.py` | 活动 | Python 模块；定义 Settings、get_settings。 |
| `errors.py` | 活动 | Python 模块；定义 AppError、ConfigurationError、ProviderError、ProviderTimeoutError、ProviderCancelledError 等。 |
| `internal_workflows.py` | 活动 | Python 配置或执行模块。 |
| `logging.py` | 活动 | Python 模块；定义 set_request_id、reset_request_id、mask_sensitive_text、redact、configure_logging。 |
| `redaction.py` | 活动 | Python 模块；定义 redact_sensitive_text。 |
| `security.py` | 活动 | Python 模块；定义 normalize_login、hash_password、verify_password、create_opaque_token、hash_token 等。 |

### `apps/api/app/courses`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `base.py` | 活动 | Python 模块；定义 CourseFallbackConfig、BaseCoursePack。 |
| `registry.py` | 活动 | Python 模块；定义 CourseRegistry、_pack、default_course_registry。 |

### `apps/api/app/database`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Database setup. |
| `base.py` | 活动 | Python 模块；定义 Base。 |
| `session.py` | 活动 | Python 模块；定义 create_engine_and_session。 |

### `apps/api/app/evaluation`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `cache.py` | 活动 | Python 模块；定义 EvaluationCache、evaluation_fingerprint。 |
| `contracts.py` | 活动 | Python 模块；定义 EvaluationProvenance、EvaluationRubric、FailureStage、EvaluationErrorType、EvaluationCase 等。 |
| `loader.py` | 活动 | Python 模块；定义 EvaluationCaseLoader。 |
| `loop.py` | 活动 | Python 模块；定义 LoopFailureStage、_id、_safe、EvaluationRecord、FailureRecord 等。 |
| `reporting.py` | 活动 | Python 模块；定义 build_statistics、write_report、evaluation_case_ids_sha256、evaluation_case_catalog_content_sha256、evaluation_case_source_files_sha256 等。 |
| `runner.py` | 活动 | Python 模块；定义 evaluation_timeout_decision、EvaluationRunner。 |

### `apps/api/app/evaluation/scorers`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `core.py` | 活动 | Python 模块；定义 normalize_text、ParsedQuantity、EvaluationScorer。 |

### `apps/api/app/infrastructure`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Infrastructure adapters and external integration composition points. |
| `runtime_adapters.py` | 活动 | Adapters from existing capability registries to Runtime handlers. |

### `apps/api/app/integrations`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | External integration boundaries. |

### `apps/api/app/models`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `entities.py` | 活动 | Python 模块；定义 utc_now、db_id、TaskStatus、AccountStatus、FileIngestionStatus 等。 |

### `apps/api/app/multimodal`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `file_parser.py` | 活动 | Python 模块；定义 detect_input_type。 |
| `image_batch.py` | 活动 | Python 模块；定义 ImageItemResult、ImageBatchProcessor。 |
| `image_composer.py` | 活动 | Python 模块；定义 SourceImage、PreparedImageBatch、MultiImageComposer。 |
| `image_encoder.py` | 活动 | Python 模块；定义 ImageEncoder。 |
| `pdf_processor.py` | 活动 | Python 模块；定义 PDFPage、PDFExtraction、PDFProcessor。 |
| `quality.py` | 活动 | Shared deterministic thresholds for multimodal extraction quality checks. |
| `result_merger.py` | 活动 | Python 模块；定义 merge_multimodal_results。 |

### `apps/api/app/observability`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `architecture_telemetry.py` | 活动 | Python 模块；定义 ArchitectureTelemetry。 |
| `metrics.py` | 活动 | Python 模块；定义 _safe_float、_safe_int、model_snapshot、trace_snapshot、task_snapshot 等。 |
| `model_tracer.py` | 活动 | Python 模块；定义 ModelCallRecord、ModelTracer。 |
| `trace_projection.py` | 活动 | Python 模块；定义 TraceSpan、TraceProjection、TraceProjectionService、_span_type、_status 等。 |
| `tracer.py` | 活动 | Python 模块；定义 TraceStore。 |

### `apps/api/app/orchestrator`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `graph_factory.py` | 活动 | Python 模块；定义 GraphFactory。 |
| `state.py` | 活动 | Python 模块；定义 XZDGraphState、new_graph_state。 |
| `supervisor.py` | 活动 | Python 模块；定义 PreparedTask、XZDSupervisor。 |

### `apps/api/app/orchestrator/graphs`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `academic_solver_graph.py` | 活动 | Python 模块；定义 GraphInterruptedError、AcademicProblemSolverGraph。 |

### `apps/api/app/providers`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `base.py` | 活动 | Python 模块；定义 AgentProvider。 |
| `development_mock.py` | 活动 | Python 模块；定义 DevelopmentMockProvider。 |
| `factory.py` | 活动 | Python 模块；定义 get_agent_provider、get_provider_availability。 |
| `local.py` | 活动 | Provider boundary for the local Runtime-only execution model. |
| `mock.py` | 活动 | Python 模块；定义 MockAgentProvider。 |

### `apps/api/app/providers/embedding`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `base.py` | 活动 | Python 模块；定义 EmbeddingProvider。 |
| `fallback.py` | 活动 | Python 模块；定义 DevelopmentEmbeddingFallback。 |
| `hash_legacy.py` | 活动 | Python 模块；定义 HashLegacyEmbeddingProvider。 |
| `local_sentence_transformer.py` | 活动 | Python 模块；定义 LocalSentenceTransformerEmbeddingProvider。 |

### `apps/api/app/providers/llm`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `base.py` | 活动 | Python 模块；定义 LLMMessage、LLMResult、BaseModelProvider。 |
| `dashscope_qwen.py` | 活动 | Python 模块；定义 resolve_dashscope_base_url、DashScopeQwenProvider。 |
| `iflytek_spark.py` | 活动 | Python 模块；定义 IflytekSparkProvider。 |
| `openai_compatible.py` | 活动 | Python 模块；定义 OpenAICompatibleProvider。 |
| `spark.py` | 活动 | Python 配置或执行模块。 |

### `apps/api/app/providers/retrieval`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `academic.py` | 活动 | Python 模块；定义 AcademicSearchProvider、AcademicProviderError、HttpAcademicProvider、ArxivAcademicProvider、CrossrefAcademicProvider 等。 |
| `adapters.py` | 活动 | Python 模块；定义 ProviderSearchContext、ProviderQuery、ProviderQueryAdapter、_cjk、OpenAlexQueryAdapter 等。 |
| `factory.py` | 活动 | Python 模块；定义 create_external_search_service、DeferredAcademicSearchService、_build_external_search_service、_usable_secret、_configured_provider_names 等。 |
| `web.py` | 活动 | Python 模块；定义 JsonWebSearchProvider、TavilySearchProvider、BraveSearchProvider、SerpApiSearchProvider、AliyunIqsSearchProvider 等。 |

### `apps/api/app/providers/vision`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `base.py` | 活动 | Python 模块；定义 VisionResult、VisionProvider。 |
| `iflytek_vision.py` | 活动 | Python 模块；定义 IFlytekVisionProvider。 |

### `apps/api/app/repositories`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `agent_runtime.py` | 活动 | Python 模块；定义 RuntimeConcurrencyError、AgentRunRepository。 |
| `artifacts.py` | 活动 | Python 模块；定义 ArtifactRepository。 |
| `conversations.py` | 活动 | Python 模块；定义 ConversationRepository。 |
| `experience_memory.py` | 活动 | Python 模块；定义 ExperienceRecordRepository。 |
| `files.py` | 活动 | Python 模块；定义 FileRepository。 |
| `learning.py` | 活动 | Python 模块；定义 LearningRecordRepository。 |
| `memories.py` | 活动 | Python 模块；定义 MemoryRepository。 |
| `runtime_context.py` | 活动 | Python 模块；定义 RuntimeContextRepository。 |
| `runtime_plan_proposals.py` | 活动 | Python 模块；定义 RuntimePlanProposalRepository。 |
| `sessions.py` | 活动 | Python 模块；定义 SessionRepository。 |
| `tasks.py` | 活动 | Python 模块；定义 TaskRepository。 |

### `apps/api/app/runtime`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Stateful Agent Runtime domain primitives. |
| `adapters.py` | 活动 | Deprecated compatibility facade for infrastructure runtime adapters. |
| `contracts.py` | 活动 | Python 模块；定义 RuntimeRunStatus、RuntimeLaunchSnapshot、RuntimeCompatibilitySnapshot、RuntimeNodeStatus、RuntimeNodeActivation 等。 |
| `controller.py` | 活动 | Python 模块；定义 RuntimeRunSuspended、RuntimeController、_resolve。 |
| `error_codes.py` | 活动 | Python 模块；定义 normalize_runtime_error_code。 |
| `event_bridge.py` | 活动 | Python 模块；定义 _elapsed_ms、_active_node_wall_ms、to_task_event、build_runtime_observability。 |
| `executor.py` | 活动 | Python 模块；定义 RuntimeNodeError、RuntimeNodeSuspended、PlanExecutor、_gather_with_exceptions。 |
| `goal_planner.py` | 活动 | Bounded goal-to-plan compilation over registered Runtime capabilities. |
| `handler_registry.py` | 活动 | Python 模块；定义 RuntimeHandlerDescriptor、RuntimeHandlerRegistryError、_schema_error、_matches_type、validate_input_schema 等。 |
| `plan_proposal_eval.py` | 活动 | Provider-free quality checks for adaptive Runtime plan proposals. |
| `replay.py` | 活动 | Offline Runtime trace auditing and evaluation primitives. |
| `semantic_evidence.py` | 活动 | Independent semantic review evidence for Legacy/Runtime pairs. |
| `solver_parity.py` | 活动 | Offline Legacy/Runtime parity evaluation for the academic solver. |
| `state_machine.py` | 活动 | Python 模块；定义 RuntimeStateMachine。 |
| `subagents.py` | 活动 | Typed, bounded registrations for Runtime sub-agent calls. |

### `apps/api/app/services`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Application services. |
| `academic_paper_review.py` | 活动 | Python 模块；定义 _matches_query_scope、AcademicPaperReviewService、_isoformat_datetime、_is_ai_frontier_request、_requested_year_range。 |
| `academic_review.py` | 活动 | Python 模块；定义 ReviewRule、AcademicReviewService。 |
| `academic_search_planner.py` | 活动 | Python 模块；定义 AcademicSearchPlannerService、requested_minimum、_deterministic_search_plan、_requested_minimum、_requests_high_citation 等。 |
| `academic_solver_runtime.py` | 活动 | Runtime adapter for the unified academic solver. |
| `academic_solver_service.py` | 活动 | Python 模块；定义 AcademicProblemSolverService。 |
| `academic_writing_runtime.py` | 活动 | Runtime adapter for the academic-writing business Agent. |
| `admin_service.py` | 活动 | Python 模块；定义 AdminService。 |
| `ae_validator.py` | 活动 | Python 模块；定义 AEValidator。 |
| `agent_result_governance.py` | 活动 | Python 模块；定义 _has_contract_value、AgentResultValidatorRegistry、BusinessResultRendererRegistry。 |
| `agent_runtime.py` | 活动 | Python 模块；定义 MappedAgentInput、ParsedWorkflowOutput、AgentInputMapper、WorkflowOutputParserRegistry、AgentExecutionPlanner 等。 |
| `agent_scaffold.py` | 活动 | Python 模块；定义 AgentScaffoldSpec、AgentScaffoldService。 |
| `analytics.py` | 活动 | Python 模块；定义 _value、_record、_nested、_task_scenario、_task_quick_template_used 等。 |
| `answer_disclosure.py` | 活动 | Python 模块；定义 AnswerDisclosureService、public_teaching_result。 |
| `assignment_review_runtime.py` | 活动 | Runtime adapter for the assignment-review business Agent. |
| `audit_service.py` | 活动 | Python 模块；定义 record_audit。 |
| `auth_service.py` | 活动 | Python 模块；定义 _as_utc、Principal、IssuedAuthSession、_LoginAttempt、LoginRateLimiter 等。 |
| `canonical_plan_adapter.py` | 活动 | Python 模块；定义 CanonicalPlanAdapter、_safe_id、_goal_phases、_canonical_node_type、_skill_bindings_from_context 等。 |
| `capability_binding_registry.py` | 活动 | Python 模块；定义 CapabilityBinding、CapabilityBindingRegistry、default_capability_binding_registry。 |
| `circuit_visualization.py` | 活动 | Python 模块；定义 CircuitVisualizationDecision、resolve_circuit_visualization_mode、decide_circuit_visualization、extract_circuit_ir、observation_from_result 等。 |
| `citation_validator.py` | 活动 | Python 模块；定义 CitationValidationResult、CitationValidator。 |
| `context_assembly.py` | 活动 | Python 模块；定义 ContextAssemblyService。 |
| `context_budget.py` | 活动 | Python 模块；定义 BudgetDecision、ContextBudgetManager。 |
| `context_cache.py` | 活动 | Python 模块；定义 ContextAssemblyCache。 |
| `conversation_message_service.py` | 活动 | Python 模块；定义 ConversationMessageService。 |
| `course_asset_review.py` | 活动 | Python 模块；定义 _load_yaml、_course_matches、_ocr_metadata_present、_ocr_confidence_present、_build_knowledge_inventory 等。 |
| `course_material_manifest.py` | 活动 | Python 模块；定义 CourseMaterialManifestResult、_write_jsonl_atomic、_write_json_atomic、_load_jsonl、load_revoked_material_ids 等。 |
| `ct_validator.py` | 活动 | Python 模块；定义 CTValidator。 |
| `de_validator.py` | 活动 | Python 模块；定义 BooleanEquivalenceResult、StateTransitionRow、DEValidator。 |
| `document_ingestion.py` | 活动 | Python 模块；定义 ChunkDraft、ExtractionResult、_normalise_text、_quality_report、_decode_text 等。 |
| `error_pool.py` | 活动 | Python 模块；定义 ErrorTemplateDefinition、ErrorPoolCatalog、ErrorPoolLookupResult、ErrorPoolRegistry。 |
| `error_pool_promotion.py` | 活动 | Python 模块；定义 _load_yaml、_sha256、_read_bytes、_relative_path、_atomic_write_bytes 等。 |
| `evaluation_attachment_cleanup.py` | 活动 | Python 模块；定义 cleanup_evaluation_attachments。 |
| `evaluation_attachment_maintenance.py` | 活动 | Python 模块；定义 EvaluationAttachmentResidueReport、_task_join、_candidate_filter、_active_task_file_filter、inspect_evaluation_attachment_residue 等。 |
| `evaluation_provenance.py` | 活动 | Python 模块；定义 _nonnegative_int、_bounded_ratio、_parse_report_time、_metadata_is_present、_base_provenance 等。 |
| `event_service.py` | 活动 | Python 模块；定义 _is_retryable_event_write_error、append_task_event、append_task_events。 |
| `evidence_excerpt.py` | 活动 | Python 模块；定义 _is_orphan_formula_line、_trim_incomplete_latex_tail、clean_evidence_excerpt、display_evidence_excerpt。 |
| `evidence_packet_adapter.py` | 活动 | Python 模块；定义 EvidencePacketAdapterService。 |
| `evidence_references.py` | 活动 | Python 模块；定义 classify_evidence_reference、analyze_evidence_references。 |
| `experience_memory.py` | 活动 | Python 模块；定义 _redact、_normalized_course、ExperienceMemoryService、ExperienceRetriever、ExperiencePlannerPrior 等。 |
| `external_research_answer.py` | 活动 | Python 模块；定义 is_academic_search_request、is_academic_search_follow_up、research_topic_families、research_topic_conflicts、_contains_compound_term 等。 |
| `external_research_runtime.py` | 活动 | Runtime adapter for the evidence-grounded external research Agent. |
| `external_retrieval.py` | 活动 | Python 模块；定义 ExternalFetchError、ExternalCitationValidation、ExternalCitationValidator、ExternalContentFetcher、_resolve_in_thread 等。 |
| `external_retrieval_execution.py` | 活动 | Provider-facing external retrieval orchestration. |
| `external_retrieval_gateway.py` | 活动 | Python 模块；定义 ExternalRetrievalGateway。 |
| `external_retrieval_intent.py` | 活动 | Python 模块；定义 _SignalGroup、ExternalRetrievalIntentRecognizer。 |
| `fallback_routing.py` | 活动 | Python 模块；定义 FallbackRoutingOutcome、FallbackRoutingService。 |
| `feature_flags.py` | 活动 | Python 模块；定义 feature_definition、is_feature_enabled、list_feature_settings、set_feature_enabled。 |
| `feedback_uptake.py` | 活动 | Python 模块；定义 _normalized、_steps、FeedbackUptakeService。 |
| `formula_output_contract.py` | 活动 | Python 模块；定义 evaluate_formula_output_contract、_evaluate_formula_semantics、_parse_equation、_normalize_equation_source、_infer_dimension 等。 |
| `general_model_fallback_runtime.py` | 活动 | Python 模块；定义 GeneralModelFallbackRuntimeService。 |
| `general_question_runtime.py` | 活动 | Python 模块；定义 GeneralQuestionRuntimeService。 |
| `general_question_service.py` | 活动 | Python 模块；定义 GeneralQuestionService。 |
| `generic_goal_runtime.py` | 活动 | Explicit structured-goal Runtime execution over registered handlers. |
| `health.py` | 活动 | Python 模块；定义 _file_digest、_runtime_identity、_configuration_warnings、_database_status、_redis_status 等。 |
| `high_risk_verification.py` | 活动 | Python 模块；定义 HighRiskVerificationService。 |
| `hint_policy.py` | 活动 | Python 模块；定义 HintPolicyService。 |
| `intent_plan.py` | 活动 | Python 模块；定义 IntentPlanCompiler。 |
| `intent_recognition.py` | 活动 | Python 模块；定义 IntentRecognitionService。 |
| `internal_agent_execution.py` | 活动 | Python 模块；定义 _duration_minutes、InternalAgentExecutionService。 |
| `knowledge_audit.py` | 活动 | Python 模块；定义 stable_id、checksum_file、posix_relative、source_uri、image_uri 等。 |
| `knowledge_base.py` | 活动 | Python 模块；定义 IndexedChunk、CourseMetadata、RetrievalTopicBoost、normalize_query、tokenize 等。 |
| `knowledge_index.py` | 活动 | Python 模块；定义 ChunkRecord、BuildResult、_split_long_block、markdown_blocks、_semantic_chunks_from_blocks 等。 |
| `knowledge_ocr_quality.py` | 活动 | Python 模块；定义 _decision_evidence_summary、_quality_row、build_ocr_quality_summary。 |
| `knowledge_ocr_review.py` | 活动 | Python 模块；定义 _review_action、_priority、_queue_row、build_ocr_review_queue、build_ocr_decision_template 等。 |
| `knowledge_ocr_review_cache.py` | 活动 | Python 模块；定义 _MemorySnapshot、_file_metadata、build_ocr_review_fingerprint、KnowledgeOCRReviewSnapshotCache。 |
| `knowledge_qa_runtime.py` | 活动 | Runtime adapter for evidence-grounded Knowledge QA and synthesis. |
| `knowledge_qa_service.py` | 活动 | Python 模块；定义 _requested_plan_days、_planned_days、KnowledgeQAExecution、KnowledgeQAService。 |
| `knowledge_resources.py` | 活动 | Python 模块；定义 resolve_course_resource、resolve_kb_image_uri。 |
| `learning_loop.py` | 活动 | Python 模块；定义 LearningRuntimeControlOutcome、LearningLoopService、_learning_control_marker。 |
| `learning_metrics.py` | 活动 | Python 模块；定义 LearningMetricsService。 |
| `learning_outcome.py` | 活动 | Python 模块；定义 LearningOutcomeResult、LearningOutcomeService。 |
| `learning_progress_runtime.py` | 活动 | Python 模块；定义 LearningProgressRuntimeOutcome、LearningProgressRuntimeService。 |
| `lesson_prep_runtime.py` | 活动 | Python 模块；定义 LessonPrepRuntimeService。 |
| `math_formatting_service.py` | 活动 | Python 模块；定义 _ProcessedChunk、MathFormattingService。 |
| `math_symbol_dictionary.py` | 活动 | Python 配置或执行模块。 |
| `memory_service.py` | 活动 | Python 模块；定义 MemoryService。 |
| `model_registry.py` | 活动 | Python 模块；定义 ModelDefinition、ModelRoute、ModelRegistry。 |
| `model_service.py` | 活动 | Python 模块；定义 ModelPreflight、ModelService。 |
| `multimodal_policy.py` | 活动 | Python 模块；定义 enrich_multimodal_request、build_multimodal_capability_hint、get_multimodal_capability_hint、requires_circuit_ir、_assign_attachment_roles 等。 |
| `next_check_question.py` | 活动 | Python 模块；定义 NextCheckQuestionService。 |
| `overall_routing.py` | 活动 | Python 模块；定义 OverallRoutingOutcome、OverallRoutingService。 |
| `planner.py` | 活动 | Python 模块；定义 PlannerOutput、PlannerExperienceShadow、GoalInterpreter、CandidateBuilder、PlannerPlanCompiler 等。 |
| `practice_generation.py` | 活动 | Python 模块；定义 PracticeGenerationService。 |
| `production_execution_manifest.py` | 活动 | The immutable production execution surface. |
| `query_rewrite.py` | 活动 | Python 模块；定义 rewrite_retrieval_query。 |
| `rag_debug.py` | 活动 | Python 模块；定义 utc_iso、DebugTraceStore、RAGDebugService。 |
| `rag_index.py` | 活动 | Python 模块；定义 IndexVersionInfo、RAGBuildResult、load_jsonl、MultimodalRAGIndexer。 |
| `rag_providers.py` | 活动 | Python 模块；定义 ProviderHealth、TextEmbeddingProvider、ImageEmbeddingProvider、RerankerProvider、resolve_device 等。 |
| `rag_retrieval.py` | 活动 | Python 模块；定义 RetrievalPolicy、policy_for、_Candidate、RAGRetrievalService。 |
| `rag_runtime.py` | 活动 | Python 模块；定义 create_text_embedding_provider、create_image_embedding_provider、create_reranker_provider、create_vector_store。 |
| `reflection_evaluation.py` | 活动 | Python 模块；定义 ReflectionEvaluationObservation、ReflectionEvaluationReport、ReflectionCanaryConfig、ReflectionCanaryDecision、ReflectionControlledCanary 等。 |
| `reflection_policy.py` | 活动 | Python 模块；定义 ReflectionPolicyConfig、ReflectionPolicy、parse_agent_allowlist。 |
| `reflection_service.py` | 活动 | Python 模块；定义 WorkerOutput、ReflectionOutcome、CriticWorker、RevisionWorker、InternalCriticWorker 等。 |
| `request_enrichment.py` | 活动 | Python 模块；定义 with_learning_context。 |
| `request_materials.py` | 活动 | Python 模块；定义 RequestMaterialExtractor。 |
| `research_analysis_planner.py` | 活动 | Python 模块；定义 _MethodSpec、ResearchAnalysisPlannerService、_effective_estimand、_missing_data_strategy。 |
| `research_analysis_review.py` | 活动 | Python 模块；定义 ResearchAnalysisReviewService。 |
| `research_analysis_runtime.py` | 活动 | Python 模块；定义 ResearchAnalysisRuntimeService。 |
| `research_data_quality.py` | 活动 | Python 模块；定义 ResearchDataQualityService。 |
| `research_frontier_service.py` | 活动 | Python 模块；定义 ResearchFrontierService。 |
| `research_knowledge.py` | 活动 | Python 模块；定义 ResearchKnowledgeService。 |
| `research_local_analysis.py` | 活动 | Python 模块；定义 LocalAnalysisExecutionError、_AnalysisOutput、ResearchLocalAnalysisExecutor、_load_rows、_raw_data_quality_report 等。 |
| `research_tabular_io.py` | 活动 | Python 模块；定义 ResearchTabularReadError、read_tabular_rows、_read_delimited、_read_json、_read_xlsx 等。 |
| `response_depth.py` | 活动 | Shared response-depth policies used by task execution services. |
| `retest_plans.py` | 活动 | Python 模块；定义 RetestPlanService。 |
| `retrieval_context.py` | 活动 | Python 模块；定义 EvidenceQuality、EvidenceQualityEvaluator、RetrievalContextService。 |
| `runtime_agent_readiness.py` | 活动 | Provider-free, per-Agent Runtime migration readiness reporting. |
| `runtime_business_registry.py` | 活动 | Python 模块；定义 RuntimeBusinessService、RuntimeBusinessRegistry。 |
| `runtime_canary_release.py` | 活动 | Load provider-free canary evidence for the Runtime launch policy. |
| `runtime_capability_descriptor.py` | 活动 | Provider-free capability descriptors for the two Runtime entry points. |
| `runtime_child_run.py` | 活动 | Durable execution boundary for typed Runtime sub-agent calls. |
| `runtime_control_policy.py` | 活动 | Provider-free control policy projections for durable Runtime runs. |
| `runtime_execution_boundary.py` | 活动 | Boundary around the durable Agent Runtime. |
| `runtime_goal_intake.py` | 活动 | Policy gate for turning a structured request goal into Runtime work. |
| `runtime_launch_policy.py` | 活动 | Per-agent launch policy for the incremental Runtime migration. |
| `runtime_persistence_hooks.py` | 活动 | Python 模块；定义 RuntimePersistenceHooks。 |
| `runtime_plan_proposals.py` | 活动 | Durable proposal and approval boundary for adaptive Runtime plans. |
| `runtime_release_authorization.py` | 活动 | Version-bound human authorization for Runtime launch promotion. |
| `runtime_request_preparation.py` | 活动 | Prepare the immutable request envelope for a durable Runtime launch. |
| `runtime_result_pipeline.py` | 活动 | Python 模块；定义 GovernedRuntimeResult、RuntimeResultPipeline。 |
| `runtime_run_lifecycle.py` | 活动 | Python 模块；定义 RuntimeRunLifecycleService。 |
| `runtime_safety.py` | 活动 | Python 模块；定义 sanitize_runtime_text、contains_sensitive_information。 |
| `runtime_task_engine.py` | 活动 | Python 模块；定义 RuntimeTaskComponents、_runtime_failure_message、utc_now、TaskRuntimeLifecycle。 |
| `scenario_catalog.py` | 活动 | Python 模块；定义 ScenarioCatalogError、ScenarioCatalog。 |
| `scenario_evidence_review.py` | 活动 | Python 模块；定义 ScenarioEvidenceReviewService。 |
| `scenario_output_contract.py` | 活动 | Python 模块；定义 _requested_research_count、ScenarioOutputContractService。 |
| `scenario_preflight.py` | 活动 | Python 模块；定义 ScenarioPreflightService。 |
| `session_compaction.py` | 活动 | Python 模块；定义 ConversationMemoryExtraction、SessionCompactionService。 |
| `session_context.py` | 活动 | Python 模块；定义 SessionContextService。 |
| `session_service.py` | 活动 | Python 模块；定义 SessionService。 |
| `session_working_state.py` | 活动 | Python 模块；定义 SessionWorkingStateService。 |
| `skill_binding.py` | 活动 | Python 模块；定义 SkillBindingRejection、SkillBindingResult、SkillBindingError、SkillBindingService。 |
| `skill_evaluation.py` | 活动 | Python 模块；定义 SkillEvaluationCase、SkillEvaluationResult、SkillEvaluationReport、SkillCanaryConfig、SkillCanaryDecision 等。 |
| `skill_policy.py` | 活动 | Python 模块；定义 SkillPolicyDecision、SkillPolicyResult、SkillPolicy。 |
| `skill_registry.py` | 活动 | Python 模块；定义 SkillDefinition、SkillCatalog、SkillMappingResult、SkillMatch、SkillRegistry。 |
| `skill_retriever.py` | 活动 | Python 模块；定义 SkillRetrievalRequest、SkillRetriever、normalized_terms。 |
| `solution_packet_adapter.py` | 活动 | Python 模块；定义 SolutionPacketAdapterService。 |
| `solver_boundary_policy.py` | 活动 | Python 模块；定义 BoundaryDecision、SolverBoundaryPolicy。 |
| `solver_quality_gate.py` | 活动 | Python 模块；定义 SolverQualityGateService。 |
| `solver_runtime_policy.py` | 活动 | Python 模块；定义 RequestTimeBudget、SolverRuntimePolicy、FallbackTracker。 |
| `storage.py` | 活动 | Python 模块；定义 sanitize_filename、StorageService。 |
| `student_answer_review.py` | 活动 | Python 模块；定义 _tokens、StudentAnswerReviewService。 |
| `student_attempts.py` | 活动 | Python 模块；定义 StudentAttemptService。 |
| `student_verification.py` | 活动 | Python 模块；定义 StudentVerificationService。 |
| `task_audit.py` | 活动 | Small, redacted audit envelope shared by Task and Runtime boundaries. |
| `task_completion.py` | 活动 | Python 模块；定义 TaskCompletionService。 |
| `task_control_service.py` | 活动 | Python 模块；定义 TaskControlService。 |
| `task_creation_service.py` | 活动 | Python 模块；定义 TaskCreationService。 |
| `task_executor.py` | 活动 | Python 模块；定义 TaskExecutor、LocalTaskExecutor、QueueTaskExecutor。 |
| `task_failure_service.py` | 活动 | Python 模块；定义 _utc_now、TaskFailureService。 |
| `task_observability.py` | 活动 | Python 模块；定义 _as_dict、first_value、bounded_int、result_sources、elapsed_ms 等。 |
| `task_post_processing.py` | 活动 | Python 模块；定义 TaskPostProcessingService。 |
| `task_presentation.py` | 活动 | Python 模块；定义 _is_orphan_formula_line、_clean_inline_formula_artifacts、_clean_markdown_image_links、_clean_evidence_excerpt、_model_generation_recorded 等。 |
| `task_progress.py` | 活动 | Deprecated compatibility import for the application progress owner. |
| `task_query_service.py` | 活动 | Deprecated compatibility import for the application task query owner. |
| `task_queue.py` | 活动 | Python 模块；定义 TaskQueue、RedisTaskQueue、InMemoryTaskQueue。 |
| `task_result_commit.py` | 活动 | Python 模块；定义 TaskTerminalCommitError、ensure_terminal_success、TaskResultCommitService。 |
| `task_result_presentation.py` | 活动 | Python 模块；定义 TaskResultPresentationService。 |
| `task_runtime_execution.py` | 活动 | Python 模块；定义 RuntimeExecutionOutcome、TaskRuntimeExecutionService。 |
| `task_runtime_preparation.py` | 活动 | Python 模块；定义 _route_progress_detail、PreparedRuntimeTask、TaskRuntimePreparationService。 |
| `task_session_commit.py` | 活动 | Python 模块；定义 TaskSessionCommitService。 |
| `task_worker.py` | 活动 | Python 模块；定义 TaskDispatcher、TaskWorker。 |
| `teaching_execution_planner.py` | 活动 | Python 模块；定义 TeachingExecutionPlanner。 |
| `teaching_foundation.py` | 活动 | Python 模块；定义 TeachingFoundationService。 |
| `teaching_input.py` | 活动 | Python 模块；定义 normalize_teaching_options、teaching_mode_status。 |
| `teaching_interaction.py` | 活动 | Python 模块；定义 TeachingInteractionService。 |
| `teaching_interaction_runtime.py` | 活动 | Python 模块；定义 TeachingRuntimeOutcome、TeachingInteractionRuntimeService。 |
| `unified_request_preparation.py` | 活动 | Python 模块；定义 UnifiedRequestPreparationService。 |
| `vector_store.py` | 活动 | Python 模块；定义 VectorSearchHit、VectorStoreAdapter、qdrant_point_id、_observe、QdrantVectorStoreAdapter。 |
| `visual_acceptance.py` | 活动 | Python 模块；定义 evaluate_visual_acceptance、_strings、_searchable_features、_explicit_signal_features、_explicit_spectrum_features 等。 |

### `apps/api/app/static/debug`

| 文件 | 状态 | 功能 |
|---|---|---|
| `admin.css` | 活动 | 静态前端样式：admin。 |
| `admin.html` | 活动 | 静态前端页面：管理总览 · 芯智导学。 |
| `admin.js` | 活动 | 静态前端交互逻辑：admin。 |
| `agents.html` | 活动 | 静态前端页面：Agent 管理 · 芯智导学。 |
| `agents.js` | 活动 | 静态前端交互逻辑：agents。 |
| `app-shell.css` | 活动 | 静态前端样式：app-shell。 |
| `components.css` | 活动 | 静态前端样式：components。 |
| `demo.html` | 活动 | 静态前端页面：演示中心 · 芯智导学。 |
| `demo.js` | 活动 | 静态前端交互逻辑：demo。 |
| `design-tokens.css` | 活动 | 静态前端样式：design-tokens。 |
| `execution-v2.css` | 活动 | 静态前端样式：execution-v2。 |
| `execution.html` | 活动 | 静态前端页面：执行调试 · 芯智导学。 |
| `execution.js` | 活动 | 静态前端交互逻辑：execution。 |
| `home.html` | 活动 | 静态前端页面：芯智导学。 |
| `login.html` | 活动 | 静态前端页面：账号入口 · 芯智导学。 |
| `login.js` | 活动 | 静态前端交互逻辑：login。 |
| `pages.css` | 活动 | 静态前端样式：pages。 |
| `rag.html` | 活动 | 静态前端页面：多模态 RAG 调试 · 芯智导学。 |
| `rag.js` | 活动 | 静态前端交互逻辑：rag。 |
| `student.html` | 活动 | 静态前端页面：智能学习 · 芯智导学。 |
| `student.js` | 活动 | 静态前端交互逻辑：student。 |
| `system.html` | 活动 | 静态前端页面：系统状态 · 芯智导学。 |
| `system.js` | 活动 | 静态前端交互逻辑：system。 |
| `teacher.css` | 活动 | 静态前端样式：teacher。 |
| `teacher.html` | 活动 | 静态前端页面：教师学习反馈工作台 · 芯智导学。 |
| `teacher.js` | 活动 | 静态前端交互逻辑：teacher。 |
| `ui-core.js` | 活动 | 静态前端交互逻辑：ui-core。 |
| `workspace-materials.js` | 活动 | 静态前端交互逻辑：workspace-materials。 |
| `workspace-task-transport.js` | 活动 | 静态前端交互逻辑：workspace-task-transport。 |
| `workspace-v2.css` | 活动 | 静态前端样式：workspace-v2。 |
| `workspace.html` | 活动 | 静态前端页面：智能任务工作台 · 芯智导学。 |
| `workspace.js` | 活动 | 静态前端交互逻辑：workspace。 |

### `apps/api/app/static/debug/assets`

| 文件 | 状态 | 功能 |
|---|---|---|
| `demo-circuit.svg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `apps/api/app/static/debug/ts`

| 文件 | 状态 | 功能 |
|---|---|---|
| `materials.js` | 活动 | 静态前端交互逻辑：materials。 |
| `task-transport.js` | 活动 | 静态前端交互逻辑：task-transport。 |
| `workspace-contracts.js` | 活动 | 静态前端交互逻辑：workspace-contracts。 |

### `apps/api/app/static/debug/vendor/katex`

| 文件 | 状态 | 功能 |
|---|---|---|
| `katex.min.css` | 活动 | 静态前端样式：katex.min。 |
| `katex.min.js` | 活动 | 静态前端交互逻辑：katex.min。 |
| `LICENSE` | 活动 | 仓库配置、资产或占位文件。 |

### `apps/api/app/static/debug/vendor/katex/fonts`

| 文件 | 状态 | 功能 |
|---|---|---|
| `KaTeX_AMS-Regular.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Caligraphic-Bold.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Caligraphic-Regular.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Fraktur-Bold.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Fraktur-Regular.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Main-Bold.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Main-BoldItalic.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Main-Italic.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Main-Regular.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Math-BoldItalic.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Math-Italic.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_SansSerif-Bold.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_SansSerif-Italic.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_SansSerif-Regular.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Script-Regular.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Size1-Regular.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Size2-Regular.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Size3-Regular.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Size4-Regular.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |
| `KaTeX_Typewriter-Regular.woff2` | 活动 | 本地前端字体资产，避免运行时依赖外部 CDN。 |

### `apps/api/app/tools`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `calculator.py` | 活动 | Python 模块；定义 calculate。 |
| `registry.py` | 活动 | Python 模块；定义 ToolDefinition、RegisteredTool、ToolRegistry、default_tool_registry。 |
| `sympy_solver.py` | 活动 | Python 模块；定义 solve_equations。 |
| `unit_checker.py` | 活动 | Python 模块；定义 UnitCheckResult、check_unit_compatibility。 |

### `apps/api/tests`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Backend test package. |
| `conftest.py` | 活动 | Python 模块；定义 ApiHelper、settings、app、client、api。 |
| `knowledge_test_utils.py` | 活动 | Python 模块；定义 make_service。 |
| `phase3_helpers.py` | 活动 | Python 模块；定义 power_payload、submit_power、learning_action。 |
| `rag_fakes.py` | 活动 | Python 模块；定义 _normalize、DeterministicFakeTextEmbeddingProvider、DeterministicFakeImageEmbeddingProvider、DeterministicFakeReranker。 |
| `test_academic_paper_review.py` | 活动 | 回归测试：academic paper review。 |
| `test_academic_retrieval_providers.py` | 活动 | 回归测试：academic retrieval providers。 |
| `test_academic_solver_runtime.py` | 活动 | 回归测试：academic solver runtime。 |
| `test_academic_writing_runtime.py` | 活动 | 回归测试：academic writing runtime。 |
| `test_admin_management.py` | 活动 | 回归测试：admin management。 |
| `test_admin_web.py` | 活动 | 回归测试：admin web。 |
| `test_ae_validator.py` | 活动 | 回归测试：ae validator。 |
| `test_agent_registry.py` | 活动 | 回归测试：agent registry。 |
| `test_agent_result_governance.py` | 活动 | 回归测试：agent result governance。 |
| `test_agent_runtime.py` | 活动 | 回归测试：agent runtime。 |
| `test_agent_runtime_foundation.py` | 活动 | 回归测试：agent runtime foundation。 |
| `test_agent_scaffold.py` | 活动 | 回归测试：agent scaffold。 |
| `test_analytics_api.py` | 活动 | 回归测试：analytics api。 |
| `test_assignment_review_runtime.py` | 活动 | 回归测试：assignment review runtime。 |
| `test_attachment_contract.py` | 活动 | 回归测试：attachment contract。 |
| `test_authentication.py` | 活动 | 回归测试：authentication。 |
| `test_automatic_routing_fixture.py` | 活动 | 回归测试：automatic routing fixture。 |
| `test_background_runtime_execution.py` | 活动 | 回归测试：background runtime execution。 |
| `test_circuit_core.py` | 活动 | 回归测试：circuit core。 |
| `test_circuit_rendering_v2.py` | 活动 | 回归测试：circuit rendering v2。 |
| `test_circuit_semantic.py` | 活动 | 回归测试：circuit semantic。 |
| `test_circuit_visualization_v3.py` | 活动 | 回归测试：circuit visualization v3。 |
| `test_commercial_scenario_cases.py` | 活动 | 回归测试：commercial scenario cases。 |
| `test_commercial_scenario_preflight.py` | 活动 | 回归测试：commercial scenario preflight。 |
| `test_config_validation.py` | 活动 | 回归测试：config validation。 |
| `test_contest_case_validation.py` | 活动 | 回归测试：contest case validation。 |
| `test_context_assembly.py` | 活动 | 回归测试：context assembly。 |
| `test_context_cache.py` | 活动 | 回归测试：context cache。 |
| `test_contracts.py` | 活动 | 回归测试：contracts。 |
| `test_course_asset_audit.py` | 活动 | 回归测试：course asset audit。 |
| `test_course_asset_review_api.py` | 活动 | 回归测试：course asset review api。 |
| `test_ct_validator.py` | 活动 | 回归测试：ct validator。 |
| `test_data_analysis_freeze.py` | 活动 | 回归测试：data analysis freeze。 |
| `test_debug_knowledge_qa.py` | 活动 | 回归测试：debug knowledge qa。 |
| `test_debug_page.py` | 活动 | 回归测试：debug page。 |
| `test_development_mock_agents.py` | 活动 | 回归测试：development mock agents。 |
| `test_docker_runtime_contract.py` | 活动 | 回归测试：docker runtime contract。 |
| `test_document_ingestion.py` | 活动 | 回归测试：document ingestion。 |
| `test_embedding_compatibility.py` | 活动 | 回归测试：embedding compatibility。 |
| `test_error_pool.py` | 活动 | 回归测试：error pool。 |
| `test_error_pool_promotion.py` | 活动 | 回归测试：error pool promotion。 |
| `test_evaluation_api.py` | 活动 | 回归测试：evaluation api。 |
| `test_evaluation_framework.py` | 活动 | 回归测试：evaluation framework。 |
| `test_evaluation_loop.py` | 活动 | 回归测试：evaluation loop。 |
| `test_event_sequence.py` | 活动 | 回归测试：event sequence。 |
| `test_evidence_packet_adapter.py` | 活动 | 回归测试：evidence packet adapter。 |
| `test_evidence_quality.py` | 活动 | 回归测试：evidence quality。 |
| `test_evidence_references.py` | 活动 | 回归测试：evidence references。 |
| `test_execution_debug_api.py` | 活动 | 回归测试：execution debug api。 |
| `test_execution_surface_lockdown.py` | 活动 | 回归测试：execution surface lockdown。 |
| `test_experience_memory.py` | 活动 | 回归测试：experience memory。 |
| `test_explanation_artifact.py` | 活动 | 回归测试：explanation artifact。 |
| `test_external_research_runtime.py` | 活动 | 回归测试：external research runtime。 |
| `test_external_retrieval_contract.py` | 活动 | 回归测试：external retrieval contract。 |
| `test_external_retrieval_intent.py` | 活动 | 回归测试：external retrieval intent。 |
| `test_external_retrieval_lazy.py` | 活动 | 回归测试：external retrieval lazy。 |
| `test_external_search_and_fetch.py` | 活动 | 回归测试：external search and fetch。 |
| `test_external_source_registry.py` | 活动 | 回归测试：external source registry。 |
| `test_feedback_api.py` | 活动 | 回归测试：feedback api。 |
| `test_feedback_uptake.py` | 活动 | 回归测试：feedback uptake。 |
| `test_file_metadata.py` | 活动 | 回归测试：file metadata。 |
| `test_file_upload.py` | 活动 | 回归测试：file upload。 |
| `test_formula_output_contract.py` | 活动 | 回归测试：formula output contract。 |
| `test_general_question_runtime.py` | 活动 | 回归测试：general question runtime。 |
| `test_general_question_service.py` | 活动 | 回归测试：general question service。 |
| `test_generic_goal_runtime.py` | 活动 | 回归测试：generic goal runtime。 |
| `test_generic_goal_task_e2e.py` | 活动 | 回归测试：generic goal task e2e。 |
| `test_goal_contract.py` | 活动 | 回归测试：goal contract。 |
| `test_heading_boost.py` | 活动 | 回归测试：heading boost。 |
| `test_health.py` | 活动 | 回归测试：health。 |
| `test_high_risk_verification.py` | 活动 | 回归测试：high risk verification。 |
| `test_history_quality_contract.py` | 活动 | 回归测试：history quality contract。 |
| `test_intent_recognition.py` | 活动 | 回归测试：intent recognition。 |
| `test_internal_agent_execution.py` | 活动 | 回归测试：internal agent execution。 |
| `test_internal_agents.py` | 活动 | 回归测试：internal agents。 |
| `test_kb_citation_integrity.py` | 活动 | 回归测试：kb citation integrity。 |
| `test_knowledge_api.py` | 活动 | 回归测试：knowledge api。 |
| `test_knowledge_base_service.py` | 活动 | 回归测试：knowledge base service。 |
| `test_knowledge_index_pipeline.py` | 活动 | 回归测试：knowledge index pipeline。 |
| `test_knowledge_lifecycle.py` | 活动 | 回归测试：knowledge lifecycle。 |
| `test_knowledge_ocr_quality.py` | 活动 | 回归测试：knowledge ocr quality。 |
| `test_knowledge_ocr_review.py` | 活动 | 回归测试：knowledge ocr review。 |
| `test_knowledge_ocr_review_cache.py` | 活动 | 回归测试：knowledge ocr review cache。 |
| `test_knowledge_qa_runtime.py` | 活动 | 回归测试：knowledge qa runtime。 |
| `test_knowledge_qa_runtime_contract.py` | 活动 | 回归测试：knowledge qa runtime contract。 |
| `test_knowledge_qa_runtime_persistence_recovery.py` | 活动 | 回归测试：knowledge qa runtime persistence recovery。 |
| `test_knowledge_qa_runtime_replan.py` | 活动 | 回归测试：knowledge qa runtime replan。 |
| `test_knowledge_qa_service.py` | 活动 | 回归测试：knowledge qa service。 |
| `test_knowledge_routing_api.py` | 活动 | 回归测试：knowledge routing api。 |
| `test_learning_attempt_api.py` | 活动 | 回归测试：learning attempt api。 |
| `test_learning_loop.py` | 活动 | 回归测试：learning loop。 |
| `test_learning_metrics.py` | 活动 | 回归测试：learning metrics。 |
| `test_learning_progress_runtime.py` | 活动 | 回归测试：learning progress runtime。 |
| `test_learning_retest_api.py` | 活动 | 回归测试：learning retest api。 |
| `test_learning_runtime_authorized_dev_e2e.py` | 活动 | 回归测试：learning runtime authorized dev e2e。 |
| `test_learning_runtime_control_api.py` | 活动 | 回归测试：learning runtime control api。 |
| `test_learning_runtime_control_service.py` | 活动 | 回归测试：learning runtime control service。 |
| `test_learning_runtime_pair_bundle.py` | 活动 | 回归测试：learning runtime pair bundle。 |
| `test_learning_runtime_pair_packaging.py` | 活动 | 回归测试：learning runtime pair packaging。 |
| `test_learning_runtime_readiness_api.py` | 活动 | 回归测试：learning runtime readiness api。 |
| `test_learning_runtime_release_readiness.py` | 活动 | 回归测试：learning runtime release readiness。 |
| `test_learning_runtime_semantic_sidecar.py` | 活动 | 回归测试：learning runtime semantic sidecar。 |
| `test_learning_runtime_status_projection.py` | 活动 | 回归测试：learning runtime status projection。 |
| `test_learning_runtime_ui_contract.py` | 活动 | 回归测试：learning runtime ui contract。 |
| `test_legacy_cleanup.py` | 活动 | 回归测试：legacy cleanup。 |
| `test_lesson_prep_runtime.py` | 活动 | 回归测试：lesson prep runtime。 |
| `test_mastery_evidence.py` | 活动 | 回归测试：mastery evidence。 |
| `test_mastery_update_policy.py` | 活动 | 回归测试：mastery update policy。 |
| `test_math_formatting_service.py` | 活动 | 回归测试：math formatting service。 |
| `test_migrations.py` | 活动 | 回归测试：migrations。 |
| `test_mock_provider.py` | 活动 | 回归测试：mock provider。 |
| `test_model_agent_evaluation.py` | 活动 | 回归测试：model agent evaluation。 |
| `test_model_api_integration.py` | 活动 | 回归测试：model api integration。 |
| `test_model_providers.py` | 活动 | 回归测试：model providers。 |
| `test_model_registry_service.py` | 活动 | 回归测试：model registry service。 |
| `test_model_security.py` | 活动 | 回归测试：model security。 |
| `test_model_service_routing.py` | 活动 | 回归测试：model service routing。 |
| `test_models_api.py` | 活动 | 回归测试：models api。 |
| `test_modernization_boundaries.py` | 活动 | 回归测试：modernization boundaries。 |
| `test_multimodal_batch.py` | 活动 | 回归测试：multimodal batch。 |
| `test_multimodal_rag.py` | 活动 | 回归测试：multimodal rag。 |
| `test_multimodal_routing_refinement.py` | 活动 | 回归测试：multimodal routing refinement。 |
| `test_observability_metrics.py` | 活动 | 回归测试：observability metrics。 |
| `test_openapi_export.py` | 活动 | 回归测试：openapi export。 |
| `test_orchestration_api.py` | 活动 | 回归测试：orchestration api。 |
| `test_orchestration_contracts.py` | 活动 | 回归测试：orchestration contracts。 |
| `test_overall_routing.py` | 活动 | 回归测试：overall routing。 |
| `test_path_traversal_rejected.py` | 活动 | 回归测试：path traversal rejected。 |
| `test_pdf_processor.py` | 活动 | 回归测试：pdf processor。 |
| `test_phase_i_ae_bias.py` | 活动 | 回归测试：phase i ae bias。 |
| `test_planner_authoritative.py` | 活动 | 回归测试：planner authoritative。 |
| `test_planner_canary.py` | 活动 | 回归测试：planner canary。 |
| `test_planner_contract.py` | 活动 | 回归测试：planner contract。 |
| `test_planner_controlled_takeover.py` | 活动 | 回归测试：planner controlled takeover。 |
| `test_planner_phase_b_baseline.py` | 活动 | 回归测试：planner phase b baseline。 |
| `test_planner_phase_b_closeout.py` | 活动 | 回归测试：planner phase b closeout。 |
| `test_planner_shadow_evaluation.py` | 活动 | 回归测试：planner shadow evaluation。 |
| `test_planner_shadow_mode.py` | 活动 | 回归测试：planner shadow mode。 |
| `test_planner_skill_shadow.py` | 活动 | 回归测试：planner skill shadow。 |
| `test_professional_tools.py` | 活动 | 回归测试：professional tools。 |
| `test_provider_factory.py` | 活动 | 回归测试：provider factory。 |
| `test_query_normalization.py` | 活动 | 回归测试：query normalization。 |
| `test_rag_debug_api.py` | 活动 | 回归测试：rag debug api。 |
| `test_rag_index_version_cache.py` | 活动 | 回归测试：rag index version cache。 |
| `test_readiness_consistency_audit.py` | 活动 | 回归测试：readiness consistency audit。 |
| `test_real_evaluation_framework.py` | 活动 | 回归测试：real evaluation framework。 |
| `test_real_rag_models.py` | 活动 | 回归测试：real rag models。 |
| `test_reflection_evaluation.py` | 活动 | 回归测试：reflection evaluation。 |
| `test_reflection_framework.py` | 活动 | 回归测试：reflection framework。 |
| `test_research03_runtime_boundary.py` | 活动 | 回归测试：research03 runtime boundary。 |
| `test_research_analysis_contract.py` | 活动 | 回归测试：research analysis contract。 |
| `test_research_analysis_demo.py` | 活动 | 回归测试：research analysis demo。 |
| `test_research_analysis_planner.py` | 活动 | 回归测试：research analysis planner。 |
| `test_research_analysis_review.py` | 活动 | 回归测试：research analysis review。 |
| `test_research_analysis_runtime.py` | 活动 | 回归测试：research analysis runtime。 |
| `test_research_analysis_runtime_verification_contract.py` | 活动 | 回归测试：research analysis runtime verification contract。 |
| `test_research_data_quality.py` | 活动 | 回归测试：research data quality。 |
| `test_research_frontier.py` | 活动 | 回归测试：research frontier。 |
| `test_research_knowledge.py` | 活动 | 回归测试：research knowledge。 |
| `test_research_local_analysis.py` | 活动 | 回归测试：research local analysis。 |
| `test_response_depth.py` | 活动 | 回归测试：response depth。 |
| `test_result_deduplication.py` | 活动 | 回归测试：result deduplication。 |
| `test_result_diversity.py` | 活动 | 回归测试：result diversity。 |
| `test_retest_plans.py` | 活动 | 回归测试：retest plans。 |
| `test_retrieval_benchmark.py` | 活动 | 回归测试：retrieval benchmark。 |
| `test_retrieval_context_packet.py` | 活动 | 回归测试：retrieval context packet。 |
| `test_runtime_adapters.py` | 活动 | 回归测试：runtime adapters。 |
| `test_runtime_agent_contract_matrix.py` | 活动 | 回归测试：runtime agent contract matrix。 |
| `test_runtime_agent_readiness.py` | 活动 | 回归测试：runtime agent readiness。 |
| `test_runtime_approval_roles.py` | 活动 | 回归测试：runtime approval roles。 |
| `test_runtime_authorized_dev_e2e.py` | 活动 | 回归测试：runtime authorized dev e2e。 |
| `test_runtime_authorized_e2e_input.py` | 活动 | 回归测试：runtime authorized e2e input。 |
| `test_runtime_browser_acceptance_analysis.py` | 活动 | 回归测试：runtime browser acceptance analysis。 |
| `test_runtime_business_registry_goal_binding.py` | 活动 | 回归测试：runtime business registry goal binding。 |
| `test_runtime_canary_cli.py` | 活动 | 回归测试：runtime canary cli。 |
| `test_runtime_canary_collection.py` | 活动 | 回归测试：runtime canary collection。 |
| `test_runtime_canary_release.py` | 活动 | 回归测试：runtime canary release。 |
| `test_runtime_capability_api_projection.py` | 活动 | 回归测试：runtime capability api projection。 |
| `test_runtime_capability_descriptor.py` | 活动 | 回归测试：runtime capability descriptor。 |
| `test_runtime_capability_ui_behavior.py` | 活动 | 回归测试：runtime capability ui behavior。 |
| `test_runtime_capability_ui_contract.py` | 活动 | 回归测试：runtime capability ui contract。 |
| `test_runtime_checkpoint_control_data.py` | 活动 | 回归测试：runtime checkpoint control data。 |
| `test_runtime_child_run.py` | 活动 | 回归测试：runtime child run。 |
| `test_runtime_contracts.py` | 活动 | 回归测试：runtime contracts。 |
| `test_runtime_control_policy.py` | 活动 | 回归测试：runtime control policy。 |
| `test_runtime_controls.py` | 活动 | 回归测试：runtime controls。 |
| `test_runtime_cross_entry_readiness_contract.py` | 活动 | 回归测试：runtime cross entry readiness contract。 |
| `test_runtime_debug_projection.py` | 活动 | 回归测试：runtime debug projection。 |
| `test_runtime_debug_ui_contract.py` | 活动 | 回归测试：runtime debug ui contract。 |
| `test_runtime_e2e_evidence_packager.py` | 活动 | 回归测试：runtime e2e evidence packager。 |
| `test_runtime_evidence_intake_contract.py` | 活动 | 回归测试：runtime evidence intake contract。 |
| `test_runtime_execution_boundary.py` | 活动 | 回归测试：runtime execution boundary。 |
| `test_runtime_execution_ui_contract.py` | 活动 | 回归测试：runtime execution ui contract。 |
| `test_runtime_goal_intake.py` | 活动 | 回归测试：runtime goal intake。 |
| `test_runtime_goal_planner.py` | 活动 | 回归测试：runtime goal planner。 |
| `test_runtime_goal_planner_parallel.py` | 活动 | 回归测试：runtime goal planner parallel。 |
| `test_runtime_handoff_contract.py` | 活动 | 回归测试：runtime handoff contract。 |
| `test_runtime_launch_policy.py` | 活动 | 回归测试：runtime launch policy。 |
| `test_runtime_observability.py` | 活动 | 回归测试：runtime observability。 |
| `test_runtime_paired_sample_analysis.py` | 活动 | 回归测试：runtime paired sample analysis。 |
| `test_runtime_parallel_recovery.py` | 活动 | 回归测试：runtime parallel recovery。 |
| `test_runtime_plan_proposals.py` | 活动 | 回归测试：runtime plan proposals。 |
| `test_runtime_readiness_projection_cli.py` | 活动 | 回归测试：runtime readiness projection cli。 |
| `test_runtime_readiness_recommended_actions.py` | 活动 | 回归测试：runtime readiness recommended actions。 |
| `test_runtime_release_authorization.py` | 活动 | 回归测试：runtime release authorization。 |
| `test_runtime_release_preflight.py` | 活动 | 回归测试：runtime release preflight。 |
| `test_runtime_replay.py` | 活动 | 回归测试：runtime replay。 |
| `test_runtime_request_preparation.py` | 活动 | 回归测试：runtime request preparation。 |
| `test_runtime_scenario_policy.py` | 活动 | 回归测试：runtime scenario policy。 |
| `test_runtime_semantic_evidence.py` | 活动 | 回归测试：runtime semantic evidence。 |
| `test_runtime_semantic_evidence_cli.py` | 活动 | 回归测试：runtime semantic evidence cli。 |
| `test_runtime_subagents.py` | 活动 | 回归测试：runtime subagents。 |
| `test_runtime_task_execution_path.py` | 活动 | 回归测试：runtime task execution path。 |
| `test_runtime_true_agent_contract_matrix.py` | 活动 | 回归测试：runtime true agent contract matrix。 |
| `test_runtime_uses_routed_agent.py` | 活动 | 回归测试：runtime uses routed agent。 |
| `test_scenario_catalog.py` | 活动 | 回归测试：scenario catalog。 |
| `test_scenario_evidence_review.py` | 活动 | 回归测试：scenario evidence review。 |
| `test_scenario_output_contract.py` | 活动 | 回归测试：scenario output contract。 |
| `test_scenario_preflight.py` | 活动 | 回归测试：scenario preflight。 |
| `test_scenarios_api.py` | 活动 | 回归测试：scenarios api。 |
| `test_score_threshold.py` | 活动 | 回归测试：score threshold。 |
| `test_sensitive_files_not_tracked.py` | 活动 | 回归测试：sensitive files not tracked。 |
| `test_sensitive_values_not_logged.py` | 活动 | 回归测试：sensitive values not logged。 |
| `test_service_layer_constraints.py` | 活动 | 回归测试：service layer constraints。 |
| `test_showcase_case_matrix.py` | 活动 | 回归测试：showcase case matrix。 |
| `test_skill_binding.py` | 活动 | 回归测试：skill binding。 |
| `test_skill_contract_phase_c.py` | 活动 | 回归测试：skill contract phase c。 |
| `test_skill_evaluation.py` | 活动 | 回归测试：skill evaluation。 |
| `test_skill_registry.py` | 活动 | 回归测试：skill registry。 |
| `test_skill_retriever_policy.py` | 活动 | 回归测试：skill retriever policy。 |
| `test_solution_packet_adapter.py` | 活动 | 回归测试：solution packet adapter。 |
| `test_solver_not_used_for_ae_de.py` | 活动 | 回归测试：solver not used for ae de。 |
| `test_solver_parity.py` | 活动 | 回归测试：solver parity。 |
| `test_solver_quality_gate.py` | 活动 | 回归测试：solver quality gate。 |
| `test_spark_llm_provider.py` | 活动 | 回归测试：spark llm provider。 |
| `test_sse_event_order.py` | 活动 | 回归测试：sse event order。 |
| `test_sse_events.py` | 活动 | 回归测试：sse events。 |
| `test_sse_reconnect.py` | 活动 | 回归测试：sse reconnect。 |
| `test_student_attempt_versions.py` | 活动 | 回归测试：student attempt versions。 |
| `test_student_runtime_controls_ui_contract.py` | 活动 | 回归测试：student runtime controls ui contract。 |
| `test_student_runtime_task_api_e2e.py` | 活动 | 回归测试：student runtime task api e2e。 |
| `test_student_web.py` | 活动 | 回归测试：student web。 |
| `test_supervisor.py` | 活动 | 回归测试：supervisor。 |
| `test_synonym_expansion.py` | 活动 | 回归测试：synonym expansion。 |
| `test_t4_numeric_parser.py` | 活动 | 回归测试：t4 numeric parser。 |
| `test_targeted_solver_optimization.py` | 活动 | 回归测试：targeted solver optimization。 |
| `test_task_api.py` | 活动 | 回归测试：task api。 |
| `test_task_audit.py` | 活动 | 回归测试：task audit。 |
| `test_task_cancel.py` | 活动 | 回归测试：task cancel。 |
| `test_task_creation_is_non_blocking.py` | 活动 | 回归测试：task creation is non blocking。 |
| `test_task_executor_reliability.py` | 活动 | 回归测试：task executor reliability。 |
| `test_task_idempotency.py` | 活动 | 回归测试：task idempotency。 |
| `test_task_presentation.py` | 活动 | 回归测试：task presentation。 |
| `test_task_presentation_external_legacy.py` | 活动 | 回归测试：task presentation external legacy。 |
| `test_task_queue_reliability.py` | 活动 | 回归测试：task queue reliability。 |
| `test_task_result_presentation.py` | 活动 | 回归测试：task result presentation。 |
| `test_task_retry.py` | 活动 | 回归测试：task retry。 |
| `test_task_router.py` | 活动 | 回归测试：task router。 |
| `test_task_runtime_execution_service.py` | 活动 | 回归测试：task runtime execution service。 |
| `test_task_session_commit.py` | 活动 | 回归测试：task session commit。 |
| `test_task_state_transitions.py` | 活动 | 回归测试：task state transitions。 |
| `test_task_terminal_boundary.py` | 活动 | 回归测试：task terminal boundary。 |
| `test_teacher_web.py` | 活动 | 回归测试：teacher web。 |
| `test_teaching_foundation_contracts.py` | 活动 | 回归测试：teaching foundation contracts。 |
| `test_teaching_foundation_evaluation.py` | 活动 | 回归测试：teaching foundation evaluation。 |
| `test_teaching_foundation_integration.py` | 活动 | 回归测试：teaching foundation integration。 |
| `test_teaching_loop_phase2_evaluation.py` | 活动 | 回归测试：teaching loop phase2 evaluation。 |
| `test_teaching_loop_phase2_integration.py` | 活动 | 回归测试：teaching loop phase2 integration。 |
| `test_teaching_loop_phase2_services.py` | 活动 | 回归测试：teaching loop phase2 services。 |
| `test_teaching_loop_phase3_evaluation.py` | 活动 | 回归测试：teaching loop phase3 evaluation。 |
| `test_teaching_state_phase3.py` | 活动 | 回归测试：teaching state phase3。 |
| `test_team_feedback_output_contracts.py` | 活动 | 回归测试：team feedback output contracts。 |
| `test_team_feedback_scenario_matrix.py` | 活动 | 回归测试：team feedback scenario matrix。 |
| `test_team_launcher.py` | 活动 | 回归测试：team launcher。 |
| `test_trace_projection.py` | 活动 | 回归测试：trace projection。 |
| `test_unified_web_ui.py` | 活动 | 回归测试：unified web ui。 |
| `test_universal_academic_solver.py` | 活动 | 回归测试：universal academic solver。 |
| `test_validate_research_pilot.py` | 活动 | 回归测试：validate research pilot。 |
| `test_visual_acceptance.py` | 活动 | 回归测试：visual acceptance。 |
| `test_workspace_learning_progress.py` | 活动 | 回归测试：workspace learning progress。 |
| `test_workspace_runtime_controls_contract.py` | 活动 | 回归测试：workspace runtime controls contract。 |

### `apps/api/tests/fixtures`

| 文件 | 状态 | 功能 |
|---|---|---|
| `circuit_golden_cases.json` | 活动 | 结构化数据集；包含 13 个顶层条目。 |
| `http_multigroup.csv` | 活动 | 仓库配置、资产或占位文件。 |
| `math_rendering_cases.json` | 活动 | 结构化数据集；包含 20 个顶层条目。 |
| `rag_eval_cases.json` | 活动 | 结构化数据集；包含 65 个顶层条目。 |
| `research_pilot_metadata.json` | 活动 | 结构化配置或数据；顶层字段：research_question、hypothesis、analysis_goal、design、unit_of_analysis、variables。 |
| `team_feedback_31_scenarios.json` | 活动 | 结构化数据集；包含 31 个顶层条目。 |

### `apps/api/tests/fixtures/agents`

| 文件 | 状态 | 功能 |
|---|---|---|
| `workflow_contract_cases.json` | 活动 | 结构化数据集；包含 15 个顶层条目。 |

### `apps/worker`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 活动 | 文档：Task Worker。 |
| `worker.py` | 活动 | Python 模块；定义 run_worker、main。 |

### `archive_legacy`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 历史隔离 | 历史隔离：文档：历史隔离区。 不参与活动运行链。 |

### `archive_legacy/apps/api/app/services`

| 文件 | 状态 | 功能 |
|---|---|---|
| `task_service.py` | 历史隔离 | 历史隔离：Archived compatibility facade for the retired ''TaskService'' import. 不参与活动运行链。 |

### `archive_legacy/docs`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 历史隔离 | 历史隔离：文档：历史文档说明。 不参与活动运行链。 |

### `archive_legacy/docs/architecture`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_stage_0_1_scope.md` | 历史隔离 | 历史隔离：文档：芯智导学多智能体平台阶段 0—1 架构摘要（保留快照）。 不参与活动运行链。 |
| `02_xinzhi_multi_agent_platform_plan_v1.0.md` | 历史隔离 | 历史隔离：文档：芯智导学多智能体平台架构（Stage 2.2）。 不参与活动运行链。 |

### `archive_legacy/docs/reviews`

| 文件 | 状态 | 功能 |
|---|---|---|
| `future_workflow_local_readiness_report.md` | 历史隔离 | 历史隔离：文档：未来工作流本地接入就绪报告。 不参与活动运行链。 |
| `stage_0_1_architecture_review.md` | 历史隔离 | 历史隔离：文档：阶段 0—1.5 架构审查。 不参与活动运行链。 |
| `stage_0_1_final_review_guide.md` | 历史隔离 | 历史隔离：文档：阶段 0—1.5 用户审查指南。 不参与活动运行链。 |
| `stage_0_1_reliability_review.md` | 历史隔离 | 历史隔离：文档：阶段 0—1.5 可靠性审查。 不参与活动运行链。 |
| `stage_0_1_security_review.md` | 历史隔离 | 历史隔离：文档：阶段 0—1.5 安全审查。 不参与活动运行链。 |
| `stage_1_6_final_review.md` | 历史隔离 | 历史隔离：文档：阶段 1.6 最终审查。 不参与活动运行链。 |
| `stage_1_6_initial_assessment.md` | 历史隔离 | 历史隔离：文档：阶段 1.6 初始评估。 不参与活动运行链。 |
| `stage_2_2_agent_registry_review.md` | 历史隔离 | 历史隔离：文档：Stage 2.2 Agent Registry Review。 不参与活动运行链。 |

### `archive_legacy/docs/workflows`

| 文件 | 状态 | 功能 |
|---|---|---|
| `all_agent_workflow_function_framework_plan.md` | 历史隔离 | 历史隔离：文档：芯智导学智能体工作流功能与框架规划。 不参与活动运行链。 |

### `ci-artifacts/stability-baseline`

| 文件 | 状态 | 功能 |
|---|---|---|
| `environment.txt` | 活动 | 仓库配置、资产或占位文件。 |
| `frontend-assets.txt` | 活动 | 仓库配置、资产或占位文件。 |
| `git-status.txt` | 活动 | 仓库配置、资产或占位文件。 |
| `health-latency.json` | 活动 | 结构化配置或数据；顶层字段：endpoint、samples、all_status_200、first_sample_ms、steady_state_min_ms、steady_state_max_ms。 |
| `process-memory.txt` | 活动 | 仓库配置、资产或占位文件。 |
| `task-statistics.txt` | 活动 | 仓库配置、资产或占位文件。 |

### `config`

| 文件 | 状态 | 功能 |
|---|---|---|
| `external_sources.yaml` | 活动 | 结构化配置或数据；顶层字段：version、sources。 |
| `learning_mastery.yaml` | 活动 | 结构化配置或数据；顶层字段：version、calibration_status、disclaimer、score_bounds、confidence_bounds、initial_score。 |
| `local_artifact_retention.yaml` | 活动 | 结构化配置或数据；顶层字段：evaluation_cache、local_outputs、mypy_cache、mypy_cache_apps、mypy_cache_api。 |
| `model_routes.yaml` | 活动 | 结构化配置或数据；顶层字段：routes。 |
| `models.yaml` | 活动 | 结构化配置或数据；顶层字段：models。 |
| `repo_layout.yaml` | 活动 | 结构化配置或数据；顶层字段：version、required_tracked、required_disk、forbidden_tracked。 |
| `scenarios.yaml` | 活动 | 结构化配置或数据；顶层字段：version、scenarios。 |

### `config/course_assets`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、course_id、runtime_loaded、runtime_source、runtime_course_pack_status、runtime_solver_entrypoint。 |
| `CT.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、course_id、runtime_loaded、runtime_source、runtime_course_pack_status、runtime_solver_entrypoint。 |

### `config/error_pool`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE.yaml` | 活动 | 结构化配置或数据；顶层字段：version、course_id、errors。 |
| `CT.yaml` | 活动 | 结构化配置或数据；顶层字段：version、course_id、errors。 |
| `DE.yaml` | 活动 | 结构化配置或数据；顶层字段：version、course_id、errors。 |

### `config/error_pool/proposals`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、course_id、runtime_loaded、review_status、proposals。 |
| `CT.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、course_id、runtime_loaded、review_status、proposals。 |

### `config/error_pool/reviews`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、course_id、runtime_loaded、review_status、reviewer、reviewed_at。 |
| `CT.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、course_id、runtime_loaded、review_status、reviewer、reviewed_at。 |

### `config/skills`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE.yaml` | 活动 | 结构化配置或数据；顶层字段：version、course_id、skills。 |
| `CT.yaml` | 活动 | 结构化配置或数据；顶层字段：version、course_id、skills。 |
| `DE.yaml` | 活动 | 结构化配置或数据；顶层字段：version、course_id、skills。 |
| `KNOWLEDGE.yaml` | 活动 | 结构化配置或数据；顶层字段：version、course_id、skills。 |
| `RESEARCH.yaml` | 活动 | 结构化配置或数据；顶层字段：version、course_id、skills。 |

### `constraints`

| 文件 | 状态 | 功能 |
|---|---|---|
| `backend-ci.txt` | 活动 | 仓库配置、资产或占位文件。 |

### `docs`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agent_extension_guide.md` | 活动 | 文档：Agent 扩展指南。 |
| `agent_registry.md` | 活动 | 文档：Agent Registry。 |
| `api_reference.md` | 活动 | 文档：API Reference。 |
| `capability_pack_design.md` | 活动 | 文档：CapabilityPack 设计。 |
| `course_pack_design.md` | 活动 | 文档：CoursePack 设计。 |
| `developer_code_navigation.md` | 活动 | 文档：芯智导学代码级开发手册。 |
| `development_guide.md` | 活动 | 文档：Development Guide。 |
| `evaluation_framework.md` | 活动 | 文档：多学科评测框架。 |
| `high_risk_verification.md` | 活动 | 文档：HIGH_RISK 校验与局部补丁。 |
| `langgraph_boundaries.md` | 活动 | 文档：LangGraph 使用边界。 |
| `local_orchestration_architecture.md` | 活动 | 文档：本地编排架构。 |
| `math_rendering_pipeline.md` | 活动 | 文档：数学公式规范化、传输与渲染。 |
| `migration_roadmap.md` | 活动 | 文档：Migration Roadmap。 |
| `model_api_configuration.md` | 活动 | 文档：国产多模型 API 配置。 |
| `observability.md` | 活动 | 文档：统一可观测性。 |
| `rag_pipeline.md` | 活动 | 文档：RAG Pipeline。 |
| `repository_architecture_guide.md` | 活动 | 文档：芯智导学仓库完整梳理。 |
| `repository_file_catalog.md` | 活动 | 本脚本生成的 Git 范围逐文件清单。 |
| `service_layer_dependency_map.md` | 活动 | 文档：服务层依赖图与收敛候选（目标 4 阶段 1）。 |
| `testing_guide.md` | 活动 | 文档：Testing Guide。 |
| `universal_academic_solver.md` | 活动 | 文档：通用多学科专业问题求解引擎。 |

### `docs/analytics`

| 文件 | 状态 | 功能 |
|---|---|---|
| `current_metric_inventory.md` | 活动 | 文档：Current metric inventory (A0)。 |
| `dashboard_guide.md` | 活动 | 文档：Dashboard 使用说明。 |
| `data_lineage.md` | 活动 | 文档：Analytics 数据血缘。 |
| `metric_dictionary.md` | 活动 | 文档：产品分析指标字典 v1。 |
| `source_of_truth_map.md` | 活动 | 文档：Analytics source-of-truth map (A0)。 |

### `docs/api`

| 文件 | 状态 | 功能 |
|---|---|---|
| `openapi.json` | 活动 | 结构化配置或数据文件（内容需由对应加载器校验）。 |

### `docs/architecture`

| 文件 | 状态 | 功能 |
|---|---|---|
| `active_execution_surface.md` | 活动 | 文档：Active Execution Surface。 |
| `agent_runtime_foundation.md` | 活动 | 文档：Agent Runtime Foundation v1。 |
| `automatic_agent_routing_architecture.md` | 活动 | 文档：自然语言自动调度架构。 |
| `canonical_plan_phase_b.md` | 活动 | 文档：Phase B2：Canonical Plan 与 Runtime Adapter。 |
| `external_retrieval_phase0_design.md` | 活动 | 文档：网络检索阶段 0：证据协议与安全边界。 |
| `external_retrieval_phase2_5_design.md` | 活动 | 文档：外部网络检索阶段 2–5 设计与运行说明。 |
| `multi_agent_runtime_architecture.md` | 活动 | 文档：多工作流本地运行架构。 |
| `overall_routing_agent.md` | 活动 | 文档：总体路由 Agent。 |
| `phase_n_control_plane_closeout.md` | 活动 | 文档：Phase N v2：Planner-Driven Control Plane 收口。 |
| `planner_phase_b_baseline.md` | 活动 | 文档：Phase B0：Planner 基线与兼容矩阵。 |
| `planner_phase_b_canary.md` | 活动 | 文档：Phase B5：Planner Canary Takeover。 |
| `planner_phase_b_final.md` | 活动 | 文档：Planner Phase B Final Architecture。 |
| `planner_phase_b_owner.md` | 活动 | 文档：Phase B1：Planner Owner 与依赖边界。 |
| `planner_phase_b_shadow.md` | 活动 | 文档：Phase B3：Planner Shadow Mode。 |
| `README.md` | 活动 | 文档：架构文档索引。 |
| `research_data_analysis_v2.md` | 活动 | 文档：科研数据分析 V2 设计合同。 |
| `runtime_capability_inventory.md` | 活动 | 文档：Runtime 能力盘点与迁移边界。 |
| `runtime_migration_research03_boundary.md` | 活动 | 文档：RESEARCH_03_DATA_ANALYSIS_V1 Runtime 迁移边界契约。 |
| `runtime_parallel_workflow.md` | 活动 | 文档：Agent Runtime 并行开发与质量协作规范。 |
| `skill_framework_phase_c.md` | 活动 | 文档：Phase C Skill Framework Architecture。 |
| `teaching_foundation_phase1.md` | 活动 | 文档：教学闭环基础能力第一阶段。 |
| `teaching_loop_phase2.md` | 活动 | 文档：教学闭环第二阶段架构。 |
| `teaching_loop_phase3.md` | 活动 | 文档：教学闭环第三阶段架构。 |
| `web_ui_architecture.md` | 活动 | 文档：芯智导学统一 Web UI 架构。 |
| `workflow_rag_integration_architecture.md` | 活动 | 文档：工作流与 RAG 融合架构。 |

### `docs/architecture_slimming`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_final_architecture.md` | 活动 | 文档：当前正式架构。 |
| `01_cleanup_record.md` | 活动 | 文档：架构收缩记录。 |
| `01_removed_and_archived.md` | 活动 | 文档：已删除与已归档内容。 |
| `02_remaining_complexity.md` | 活动 | 文档：剩余复杂度与服务候选。 |
| `03_runtime_graph.md` | 活动 | 文档：当前运行时文件关联图。 |
| `03_validation_report.md` | 活动 | 文档：结构收敛验证报告。 |
| `04_migration_risks.md` | 活动 | 文档：收缩后的迁移风险与验证边界。 |
| `04_next_latency_targets.md` | 活动 | 文档：下一阶段 Runtime 延迟目标。 |
| `before_after_metrics.json` | 活动 | 结构化配置或数据；顶层字段：audit_date、scope、before_cleanup_snapshot、after_cleanup_worktree_scan、removed_exact_surfaces、preserved_runtime_modules。 |
| `service_candidates.md` | 活动 | 文档：服务候选清单。 |

### `docs/audit`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01_system_function_inventory.md` | 活动 | 文档：芯智导学系统功能清单（只读审计初稿）。 |
| `02_runtime_call_chain.md` | 活动 | 文档：芯智导学核心调用链（只读审计初稿）。 |
| `03_bug_audit_report.md` | 活动 | 文档：芯智导学问题审计报告。 |
| `04_bug_fix_report.md` | 活动 | 文档：芯智导学问题修复报告。 |
| `05_test_validation_report.md` | 活动 | 文档：芯智导学测试与验证报告。 |
| `06_stable_baseline_closeout.md` | 活动 | 文档：芯智导学稳定基线收口报告。 |
| `07_scenario_runtime_matrix.md` | 活动 | 文档：六业务场景运行矩阵（修复后基线）。 |
| `08_scenario_failure_analysis.md` | 活动 | 文档：六业务场景失败归因与共享根因。 |
| `09_scenario_fix_report.md` | 活动 | 文档：六业务场景稳定性修复报告。 |
| `10_scenario_stability_closeout.md` | 活动 | 文档：六业务场景稳定性专项收口。 |
| `46_harness_circuit_baseline.md` | 活动 | 文档：H0 Harness + Circuit Baseline。 |
| `47_trace_projection_report.md` | 活动 | 文档：H1 Trace Projection 验收报告。 |
| `58_execution_lockdown_baseline.md` | 活动 | 文档：Execution Surface Lockdown：冻结基线报告。 |
| `59_legacy_quarantine_inventory.md` | 活动 | 文档：Legacy Quarantine Inventory。 |
| `60_active_execution_graph.md` | 活动 | 文档：Active Execution Graph。 |
| `61_registry_bootstrap_lockdown.md` | 活动 | 文档：Registry / Bootstrap Lockdown。 |
| `62_checkpoint_queue_generation_report.md` | 活动 | 文档：Checkpoint / Queue / Generation Report。 |
| `63_restart_soak_report.md` | 活动 | 文档：Restart / Soak Report。 |
| `64_legacy_tripwire_report.md` | 活动 | 文档：Legacy Tripwire Report。 |
| `65_execution_lockdown_regression.md` | 活动 | 文档：Execution Lockdown Regression。 |
| `66_execution_surface_stable_baseline.md` | 活动 | 文档：Execution Surface Stable Baseline。 |
| `67_dirty_change_ownership.md` | 活动 | 文档：Dirty Change Ownership Audit。 |
| `68_rc_exec_01_identity.md` | 活动 | 文档：RC-EXEC-01 Release Candidate Identity。 |
| `68_soak_test_baseline.md` | 活动 | 文档：8h Soak Test Baseline。 |
| `69_cold_restart_matrix.md` | 活动 | 文档：Release A2 Cold Restart Matrix。 |
| `70_persisted_state_generation_report.md` | 活动 | 文档：Release A3 Persisted State and Generation Report。 |
| `71_execution_surface_soak_report.md` | 活动 | 文档：Release A4 execution-surface soak。 |
| `72_workspace_release_matrix.md` | 活动 | 文档：Release A5 '/workspace' browser release matrix。 |
| `73_circuit_release_b_v1.md` | 活动 | 文档：Release B — Circuit Capability v1。 |
| `73_circuit_stress_report.md` | 活动 | 文档：Circuit Stress Report — Release B controlled slice。 |
| `81_multimodal_gate_audit.md` | 活动 | 文档：81 多模态 Gate 审计。 |
| `82_image_role_contract.md` | 活动 | 文档：82 图片角色契约。 |
| `83_multimodal_capability_routing.md` | 活动 | 文档：83 多模态能力提示与路由。 |
| `84_circuit_ir_trigger_report.md` | 活动 | 文档：84 CircuitIR 触发报告。 |
| `85_multimodal_browser_regression.md` | 活动 | 文档：85 多模态浏览器回归。 |
| `86_multimodal_refinement_stable_baseline.md` | 活动 | 文档：86 多模态细化稳定基线。 |
| `87_circuit_rendering_v2_audit.md` | 活动 | 文档：87 电路绘图 v2 审计。 |
| `88_symbol_library_report.md` | 活动 | 文档：88 电路符号库报告。 |
| `89_schematic_layout_report.md` | 活动 | 文档：89 原理图布局报告。 |
| `90_circuit_theory_render_report.md` | 活动 | 文档：90 电路理论绘图报告。 |
| `91_analog_render_report.md` | 活动 | 文档：91 模拟电路绘图报告。 |
| `92_digital_render_report.md` | 活动 | 文档：92 数字电路绘图报告。 |
| `93_routing_label_report.md` | 活动 | 文档：93 布线与标签报告。 |
| `94_circuit_browser_visual_report.md` | 活动 | 文档：94 浏览器电路图报告。 |
| `95_circuit_render_benchmark.md` | 活动 | 文档：95 电路绘图基准报告。 |
| `96_circuit_debug_fix_log.md` | 活动 | 文档：96 电路绘图调试修复记录。 |
| `97_circuit_visual_polish_report.md` | 活动 | 文档：97 电路图视觉打磨报告。 |
| `98_circuit_soak_report.md` | 活动 | 文档：98 电路绘图 Soak 报告。 |
| `99_circuit_rendering_v2_stable_baseline.md` | 活动 | 文档：99 电路绘图 v2 稳定基线。 |
| `agent_architecture_audit_phase1.md` | 活动 | 文档：芯智导学 Agent Architecture Audit & Refactoring Plan Phase 1。 |
| `agent_upgrade_roadmap.md` | 活动 | 文档：Agent Architecture Evolution Plan。 |
| `current_system_baseline.md` | 活动 | 文档：当前系统基线（2026-08-26）。 |
| `module_refactoring_plan_phase1.md` | 活动 | 文档：模块职责审计与 Phase 1 重构处理建议。 |
| `scenario_e2e_results.md` | 活动 | 文档：六业务场景初始 E2E 结果（修复前）。 |
| `scenario_runtime_matrix.md` | 活动 | 文档：工作台六业务场景运行矩阵（初始只读提取）。 |

### `docs/audits`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agent_function_architecture_audit_2026-08-21.md` | 活动 | 文档：学科智能体项目功能与架构审计报告。 |
| `challenge_cup_phase1_audit.md` | 活动 | 文档：“揭榜挂帅”项目阶段一现状审计。 |
| `evaluation_loop_phase_f1_contract.md` | 活动 | 文档：Phase F1：现有 Evaluation 审计与统一 Contract。 |
| `evaluation_loop_phase_f2_taxonomy.md` | 活动 | 文档：Phase F2：Trace-level Scoring 与 Failure Taxonomy。 |
| `evaluation_loop_phase_f3_failure_patterns.md` | 活动 | 文档：Phase F3：Failure Attribution 与 Pattern Aggregation。 |
| `evaluation_loop_phase_f4_improvement_proposals.md` | 活动 | 文档：Phase F4：Improvement Proposal Framework。 |
| `evaluation_loop_phase_f5_replay.md` | 活动 | 文档：Phase F5：Offline Replay 与 Counterfactual Evaluation。 |
| `evaluation_loop_phase_f6_promotion.md` | 活动 | 文档：Phase F6：Promotion Governance 与 Experience 对接。 |
| `evaluation_loop_phase_f7_full_suite.md` | 活动 | 文档：Phase F7：Full Suite 与 Evidence Campaign。 |
| `evaluation_loop_phase_f_closeout.md` | 活动 | 文档：Phase F：Evaluation Loop Closeout。 |
| `experience_memory_phase_e2_contract.md` | 活动 | 文档：Phase E2：ExperienceRecord 与治理 Contract。 |
| `experience_memory_phase_e3_governance.md` | 活动 | 文档：Phase E3：Experience Write 与 Promotion Pipeline。 |
| `experience_memory_phase_e4_retrieval_shadow.md` | 活动 | 文档：Phase E4：ExperienceRetriever 与 Planner Shadow。 |
| `experience_memory_phase_e5_controlled_prior.md` | 活动 | 文档：Phase E5：Controlled Planner Prior Integration。 |
| `experience_memory_phase_e6_evaluation_privacy.md` | 活动 | 文档：Phase E6：Evaluation、Privacy、Conflict 与 Forget。 |
| `experience_memory_phase_e_closeout.md` | 活动 | 文档：Phase E：Experience Memory Closeout。 |
| `phase_c0_repository_checkpoint.md` | 活动 | 文档：Phase C0 Repository Checkpoint。 |
| `phase_c1_existing_skill_audit_and_contract.md` | 活动 | 文档：Phase C1 Existing Skill Audit and Contract。 |
| `phase_c2_skill_registry_consolidation.md` | 活动 | 文档：Phase C2 Skill Registry Consolidation。 |
| `phase_c3_skill_retriever_and_policy.md` | 活动 | 文档：Phase C3 SkillRetriever and SkillPolicy。 |
| `phase_c4_planner_skill_shadow.md` | 活动 | 文档：Phase C4 Planner Skill Shadow Integration。 |
| `phase_c5_runtime_skill_binding.md` | 活动 | 文档：Phase C5 Runtime Skill Binding。 |
| `phase_c6_skill_evaluation_and_controlled_canary.md` | 活动 | 文档：Phase C6 Skill Evaluation 与 Controlled Canary 审计。 |
| `phase_d0_phase_c_release_checkpoint.md` | 活动 | 文档：Phase D0：Phase C Release Checkpoint。 |
| `phase_d1_existing_verification_audit_and_reflection_contract.md` | 活动 | 文档：Phase D1：Existing Verification Audit & Reflection Contract。 |
| `phase_d2_reflection_policy_and_trigger.md` | 活动 | 文档：Phase D2：ReflectionPolicy & Trigger Strategy。 |
| `phase_d3_critic_shadow_mode.md` | 活动 | 文档：Phase D3：Critic Shadow Mode。 |
| `phase_d4_bounded_revision_integration.md` | 活动 | 文档：Phase D4：Bounded Revision Integration。 |
| `phase_d5_verification_and_publish_gate.md` | 活动 | 文档：Phase D5：Verification & Publish Gate Integration。 |
| `phase_d6_reflection_evaluation_and_controlled_canary.md` | 活动 | 文档：Phase D6：Reflection Evaluation & Controlled Canary。 |
| `phase_e0_phase_d_release_checkpoint.md` | 活动 | 文档：Phase E0 — Phase D Release Checkpoint。 |
| `phase_e1_memory_and_trace_audit.md` | 活动 | 文档：Phase E1：Memory / Trace / Evaluation 现状审计。 |
| `phase_f0_phase_e_release_checkpoint.md` | 活动 | 文档：Phase F0：Phase E Release Checkpoint。 |
| `phase_f7_historical_failure_records.json` | 活动 | 结构化数据集；包含 6 个顶层条目。 |
| `phase_g_real_provider_baseline.md` | 活动 | 文档：Phase G：真实 Provider Baseline 与 Benchmark Harness。 |
| `phase_h_large_benchmark.md` | 活动 | 文档：Phase H：大规模 Benchmark Campaign。 |
| `phase_i_targeted_optimization.md` | 活动 | 文档：Phase I：Failure-driven Targeted Optimization。 |
| `phase_j_robustness.md` | 活动 | 文档：Phase J：Robustness / Stress / Regression 审计。 |
| `planner_phase_b_closeout.md` | 活动 | 文档：Planner Phase B Closeout Audit。 |
| `planner_phase_b_shadow_cases.yaml` | 活动 | 结构化配置或数据；顶层字段：version、evidence_level、cases。 |
| `planner_phase_b_shadow_parity.json` | 活动 | 结构化配置或数据；顶层字段：report_version、evidence_level、readiness、no_production_takeover、thresholds、checks。 |
| `planner_phase_b_shadow_parity.md` | 活动 | 文档：Phase B4 Planner Shadow Parity Report。 |
| `reflection_phase_d6_evaluation_report.md` | 活动 | 文档：Phase D6 Evaluation Report。 |
| `reflection_phase_d_closeout.md` | 活动 | 文档：Reflection Phase D Closeout。 |
| `skill_framework_phase_c_closeout.md` | 活动 | 文档：Skill Framework Phase C Closeout。 |
| `teaching_foundation_phase1_audit.md` | 活动 | 文档：教学闭环基础能力第一阶段实施前审计。 |
| `teaching_loop_phase3_audit.md` | 活动 | 文档：教学闭环第三阶段实施前审计。 |

### `docs/circuit`

| 文件 | 状态 | 功能 |
|---|---|---|
| `circuit_rendering_hardening_v2_closeout.md` | 活动 | 文档：Circuit rendering hardening v2 closeout。 |
| `circuit_visualization_core_closeout.md` | 活动 | 文档：Circuit visualization core closeout。 |
| `frontend_handoff.md` | 活动 | 文档：Frontend handoff。 |
| `performance_baseline.md` | 活动 | 文档：Math and circuit performance baseline。 |

### `docs/commercial_cases`

| 文件 | 状态 | 功能 |
|---|---|---|
| `academic_text_diagnostic_solver_v1.md` | 活动 | 文档：学术纯文本电路诊断与验证。 |
| `academic_visual_problem_solver_v1.md` | 活动 | 文档：学术题图视觉求解与结构验收。 |
| `academic_visual_spectrum_solver_v1.md` | 活动 | 文档：academic_visual_spectrum_solver_v1。 |
| `assessment_diagnosis_v1.md` | 活动 | 文档：案例二：作业批改与首错定位。 |
| `department_knowledge_governance_v1.md` | 活动 | 文档：案例五：学院知识库治理与课程资产发布。 |
| `faculty_course_copilot_v1.md` | 活动 | 文档：案例一：教师智能备课与课程资源生成。 |
| `final_report.md` | 活动 | 文档：剩余五个商业案例总报告。 |
| `README.md` | 活动 | 文档：商业案例打磨包。 |
| `research_data_workbench_v1.md` | 活动 | 文档：案例四：科研数据分析与可复现解释。 |
| `rubric_generation_v1.md` | 活动 | 文档：教师评分量规生成。 |
| `student_learning_path_v1.md` | 活动 | 文档：案例三：学情诊断与个性化学习路径。 |

### `docs/demo`

| 文件 | 状态 | 功能 |
|---|---|---|
| `final_demo_runbook.md` | 活动 | 文档：六案例最终演示运行手册。 |
| `frontend_display_standard.md` | 活动 | 文档：六案例前端展示规范。 |

### `docs/deployment`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agent_debug_console_guide.md` | 活动 | 文档：Agent 接入控制台指南。 |
| `authentication.md` | 活动 | 文档：认证基础（第一阶段）。 |
| `conversation_memory_guide.md` | 活动 | 文档：会话与长期记忆部署指南。 |
| `debug_console_ui_guide.md` | 活动 | 文档：Debug 控制台 UI 指南。 |
| `debug_page.md` | 活动 | 文档：本地演示页面。 |
| `execution_debug_console_guide.md` | 活动 | 文档：统一 Execution Debug 使用指南。 |
| `learning_state_configuration.md` | 活动 | 文档：学习状态配置。 |
| `local_development.md` | 活动 | 文档：本地开发指南。 |
| `meeting_auto_routing_demo_guide.md` | 活动 | 文档：会议自然语言自动调度演示指南。 |
| `meeting_demo_guide.md` | 活动 | 文档：会议演示指南。 |
| `meeting_demo_v2_guide.md` | 活动 | 文档：会议演示 V2 指南。 |
| `multi_workflow_frontend_guide.md` | 活动 | 文档：统一多工作流前端指南。 |
| `multimodal_input_guide.md` | 活动 | 文档：多模态材料输入。 |
| `server_production.md` | 活动 | 文档：服务器部署。 |
| `student_web_ui_guide.md` | 活动 | 文档：学生端 Web UI 指南。 |
| `student_web_v1_guide.md` | 活动 | 文档：学生端 Web v1 指南。 |
| `teaching_foundation_config.md` | 活动 | 文档：教学基础配置与验证。 |
| `teaching_loop_phase2_config.md` | 活动 | 文档：教学闭环第二阶段配置与运行。 |
| `team_quick_start.md` | 活动 | 文档：芯智导学团队快速使用指南。 |
| `unified_web_navigation_guide.md` | 活动 | 文档：统一 Web 导航指南。 |

### `docs/design`

| 文件 | 状态 | 功能 |
|---|---|---|
| `web_design_system.md` | 活动 | 文档：芯智导学 Web 设计系统。 |
| `workspace_ui_design.md` | 活动 | 文档：智能任务工作台 UI 设计。 |

### `docs/evaluation`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agent_runtime_replay.md` | 活动 | 文档：Agent Runtime 离线回放与评测。 |
| `evidence_projection_edge_followup_2026-08-13.md` | 活动 | 文档：资料依据投影与 Edge 复测补充记录（2026-08-13）。 |
| `formal_edge_acceptance_matrix_2026-08-14.md` | 活动 | 文档：芯智导学正式 Edge 验收矩阵（2026-08-14）。 |
| `full_acceptance_followup_2026-08-13.md` | 活动 | 文档：芯智导学完整验收跟进记录（2026-08-13）。 |
| `full_acceptance_followup_2026-08-14.md` | 活动 | 文档：Full acceptance follow-up — 2026-08-14。 |
| `knowledge_qa_runtime_contract.md` | 活动 | 文档：'LEARN_01_LOCAL_RETRIEVAL_V1' Runtime 合同评测。 |
| `real_evaluation_dataset_guide.md` | 活动 | 文档：真实评测数据集接入指南。 |
| `research_data_analysis_v2_synthetic.md` | 活动 | 文档：RESEARCH_03_DATA_ANALYSIS_V2 合成与边界评测。 |
| `runtime_agent_contract_matrix.md` | 活动 | 文档：Runtime Agent 合同矩阵。 |
| `runtime_ai_preliminary_semantic_review_2026-08-10.md` | 活动 | 文档：Runtime 语义初审记录（2026-08-10）。 |
| `runtime_authorized_dev_e2e_2026-08-10.md` | 活动 | 文档：授权开发环境 Runtime 端到端验证记录（2026-08-10）。 |
| `runtime_authorized_paired_trace_release_runbook.md` | 活动 | 文档：Runtime 授权成对 trace 采集与发布决策 Runbook。 |
| `runtime_business_closure_evidence.md` | 活动 | 文档：Business Runtime Closure Evidence。 |
| `runtime_completion_audit_2026-08-10.md` | 活动 | 文档：Agent Runtime 代码层完成审计（2026-08-10）。 |
| `runtime_edge_evidence_2026-08-12.md` | 活动 | 文档：Runtime / Edge 应用验证记录（2026-08-12）。 |
| `runtime_edge_evidence_2026-08-13.md` | 活动 | 文档：Runtime / Edge 补充验证记录（2026-08-13）。 |
| `runtime_evidence_intake_contract.md` | 活动 | 文档：Runtime evidence intake contract。 |
| `runtime_initial_audit_2026-08-09.md` | 活动 | 文档：Agent Runtime Initial Audit。 |
| `runtime_non_xingchen_application_e2e_2026-08-10.md` | 活动 | 文档：Non-Xingchen Runtime application E2E (2026-08-10)。 |
| `runtime_non_xingchen_paired_review_2026-08-10.md` | 活动 | Markdown 说明文档。 |
| `runtime_true_agent_contract_matrix.md` | 活动 | 文档：Runtime True-Agent Contract Matrix。 |
| `runtime_workspace_solver_e2e_2026-08-10.md` | 活动 | 文档：Runtime 工作台解题链路验收记录（2026-08-10）。 |

### `docs/full_system_audit`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_executive_summary.md` | 活动 | 文档：芯智导学全功能客观用户视角审计：执行摘要。 |
| `01_current_system_baseline.md` | 活动 | 文档：当前系统基线。 |
| `02_test_scope_and_methodology.md` | 活动 | 文档：测试范围与方法。 |
| `03_test_case_matrix.md` | 活动 | 文档：测试用例矩阵。 |
| `04_end_to_end_findings.md` | 活动 | 文档：端到端链路发现。 |
| `05_context_and_memory_findings.md` | 活动 | 文档：上下文、会话与记忆发现。 |
| `06_agent_router_planner_findings.md` | 活动 | 文档：Agent、Router、Planner 与能力绑定发现。 |
| `07_tool_rag_file_findings.md` | 活动 | 文档：Tool、RAG 与文件链路发现。 |
| `08_multimodal_findings.md` | 活动 | 文档：多模态与电路可视化发现。 |
| `09_solver_quality_findings.md` | 活动 | 文档：求解质量与答案表达发现。 |
| `10_research_workflow_findings.md` | 活动 | 文档：研究工作流发现。 |
| `11_frontend_ux_findings.md` | 活动 | 文档：前端与用户体验发现。 |
| `12_performance_findings.md` | 活动 | 文档：性能与可观测性发现。 |
| `13_stability_findings.md` | 活动 | 文档：稳定性发现。 |
| `14_fallback_and_review_findings.md` | 活动 | 文档：Fallback、人工复核与发布边界。 |
| `15_issue_register.md` | 活动 | 文档：问题登记表。 |
| `16_systemic_root_cause_hypotheses.md` | 活动 | 文档：系统性根因假设。 |
| `17_release_readiness_assessment.md` | 活动 | 文档：发布就绪评估。 |
| `issue_register.csv` | 活动 | 仓库配置、资产或占位文件。 |
| `latency_breakdown.csv` | 活动 | 仓库配置、资产或占位文件。 |
| `stability_runs.csv` | 活动 | 仓库配置、资产或占位文件。 |
| `test_cases.csv` | 活动 | 仓库配置、资产或占位文件。 |

### `docs/history`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 历史隔离 | 历史隔离：文档：历史资料索引。 不参与活动运行链。 |

### `docs/history/architecture-migration`

| 文件 | 状态 | 功能 |
|---|---|---|
| `architecture_consolidation_audit.md` | 历史隔离 | 历史隔离：文档：架构融合审计（历史记录）。 不参与活动运行链。 |
| `architecture_migration_audit.md` | 历史隔离 | 历史隔离：文档：架构迁移审计（历史记录）。 不参与活动运行链。 |
| `true_agent_runtime_roadmap.md` | 历史隔离 | 历史隔离：文档：True Agent Runtime 长期演进路线。 不参与活动运行链。 |

### `docs/history/frontend-react`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ci_and_evaluation.md` | 历史隔离 | 历史隔离：文档：CI 与评测闭环。 不参与活动运行链。 |

### `docs/history/frontend-react/architecture`

| 文件 | 状态 | 功能 |
|---|---|---|
| `phase_n0_baseline_drift.md` | 历史隔离 | 历史隔离：文档：Phase N0：基线漂移与控制面审计。 不参与活动运行链。 |
| `phase_n8_takeover_evaluation.md` | 历史隔离 | 历史隔离：文档：Phase N8：Presentation 解耦与 Active Takeover 评估。 不参与活动运行链。 |

### `docs/history/frontend-react/demo`

| 文件 | 状态 | 功能 |
|---|---|---|
| `math_rendering_audit.md` | 历史隔离 | 历史隔离：文档：六案例数学公式渲染审计。 不参与活动运行链。 |
| `six_scenario_demo_guide.md` | 历史隔离 | 历史隔离：文档：六大 Agent 演示案例使用指南。 不参与活动运行链。 |
| `six_scenario_test_report.md` | 历史隔离 | 历史隔离：文档：六大 Agent 演示案例测试报告。 不参与活动运行链。 |

### `docs/history/frontend-react/frontend`

| 文件 | 状态 | 功能 |
|---|---|---|
| `frontend_consolidation_closeout.md` | 历史隔离 | 历史隔离：文档：前端收敛交付记录。 不参与活动运行链。 |
| `frontend_parity_matrix.md` | 历史隔离 | 历史隔离：文档：Frontend parity baseline (A0)。 不参与活动运行链。 |
| `frontend_route_map.md` | 历史隔离 | 历史隔离：文档：Frontend route map (A0)。 不参与活动运行链。 |

### `docs/history/frontend-react/modernization`

| 文件 | 状态 | 功能 |
|---|---|---|
| `final_architecture_map.md` | 历史隔离 | 历史隔离：文档：Phase M Final Architecture Map。 不参与活动运行链。 |
| `m0_contract_freeze.md` | 历史隔离 | 历史隔离：文档：M0：Repository / Contract Freeze。 不参与活动运行链。 |
| `m1_backend_move_matrix.md` | 历史隔离 | 历史隔离：文档：M1：Backend Architecture Inventory 与 Move Matrix。 不参与活动运行链。 |
| `m1_frontend_feature_inventory.md` | 历史隔离 | 历史隔离：文档：M1：Frontend Feature Inventory。 不参与活动运行链。 |
| `m2_react_shell.md` | 历史隔离 | 历史隔离：文档：M2：React + TypeScript + Vite Shell。 不参与活动运行链。 |
| `m3_m4_backend_consolidation.md` | 历史隔离 | 历史隔离：文档：M3/M4：Backend Application、Capability、Runtime、Infrastructure、Governance 收敛。 不参与活动运行链。 |
| `m5_workspace_features.md` | 历史隔离 | 历史隔离：文档：M5：React Workspace Feature Migration。 不参与活动运行链。 |
| `m6_state_sse_learning.md` | 历史隔离 | 历史隔离：文档：M6：Frontend State / SSE / Learning Migration。 不参与活动运行链。 |
| `m7_parity_verification.md` | 历史隔离 | 历史隔离：文档：M7：Cross-stack Parity 与 Regression。 不参与活动运行链。 |
| `m8_code_health.md` | 历史隔离 | 历史隔离：文档：M8：Legacy Cleanup 与 Code Health。 不参与活动运行链。 |
| `phase_m_closeout.md` | 历史隔离 | 历史隔离：文档：Phase M Closeout。 不参与活动运行链。 |

### `docs/history/frontend-react/release`

| 文件 | 状态 | 功能 |
|---|---|---|
| `phase_p_final_report.md` | 历史隔离 | 历史隔离：文档：Phase P Final Report。 不参与活动运行链。 |

### `docs/history/frontend-react/reviews`

| 文件 | 状态 | 功能 |
|---|---|---|
| `frontend_visual_refinement_report.md` | 历史隔离 | 历史隔离：文档：前端视觉精修报告。 不参与活动运行链。 |
| `web_ui_refactor_report.md` | 历史隔离 | 历史隔离：文档：统一 Web UI 重构报告。 不参与活动运行链。 |

### `docs/history/frontend-react/reviews/web_ui_baseline`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agents-before.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `rag-before.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `student-before.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |

### `docs/history/frontend-react/reviews/web_ui_screenshots`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01-home-light.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `02-home-dark.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `03-student-empty.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `04-student-completed-answer.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `05-student-image-solver.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `06-rag-overview.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `07-rag-retrieval-results.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `08-agent-list.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `09-agent-detail.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `10-system-status.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `11-demo-center.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `12-presentation-mode.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `13-laptop-1366x768.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `14-mobile-390x844.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |

### `docs/history/frontend-react/reviews/workspace_v2_baseline`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01-home-light.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `02-home-dark.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `03-student-empty.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |

### `docs/history/frontend-react/reviews/workspace_v2_screenshots`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01-workspace-empty.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `02-ct-knowledge-answer.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `03-context-evidence.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `04-evidence-linked.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `05-process-simple.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `06-answer-info.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `07-ae-knowledge-answer.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `08-de-knowledge-answer.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `09-solver-text.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `10-solver-image-ready.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `11-mock-or-fallback-boundary.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `12-execution-debug.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `13-evidence-flow-comparison.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `14-demo-center.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `15-presentation-1280x720.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `16-workspace-dark.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |
| `17-workspace-mobile.png` | 历史隔离 | 历史隔离：界面验收、测试或文档使用的图像资产。 不参与活动运行链。 |

### `docs/history/frontend-react/xinzhi_architecture_modernization`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_PHASE_M_MASTER_GOAL.md` | 历史隔离 | 历史隔离：文档：Phase M：Frontend + Backend Architecture Modernization。 不参与活动运行链。 |
| `10_CODEX_FULL_EXECUTION_INSTRUCTION.md` | 历史隔离 | 历史隔离：文档：Codex Phase M 全量执行指令。 不参与活动运行链。 |
| `M0_repository_and_contract_freeze.md` | 历史隔离 | 历史隔离：文档：M0：Repository / Contract Freeze。 不参与活动运行链。 |
| `M1_architecture_inventory_and_move_matrix.md` | 历史隔离 | 历史隔离：文档：M1：Architecture Inventory 与 Move Matrix。 不参与活动运行链。 |
| `M2_react_vite_shell_and_api_boundary.md` | 历史隔离 | 历史隔离：文档：M2：React + TypeScript + Vite Shell。 不参与活动运行链。 |
| `M3_backend_application_and_capability_consolidation.md` | 历史隔离 | 历史隔离：文档：M3：Backend Application + Capability Consolidation。 不参与活动运行链。 |
| `M4_backend_runtime_infrastructure_governance_consolidation.md` | 历史隔离 | 历史隔离：文档：M4：Runtime / Infrastructure / Governance Consolidation。 不参与活动运行链。 |
| `M5_react_workspace_feature_migration.md` | 历史隔离 | 历史隔离：文档：M5：React Workspace Feature Migration。 不参与活动运行链。 |
| `M6_frontend_state_sse_and_learning_migration.md` | 历史隔离 | 历史隔离：文档：M6：Frontend State / SSE / Learning Migration。 不参与活动运行链。 |
| `M7_cross_stack_parity_and_regression.md` | 历史隔离 | 历史隔离：文档：M7：Cross-stack Parity 与 Regression。 不参与活动运行链。 |
| `M8_legacy_cleanup_and_code_health.md` | 历史隔离 | 历史隔离：文档：M8：Legacy Cleanup 与 Code Health。 不参与活动运行链。 |
| `M9_closeout_git_release_and_resume_testing.md` | 历史隔离 | 历史隔离：文档：M9：Closeout、统一 Git Release 与恢复 Benchmark。 不参与活动运行链。 |

### `docs/history/frontend-react/xinzhi_phase_n_v2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_PHASE_N_V2_MASTER_GOAL.md` | 历史隔离 | 历史隔离：文档：芯智导学 Phase N v2：Control Plane Convergence。 不参与活动运行链。 |
| `11_CODEX_PHASE_N_V2_INSTRUCTION.md` | 历史隔离 | 历史隔离：文档：Codex Phase N v2 完整执行指令。 不参与活动运行链。 |
| `N0_BASELINE_DRIFT_AND_CONTROL_AUDIT.md` | 历史隔离 | 历史隔离：文档：N0：基线漂移治理 + 控制面审计。 不参与活动运行链。 |
| `N10_DELETE_OLD_CLOSEOUT_RELEASE.md` | 历史隔离 | 历史隔离：文档：N10：删除旧路径、文档收口与 Git Release。 不参与活动运行链。 |
| `N1_UNIFIED_INGRESS_GOAL_CONTRACT.md` | 历史隔离 | 历史隔离：文档：N1：Unified Ingress + GoalContract。 不参与活动运行链。 |
| `N2_PLANNER_SHADOW_UPGRADE.md` | 历史隔离 | 历史隔离：文档：N2：Planner Shadow 真实性提升。 不参与活动运行链。 |
| `N3_CAPABILITY_SKILL_PRODUCTION.md` | 历史隔离 | 历史隔离：文档：N3：Capability / Skill 生产化。 不参与活动运行链。 |
| `N4_CANONICAL_PLAN_RUNTIME.md` | 历史隔离 | 历史隔离：文档：N4：CanonicalPlan → Runtime 单向执行。 不参与活动运行链。 |
| `N5_CONTROLLED_TAKEOVER.md` | 历史隔离 | 历史隔离：文档：N5：Controlled Takeover。 不参与活动运行链。 |
| `N6_RETIRE_OLD_ROUTING.md` | 历史隔离 | 历史隔离：文档：N6：退休 Overall Router 与 IntentPlanCompiler 默认权力。 不参与活动运行链。 |
| `N7_RETIRE_LEGACY_FIXED_RUNTIME.md` | 历史隔离 | 历史隔离：文档：N7：退休 Legacy Runtime / Fixed Agent Workflow。 不参与活动运行链。 |
| `N8_PRESENTATION_DECOUPLING.md` | 历史隔离 | 历史隔离：文档：N8：Presentation 解耦与前端兼容验证。 不参与活动运行链。 |
| `N9_ACTIVE_TAKEOVER_FULL_REGRESSION.md` | 历史隔离 | 历史隔离：文档：N9：Active Takeover + Full Regression。 不参与活动运行链。 |

### `docs/history/frontend-react/xinzhi_phase_p_pilot_validation`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_PHASE_P_MASTER_GOAL.md` | 历史隔离 | 历史隔离：文档：芯智导学 Phase P：Pilot Validation & Product Hardening。 不参与活动运行链。 |
| `09_TEAMMATE_PILOT0_TEST_GUIDE.md` | 历史隔离 | 历史隔离：文档：组员 Pilot 0 真实测试指南。 不参与活动运行链。 |
| `10_CODEX_PHASE_P_EXECUTION_INSTRUCTION.md` | 历史隔离 | 历史隔离：文档：Codex Phase P 完整执行指令。 不参与活动运行链。 |
| `P0_PILOT_EVIDENCE_FREEZE.md` | 历史隔离 | 历史隔离：文档：P0：Pilot 0 证据冻结。 不参与活动运行链。 |
| `P1_REAL_FAILURE_ATTRIBUTION.md` | 历史隔离 | 历史隔离：文档：P1：真实问题归因。 不参与活动运行链。 |
| `P2_CRITICAL_PRODUCT_FIXES.md` | 历史隔离 | 历史隔离：文档：P2：Critical Product Fixes。 不参与活动运行链。 |
| `P3_AGENT_QUALITY_OPTIMIZATION.md` | 历史隔离 | 历史隔离：文档：P3：Agent Quality 定向优化。 不参与活动运行链。 |
| `P4_SIX_DEMO_PRODUCTIZATION.md` | 历史隔离 | 历史隔离：文档：P4：六案例产品化收口。 不参与活动运行链。 |
| `P5_UX_LOCALIZATION_MATH_POLISH.md` | 历史隔离 | 历史隔离：文档：P5：UX / 中文 / LaTeX / 可读性收口。 不参与活动运行链。 |
| `P6_RELIABILITY_PERFORMANCE_COST.md` | 历史隔离 | 历史隔离：文档：P6：稳定性、性能与成本。 不参与活动运行链。 |
| `P7_FINAL_PILOT_ACCEPTANCE.md` | 历史隔离 | 历史隔离：文档：P7：Final Pilot + Acceptance。 不参与活动运行链。 |
| `P8_RELEASE_HANDOFF_AND_SHOWCASE.md` | 历史隔离 | 历史隔离：文档：P8：Release / Team Handoff / Showcase。 不参与活动运行链。 |

### `docs/history/frontend-react/xinzhi_six_demo_optimization`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_MASTER_PLAN.md` | 历史隔离 | 历史隔离：文档：芯智导学六大演示案例优化总计划。 不参与活动运行链。 |
| `01_FRONTEND_PRESENTATION_STANDARD.md` | 历史隔离 | 历史隔离：文档：六大演示案例前端呈现统一规范。 不参与活动运行链。 |
| `02_LANGUAGE_NORMALIZATION.md` | 历史隔离 | 历史隔离：文档：前端中英文混杂专项治理。 不参与活动运行链。 |
| `03_LATEX_RENDERING.md` | 历史隔离 | 历史隔离：文档：LaTeX 数学公式呈现专项优化。 不参与活动运行链。 |
| `04_DEMO_TEACHER_PREP.md` | 历史隔离 | 历史隔离：文档：Demo 1：教师智能备课。 不参与活动运行链。 |
| `05_DEMO_FIRST_ERROR_DIAGNOSIS.md` | 历史隔离 | 历史隔离：文档：Demo 2：作业批改与首错诊断。 不参与活动运行链。 |
| `06_DEMO_PERSONALIZED_LEARNING.md` | 历史隔离 | 历史隔离：文档：Demo 3：学生个性化学习路径。 不参与活动运行链。 |
| `07_DEMO_RESEARCH_EVIDENCE_BRIEF.md` | 历史隔离 | 历史隔离：文档：Demo 4：科研前沿证据简报。 不参与活动运行链。 |
| `08_DEMO_KNOWLEDGE_GOVERNANCE.md` | 历史隔离 | 历史隔离：文档：Demo 5：学院知识库治理。 不参与活动运行链。 |
| `09_DEMO_ANALOG_CIRCUIT_DIAGNOSIS.md` | 历史隔离 | 历史隔离：文档：Demo 6：模拟电子技术电路诊断。 不参与活动运行链。 |
| `10_CROSS_DEMO_ACCEPTANCE.md` | 历史隔离 | 历史隔离：文档：六大案例统一验收。 不参与活动运行链。 |
| `11_CODEX_EXECUTION_INSTRUCTION.md` | 历史隔离 | 历史隔离：文档：Codex 六大演示案例专项优化执行指令。 不参与活动运行链。 |

### `docs/history/retired-solver-ct`

| 文件 | 状态 | 功能 |
|---|---|---|
| `legacy_cleanup_report.md` | 历史隔离 | 历史隔离：文档：旧文件与功能清理记录。 不参与活动运行链。 |
| `solver_ct_migration.md` | 历史隔离 | 历史隔离：文档：SolverCT 兼容迁移。 不参与活动运行链。 |

### `docs/history/retired-solver-ct/baseline`

| 文件 | 状态 | 功能 |
|---|---|---|
| `solver_ct_known_issues.md` | 历史隔离 | 历史隔离：文档：SOLVER_CT v1.0 已知事项。 不参与活动运行链。 |
| `solver_ct_node_inventory.md` | 历史隔离 | 历史隔离：文档：SOLVER_CT v1.0 节点清单。 不参与活动运行链。 |
| `solver_ct_release_checklist.md` | 历史隔离 | 历史隔离：文档：本地阶段 0—1.5 发布检查清单。 不参与活动运行链。 |
| `solver_ct_v1.0_baseline.md` | 历史隔离 | 历史隔离：文档：SOLVER_CT v1.0 冻结基线。 不参与活动运行链。 |

### `docs/history/retired-solver-ct/baseline/generated`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 历史隔离 | 历史隔离：文档：SOLVER_CT 导出解析结果。 不参与活动运行链。 |

### `docs/implementation`

| 文件 | 状态 | 功能 |
|---|---|---|
| `answer_disclosure_policy.md` | 活动 | 文档：AnswerDisclosurePolicy V1。 |
| `challenge_cup_p0_plan.md` | 活动 | 文档：P0：CT/AE 旗舰教学闭环实施计划。 |
| `evidence_packet_v1.md` | 活动 | 文档：EvidencePacket v1。 |
| `feedback_uptake_v1.md` | 活动 | 文档：FeedbackUptakeV1。 |
| `hint_policy_h0_h2.md` | 活动 | 文档：H0—H2 提示策略。 |
| `learning_quality_loop.md` | 活动 | 文档：学习质量闭环实现说明。 |
| `mastery_evidence.md` | 活动 | 文档：MasteryEvidence 与学习进度估计。 |
| `next_check_question.md` | 活动 | 文档：NextCheckQuestion V1。 |
| `p10_pdf_text_layer_and_page_evidence.md` | 活动 | 文档：P10：PDF 文本层与页码证据链。 |
| `p11_ocr_review_queue.md` | 活动 | 文档：P11：PDF/OCR 教师复核队列。 |
| `p12_ocr_review_decisions.md` | 活动 | 文档：P12：OCR 复核决策协议。 |
| `p13_ocr_evidence_merge.md` | 活动 | 文档：P13：OCR 复核证据增强与决策合并。 |
| `p14_ocr_review_api.md` | 活动 | 文档：P14：教师侧只读 OCR 复核 API。 |
| `p15_teacher_ocr_workbench.md` | 活动 | 文档：P15 教师 OCR 复核工作台。 |
| `p16_ocr_review_snapshot_cache.md` | 活动 | 文档：P16 OCR 复核队列快照缓存。 |
| `p17_teacher_ocr_observability.md` | 活动 | 文档：P17 教师 OCR 复核可观测性。 |
| `p18_teacher_ocr_queue_filters.md` | 活动 | 文档：P18 教师 OCR 队列聚焦筛选。 |
| `p19_teacher_review_queue.md` | 活动 | 文档：P19：CT/AE 错误模板教师复核清单。 |
| `p1_document_quality.md` | 活动 | 文档：P1：课程资料解析质量报告。 |
| `p20_teacher_asset_review_workbench.md` | 活动 | 文档：P20：教师工作台课程错误模板复核队列。 |
| `p21_course_asset_readiness.md` | 活动 | 文档：P21：课程资产与竞赛支撑 readiness 摘要。 |
| `p22_readiness_evidence_checks.md` | 活动 | 文档：P22：Readiness 证据一致性检查。 |
| `p23_knowledge_inventory_readiness.md` | 活动 | 文档：P23：知识库质量摘要接入课程 readiness。 |
| `p24_ocr_quality_evidence_workbench.md` | 活动 | 文档：P24：OCR 质量证据工作台。 |
| `p25_ocr_decision_evidence_status.md` | 活动 | 文档：P25：OCR 决策证据状态。 |
| `p26_ocr_decision_writeback.md` | 活动 | 文档：P26：教师 OCR 决策与证据写回。 |
| `p27_ocr_readiness_integration.md` | 活动 | 文档：P27：OCR 决策证据纳入课程资产 readiness。 |
| `p28_evaluation_provenance_readiness.md` | 活动 | 文档：P28：离线评测 provenance 接入课程 readiness。 |
| `p29_evaluation_report_provenance_generation.md` | 活动 | 文档：P29：评测报告 provenance 生成链路。 |
| `p2_learning_metrics.md` | 活动 | 文档：P2 学习反馈与教师统计。 |
| `p30_evaluation_readiness_consistency.md` | 活动 | 文档：P30：评测报告与 readiness 一致性校验。 |
| `p31_evaluation_scope_time_provenance.md` | 活动 | 文档：P31：评测范围与 readiness 时间 provenance。 |
| `p32_evaluation_case_content_fingerprint.md` | 活动 | 文档：P32：评测案例内容 fingerprint。 |
| `p33_evaluation_source_manifest_fingerprint.md` | 活动 | 文档：P33：评测案例源文件 manifest fingerprint。 |
| `p34_evaluation_attachment_manifest_fingerprint.md` | 活动 | 文档：P34：评测案例来源与附件边界。 |
| `p35_evaluation_controlled_attachment_manifest.md` | 活动 | 文档：P35：评测受控附件 manifest。 |
| `p36_local_mock_attachment_adapter.md` | 活动 | 文档：P36：本地 Mock 评测附件适配。 |
| `p37_evaluation_attachment_lifecycle.md` | 活动 | 文档：P37：评测附件本地任务链与生命周期。 |
| `p38_terminal_attachment_cleanup.md` | 活动 | 文档：P38：任务终态附件清理与超时竞态。 |
| `p39_evaluation_attachment_residue_monitoring.md` | 活动 | 文档：P39：评测附件残留监控与受控回收。 |
| `p3_evaluation_observability.md` | 活动 | 文档：P3 评测与可观测性边界。 |
| `p40_task_failure_observability.md` | 活动 | 文档：P40：任务失败与路由聚合可观测性。 |
| `p41_task_latency_observability.md` | 活动 | 文档：P41：任务延迟时间窗口与分位数统计。 |
| `p42_ct_ae_error_pool_teacher_review.md` | 活动 | 文档：P42：CT/AE 错误模板教师证据审核闭环。 |
| `p43_ct_ae_error_pool_promotion_gate.md` | 活动 | 文档：P43：CT/AE 错误模板显式发布闸门。 |
| `p44_ae_structured_validation.md` | 活动 | 文档：P44：AE 结构化条件验证增强。 |
| `p45_ae_small_signal_frequency_validation.md` | 活动 | 文档：P45：AE 小信号与频率条件验证。 |
| `p46_ae_gain_resistance_validation.md` | 活动 | 文档：P46：AE 增益符号与输入/输出电阻验证。 |
| `p47_ae_rule_evidence_audit.md` | 活动 | 文档：P47：AE 课程规则证据覆盖审计。 |
| `p48_ae_teacher_evidence_traceability.md` | 活动 | 文档：P48：AE 教师复核证据可追踪性。 |
| `p49_promotion_evidence_preview.md` | 活动 | 文档：P49：错误模板发布前证据预览。 |
| `p4_course_asset_audit.md` | 活动 | 文档：P4 CT/AE 课程资产审计起点。 |
| `p50_evidence_reference_traceability.md` | 活动 | 文档：P50：教师证据引用可追踪性。 |
| `p51_readiness_evidence_consistency.md` | 活动 | 文档：P51：课程资产 readiness 与教师证据质量一致性。 |
| `p52_ct_rule_evidence_boundary.md` | 活动 | 文档：P52：CT 有限规则证据边界。 |
| `p53_ct_structured_balance_validator.md` | 活动 | 文档：P53：CT 结构化平衡校验器。 |
| `p54_ct_candidate_error_evidence.md` | 活动 | 文档：P54：CT 候选错误签名证据映射。 |
| `p55_teacher_evidence_scope.md` | 活动 | 文档：P55：教师复核证据范围与来源说明。 |
| `p56_readiness_validator_evidence_summary.md` | 活动 | 文档：P56：readiness 校验器证据状态汇总。 |
| `p57_contest_package_consistency_audit.md` | 活动 | 文档：P57：竞赛支撑材料一致性审计。 |
| `p58_readiness_consistency_audit.md` | 活动 | 文档：P58：静态资产与 readiness 一致性审计。 |
| `p59_final_risk_and_acceptance.md` | 活动 | 文档：P59：最终风险清单与可复现验收入口。 |
| `p5_ocr_quality_boundary.md` | 活动 | 文档：P5 OCR 质量边界。 |
| `p60_final_integration.md` | 活动 | 文档：P60：长期维护最终统合。 |
| `p61_contest_scenario_catalog.md` | 活动 | 文档：赛题商业化场景目录与运行契约。 |
| `p63_external_source_registry.md` | 活动 | 文档：外部学术源登记与审查边界。 |
| `p66_scenario_runtime_observability.md` | 活动 | 文档：场景运行时可观测性与性能基准。 |
| `p6_material_review_lifecycle.md` | 活动 | 文档：P6 课程材料教师复核闭环。 |
| `p7_user_feedback_loop.md` | 活动 | 文档：P7 显式用户反馈与运营统计。 |
| `p8_ct_ae_error_templates.md` | 活动 | 文档：P8：CT/AE 错误模板候选与竞赛证据边界。 |
| `p9_course_boundary_audit.md` | 活动 | 文档：P9：知识库课程边界与解析证据审计。 |
| `research_analysis_pilot_input_template.md` | 活动 | 文档：科研数据分析 V2 授权试点输入包模板。 |
| `research_data_analysis_v2_acceptance.md` | 活动 | Markdown 说明文档。 |
| `research_data_analysis_v2_completion_audit.md` | 活动 | 文档：RESEARCH_03_DATA_ANALYSIS_V2 完成审计。 |
| `research_data_analysis_v2_evidence_matrix.md` | 活动 | Markdown 说明文档。 |
| `retest_plan.md` | 活动 | 文档：RetestPlan。 |
| `skill_registry.md` | 活动 | 文档：CT/AE/DE SkillRegistry。 |
| `solution_packet_v1.md` | 活动 | 文档：SolutionPacket v1。 |
| `student_attempt_versioning.md` | 活动 | 文档：StudentAttempt 多版本记录。 |
| `student_verification_v1.md` | 活动 | 文档：StudentVerification V1。 |
| `teaching_state_boundaries.md` | 活动 | 文档：TeachingState、Memory 与 mastery 边界。 |

### `docs/knowledge`

| 文件 | 状态 | 功能 |
|---|---|---|
| `evidence_interaction_guide.md` | 活动 | 文档：证据交互指南。 |
| `knowledge_base_integration_guide.md` | 活动 | 文档：本地多模态知识库构建与接入指南。 |
| `local_knowledge_base_assessment.md` | 活动 | 文档：电路理论、模电、数电本地知识库审计。 |
| `local_knowledge_base_integration.md` | 活动 | 文档：本地知识库接入说明。 |
| `multimodal_rag_integration_guide.md` | 活动 | 文档：多模态 RAG 集成指南。 |
| `rag_debug_site_guide.md` | 活动 | 文档：芯智导学多模态 RAG 调试台使用指南。 |

### `docs/math`

| 文件 | 状态 | 功能 |
|---|---|---|
| `katex_compatibility_report.md` | 活动 | 文档：KaTeX compatibility report。 |
| `math_corpus_audit.md` | 活动 | 文档：Math corpus audit。 |
| `math_rendering_hardening_closeout.md` | 活动 | 文档：Math rendering hardening closeout。 |

### `docs/operations`

| 文件 | 状态 | 功能 |
|---|---|---|
| `芯智导学_Tailscale组员连接操作手册_20260815.docx` | 活动 | 仓库配置、资产或占位文件。 |

### `docs/operations/_qa_tailscale_manual`

| 文件 | 状态 | 功能 |
|---|---|---|
| `芯智导学_Tailscale组员连接操作手册_20260815.pdf` | 活动 | 仓库配置、资产或占位文件。 |

### `docs/operations/_qa_tailscale_manual_v2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `芯智导学_Tailscale组员连接操作手册_20260815.pdf` | 活动 | 仓库配置、资产或占位文件。 |

### `docs/operations/_qa_tailscale_manual_v3`

| 文件 | 状态 | 功能 |
|---|---|---|
| `芯智导学_Tailscale组员连接操作手册_20260815.pdf` | 活动 | 仓库配置、资产或占位文件。 |

### `docs/operations/_qa_tailscale_manual_v5`

| 文件 | 状态 | 功能 |
|---|---|---|
| `team_manual.docx` | 活动 | 仓库配置、资产或占位文件。 |

### `docs/operations/_qa_tailscale_manual_v5/rendered`

| 文件 | 状态 | 功能 |
|---|---|---|
| `page-1.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-2.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-3.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-4.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-5.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-6.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-7.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-8.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-9.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `team_manual.pdf` | 活动 | 仓库配置、资产或占位文件。 |

### `docs/operations/_qa_tailscale_manual_v6`

| 文件 | 状态 | 功能 |
|---|---|---|
| `team_manual.docx` | 活动 | 仓库配置、资产或占位文件。 |

### `docs/operations/_qa_tailscale_manual_v6/rendered`

| 文件 | 状态 | 功能 |
|---|---|---|
| `page-1.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-2.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-3.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-4.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-5.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-6.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-7.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-8.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `page-9.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `team_manual.pdf` | 活动 | 仓库配置、资产或占位文件。 |

### `docs/optimization`

| 文件 | 状态 | 功能 |
|---|---|---|
| `context_memory_performance_v1.md` | 活动 | 文档：耗时、记忆与上下文管理优化记录。 |
| `latest_retest_followup_20260729.md` | 活动 | 文档：100 例重点重测后续优化记录（2026-07-29）。 |
| `pending_issues_2026-08-22.md` | 活动 | 文档：问题待解清单（2026-08-22）。 |
| `real_model_first_improvement_plan_2026-08-22.md` | 活动 | 文档：芯智导学真实模型优先改进任务单。 |
| `targeted_retest_optimization_v2.md` | 活动 | 文档：100 例定向重测问题总结与第二轮优化。 |
| `targeted_solver_audit_v1.md` | 活动 | 文档：统一学术求解器定向审计 v1。 |
| `targeted_solver_implementation_v1.md` | 活动 | 文档：统一学术求解器定向优化实施说明 v1。 |
| `targeted_solver_test_report_v1.md` | 活动 | 文档：统一学术求解器定向测试报告 v1。 |
| `team_feedback_31_edge_acceptance_2026-08-21.md` | 活动 | 文档：组员反馈 31 场景 Edge 全流程验收记录。 |
| `team_feedback_31_scenario_ledger.md` | 活动 | 文档：组员反馈 31 个场景长期改造台账。 |

### `docs/phaseB_planner_upgrade`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_PHASE_B_MASTER_GOAL.md` | 活动 | 文档：芯智导学 Phase B 总目标：Planner + Canonical Plan 引入。 |
| `B0_contract_and_baseline_freeze.md` | 活动 | 文档：Phase B0：Contract 与 Baseline 冻结。 |
| `B1_planner_contract_and_owner.md` | 活动 | 文档：Phase B1：Planner Contract 与唯一 Owner 建立。 |
| `B2_canonical_plan_and_adapter.md` | 活动 | 文档：Phase B2：Canonical Plan 与 Runtime Adapter。 |
| `B3_planner_shadow_mode.md` | 活动 | 文档：Phase B3：Planner Shadow Mode 接入。 |
| `B4_shadow_evaluation_and_lineage.md` | 活动 | 文档：Phase B4：Shadow Evaluation、Parity 与 Lineage 对账。 |
| `B5_planner_canary_takeover.md` | 活动 | 文档：Phase B5：Planner Canary 接管。 |
| `B6_overall_router_retirement_and_closeout.md` | 活动 | 文档：Phase B6：Overall Router 退出与 Phase B 收尾。 |
| `STATUS.md` | 活动 | 文档：Phase B Execution Status。 |

### `docs/phaseC_skill_framework`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_PHASE_C_MASTER_GOAL.md` | 活动 | 文档：芯智导学 Phase C 总目标：Skill Framework。 |
| `C0_repository_sync_and_phase_b_checkpoint.md` | 活动 | 文档：Phase C0：Repository Sync 与 Phase B GitHub Checkpoint。 |
| `C1_existing_skill_audit_and_contract.md` | 活动 | 文档：Phase C1：现有 Skill 审计与 Contract 定义。 |
| `C2_skill_registry_consolidation.md` | 活动 | 文档：Phase C2：Skill Registry 收敛。 |
| `C3_skill_retriever_and_policy.md` | 活动 | 文档：Phase C3：SkillRetriever 与 SkillPolicy。 |
| `C4_planner_skill_shadow_integration.md` | 活动 | 文档：Phase C4：Planner × Skill Shadow Integration。 |
| `C5_runtime_skill_binding.md` | 活动 | 文档：Phase C5：Runtime Skill Binding。 |
| `C6_skill_evaluation_and_controlled_canary.md` | 活动 | 文档：Phase C6：Skill Evaluation 与 Controlled Canary。 |
| `C7_phase_c_closeout.md` | 活动 | 文档：Phase C7：Phase C Closeout。 |

### `docs/phaseD_reflection_framework`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_PHASE_D_MASTER_GOAL.md` | 活动 | 文档：芯智导学 Phase D 总目标：Reflection / Critic / Bounded Revision。 |
| `D0_phase_c_release_checkpoint.md` | 活动 | 文档：Phase D0：Phase C Release Checkpoint。 |
| `D1_existing_verification_audit_and_reflection_contract.md` | 活动 | 文档：Phase D1：现有 Verification 审计与 Reflection Contract。 |
| `D2_reflection_policy_and_trigger.md` | 活动 | 文档：Phase D2：ReflectionPolicy 与触发策略。 |
| `D3_critic_shadow_mode.md` | 活动 | 文档：Phase D3：Critic Shadow Mode。 |
| `D4_bounded_revision_integration.md` | 活动 | 文档：Phase D4：Bounded Revision 集成。 |
| `D5_verification_and_publish_gate_integration.md` | 活动 | 文档：Phase D5：Verification 与 Publish Gate 融合。 |
| `D6_reflection_evaluation_and_controlled_canary.md` | 活动 | 文档：Phase D6：Reflection Evaluation 与 Controlled Canary。 |
| `D7_phase_d_closeout_and_git_release.md` | 活动 | 文档：Phase D7：Phase D Closeout 与 Git Release。 |

### `docs/phaseE_experience_memory`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_PHASE_E_MASTER_GOAL.md` | 活动 | 文档：芯智导学 Phase E 总目标：Experience Memory。 |
| `E0_phase_d_release_checkpoint.md` | 活动 | 文档：Phase E0：Phase D Release Checkpoint。 |
| `E1_memory_and_trace_audit.md` | 活动 | 文档：Phase E1：Memory / Trace / Evaluation 现状审计。 |
| `E2_experience_record_and_governance_contract.md` | 活动 | 文档：Phase E2：ExperienceRecord 与治理 Contract。 |
| `E3_experience_write_and_promotion_pipeline.md` | 活动 | 文档：Phase E3：Experience Write 与 Promotion Pipeline。 |
| `E4_experience_retriever_and_planner_shadow.md` | 活动 | 文档：Phase E4：ExperienceRetriever 与 Planner Shadow。 |
| `E5_controlled_planner_prior_integration.md` | 活动 | 文档：Phase E5：Controlled Planner Prior Integration。 |
| `E6_experience_evaluation_privacy_and_forgetting.md` | 活动 | 文档：Phase E6：Experience Evaluation、Privacy、Conflict 与 Forget。 |
| `E7_phase_e_closeout_and_git_release.md` | 活动 | 文档：Phase E7：Phase E Closeout 与 Git Release。 |

### `docs/phaseF_evaluation_loop`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_PHASE_F_MASTER_GOAL.md` | 活动 | 文档：芯智导学 Phase F 总目标：Evaluation → Failure Analysis → Improvement Proposal → Offline Replay → Promotion。 |
| `F0_phase_e_release_checkpoint.md` | 活动 | 文档：Phase F0：Phase E Release Checkpoint。 |
| `F1_existing_evaluation_audit_and_contract.md` | 活动 | 文档：Phase F1：现有 Evaluation 审计与统一 Contract。 |
| `F2_trace_level_scoring_and_failure_taxonomy.md` | 活动 | 文档：Phase F2：Trace-level Scoring 与 Failure Taxonomy。 |
| `F3_failure_attribution_and_pattern_aggregation.md` | 活动 | 文档：Phase F3：Failure Attribution 与 Pattern Aggregation。 |
| `F4_improvement_proposal_framework.md` | 活动 | 文档：Phase F4：Improvement Proposal Framework。 |
| `F5_offline_replay_and_counterfactual_evaluation.md` | 活动 | 文档：Phase F5：Offline Replay 与 Counterfactual Evaluation。 |
| `F6_experience_and_promotion_governance.md` | 活动 | 文档：Phase F6：Promotion Governance 与 Experience 对接。 |
| `F7_full_suite_and_real_evidence_campaign.md` | 活动 | 文档：Phase F7：Full Suite 与真实 Evidence Campaign。 |
| `F8_phase_f_closeout_and_git_release.md` | 活动 | 文档：Phase F8：Phase F Closeout 与 Git Release。 |

### `docs/pilot`

| 文件 | 状态 | 功能 |
|---|---|---|
| `p1_failure_attribution.md` | 活动 | 文档：P1 真实问题归因：Top 15 Failure Patterns。 |
| `p2_critical_fixes.md` | 活动 | 文档：P2 Critical Product Fixes。 |
| `pilot0_case_manifest.md` | 活动 | 文档：Pilot 0 Case Manifest。 |
| `pilot0_summary.md` | 活动 | 文档：Phase P Pilot 0 证据冻结摘要。 |
| `pilot_data_collection_guide.md` | 活动 | 文档：Pilot 数据采集说明。 |

### `docs/post_phase_f_roadmap`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_POST_F_MASTER_ROADMAP.md` | 活动 | 文档：芯智导学 Phase F 之后总路线：从架构收口进入大规模实测与迭代。 |
| `01_OVERNIGHT_EXECUTION_RULES.md` | 活动 | 文档：Codex 半夜无人值守执行总规则。 |
| `G_REAL_PROVIDER_BASELINE.md` | 活动 | 文档：Phase G：真实 Provider Baseline 与 Benchmark Harness。 |
| `H_LARGE_SCALE_BENCHMARK.md` | 活动 | 文档：Phase H：大规模 Benchmark Campaign。 |
| `I_FAILURE_DRIVEN_OPTIMIZATION.md` | 活动 | 文档：Phase I：Failure-driven Targeted Optimization。 |
| `J_ROBUSTNESS_STRESS_REGRESSION.md` | 活动 | 文档：Phase J：Robustness / Stress / Regression。 |
| `K_FINAL_RELEASE_ACCEPTANCE.md` | 活动 | 文档：Phase K：Final Acceptance / Release Candidate。 |
| `L_CONTINUOUS_ITERATION_PLAYBOOK.md` | 活动 | 文档：Phase K 之后：长期 Iteration Playbook。 |

### `docs/presentations`

| 文件 | 状态 | 功能 |
|---|---|---|
| `xinzhi_project_meeting_20260723.html` | 活动 | 静态前端页面：芯智导学｜项目进展、架构与下一阶段计划。 |

### `docs/quality`

| 文件 | 状态 | 功能 |
|---|---|---|
| `bug_backlog.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、last_updated、owner、source_protocol、entries。 |
| `long_term_verification_and_bug_triage.md` | 活动 | 文档：长期检测、回归测试与 Bug 定位工作协议。 |

### `docs/refactor`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agent_layer_policy.md` | 活动 | 文档：Agent 层级策略。 |
| `overall_router_migration.md` | 活动 | 文档：OverallRoutingService 迁移边界。 |
| `plan_boundary_design.md` | 活动 | 文档：Plan 边界设计。 |
| `state_ownership.md` | 活动 | 文档：Context 与 State 所有权。 |
| `supervisor_consolidation.md` | 活动 | 文档：Supervisor 职责收敛。 |
| `task_router_freeze.md` | 活动 | 文档：TaskRouter 冻结与 Preflight 边界。 |

### `docs/release`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_AGENTIC_V1_RC.md` | 活动 | 文档：芯智导学 Agentic v1.0 Release Candidate。 |
| `architecture_overview.md` | 活动 | 文档：Architecture Overview。 |
| `benchmark_results.md` | 活动 | 文档：Benchmark Results。 |
| `demo_cases.md` | 活动 | 文档：Demo Cases。 |
| `evaluation_methodology.md` | 活动 | 文档：Evaluation Methodology。 |
| `execution_surface_and_circuit_release_plan.md` | 活动 | 文档：Execution Surface Stable + Circuit Capability Release Plan。 |
| `failure_driven_optimization.md` | 活动 | 文档：Failure-driven Optimization。 |
| `known_limitations.md` | 活动 | 文档：Known Limitations。 |
| `pilot_validation_report.md` | 活动 | 文档：Phase P Pilot Validation Report。 |
| `safety_governance.md` | 活动 | 文档：Safety and Governance。 |
| `team_handoff.md` | 活动 | 文档：Phase P Team Handoff。 |

### `docs/reports`

| 文件 | 状态 | 功能 |
|---|---|---|
| `retrieval_baseline_comparison.md` | 活动 | 文档：阶段 1.6 本地检索基线对比。 |

### `docs/reviews`

| 文件 | 状态 | 功能 |
|---|---|---|
| `automatic_routing_test_report.md` | 活动 | 文档：自动路由测试报告。 |
| `cloud_learn_rag_e2e_report.md` | 活动 | 文档：Cloud LEARN RAG 端到端实测报告。 |
| `completed_workflow_integration_report.md` | 活动 | 文档：已完成工作流接入审计报告。 |
| `internal_agent_model_evaluation_report.md` | 活动 | 文档：内部模型 Agent 首轮评测报告。 |
| `knowledge_base_audit_report.md` | 活动 | 文档：本地知识库审计报告。 |
| `local_latency_optimization_report.md` | 活动 | 文档：本地延迟优化报告。 |
| `local_routing_latency_report.md` | 活动 | 文档：本地自动调度延迟报告。 |
| `multi_agent_compatibility_report.md` | 活动 | 文档：多 Agent 兼容性报告。 |
| `multimodal_rag_implementation_report.md` | 活动 | 文档：多模态 RAG 实施报告。 |
| `rag_debug_site_screenshot.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `rag_quality_improvement_report.md` | 活动 | 文档：RAG 质量改进报告。 |
| `workflow_rag_integration_report.md` | 活动 | 文档：工作流与 RAG 融合实施报告。 |

### `docs/testing`

| 文件 | 状态 | 功能 |
|---|---|---|
| `known_baseline_failures.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、captured_at、policy、failures。 |
| `t0_baseline_freeze.md` | 活动 | 文档：T0：测试环境与数据基线冻结。 |
| `t1_336_full_baseline.md` | 活动 | 文档：T1：336-case 当前架构全量 Baseline。 |
| `t2_failure_analysis.md` | 活动 | 文档：T2：Failure Attribution 与 Top Failure Patterns。 |
| `t3_targeted_suites.md` | 活动 | 文档：T3：Targeted 专项测试集建设报告。 |
| `t4_optimization_replay.md` | 活动 | 文档：T4 定向优化 Replay / Counterfactual Test。 |
| `t5_expanded_benchmark.md` | 活动 | 文档：T5：Expanded Benchmark V2。 |

### `docs/workflows`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agent_contract_reference.md` | 活动 | 文档：Agent 契约参考。 |
| `agent_scaffold_guide.md` | 活动 | 文档：Agent 脚手架指南。 |
| `development_mock_agent_guide.md` | 活动 | 文档：开发态 Mock Agent 指南。 |
| `new_agent_integration_guide.md` | 活动 | 文档：新 Agent 接入指南。 |
| `workflow_input_contracts.md` | 活动 | 文档：工作流输入契约。 |
| `workflow_output_validation_guide.md` | 活动 | 文档：工作流输出校验与展示指南。 |

### `docs/xinzhi_8h_soak_boundary_quality_v1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01_test_governance_and_baseline.md` | 活动 | 文档：01 测试治理与基线冻结。 |
| `02_8h_execution_schedule.md` | 活动 | 文档：02 至少 8 小时执行时间表。 |
| `03_browser_visual_quality.md` | 活动 | 文档：03 浏览器视觉质量专项。 |
| `04_latex_katex_torture_test.md` | 活动 | 文档：04 LaTeX / KaTeX Torture Test。 |
| `05_backend_latency_resource_metrics.md` | 活动 | 文档：05 后端耗时与资源专项。 |
| `06_six_scenario_targeted_tests.md` | 活动 | 文档：06 六案例专项测试。 |
| `07_circuit_rendering_stress.md` | 活动 | 文档：07 Circuit Rendering 强化专项。 |
| `08_multimodal_boundary.md` | 活动 | 文档：08 多模态与附件边界。 |
| `09_long_context_session_stress.md` | 活动 | 文档：09 长对话、Session 与纠错压力。 |
| `10_restart_failure_chaos.md` | 活动 | 文档：10 Restart / Failure / Recovery 专项。 |
| `11_same_question_repeatability.md` | 活动 | 文档：11 同题重复稳定性。 |
| `12_fix_policy_no_patch_no_rewrite.md` | 活动 | 文档：12 问题修复政策：不补丁、不重写主线。 |
| `13_final_release_gate.md` | 活动 | 文档：13 最终 Release Gate。 |
| `14_codex_master_instruction.md` | 活动 | 文档：Codex 总执行指令：8+ 小时持续稳定性与边界验收。 |
| `README.md` | 活动 | 文档：芯智导学：8+ 小时持续稳定性、边界能力与浏览器质量验收 v1。 |

### `docs/xinzhi_answer_quality_browser_hardening`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01_browser_first_acceptance.md` | 活动 | 文档：01 Browser-First 验收制度。 |
| `02_answer_quality_contract.md` | 活动 | 文档：02 回答质量合同。 |
| `03_degradation_policy_rework.md` | 活动 | 文档：03 降级策略专项重构。 |
| `04_review_policy_rework.md` | 活动 | 文档：04 waiting_review 与人工审批策略专项。 |
| `05_same_question_stability.md` | 活动 | 文档：05 同题稳定性专项。 |
| `06_browser_real_world_case_matrix.md` | 活动 | 文档：06 浏览器真实用户问题矩阵。 |
| `07_quality_fix_rules.md` | 活动 | 文档：07 回答质量修复规则。 |
| `08_final_browser_regression_and_commit.md` | 活动 | 文档：08 最终浏览器回归与 Git 提交。 |
| `09_codex_master_instruction.md` | 活动 | 文档：Codex 总执行指令：浏览器真实体验与回答质量专项。 |
| `README.md` | 活动 | 文档：芯智导学：浏览器真实体验与回答质量专项加固。 |

### `docs/xinzhi_capability_quality_hardening`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01_local_asset_discovery.md` | 活动 | 文档：01 本地题库与电路图资产发现。 |
| `02_multimodal_semantic_hardening.md` | 活动 | 文档：02 多图语义可靠性专项。 |
| `03_long_context_memory_hardening.md` | 活动 | 文档：03 长上下文、WorkingState 与记忆专项。 |
| `04_general_answer_and_data_analysis_merge.md` | 活动 | 文档：04 通用回答与数据分析能力收敛。 |
| `05_semantic_validator_and_benchmark.md` | 活动 | 文档：05 Semantic Validator 与专业 Benchmark。 |
| `06_framework_fix_rules.md` | 活动 | 文档：06 框架级修复规则。 |
| `07_regression_and_commit.md` | 活动 | 文档：07 回归、收口与 Git 提交。 |
| `08_codex_master_instruction.md` | 活动 | 文档：Codex 下一阶段总执行指令。 |
| `README.md` | 活动 | 文档：芯智导学：能力质量专项加固包。 |

### `docs/xinzhi_full_testing_roadmap`

| 文件 | 状态 | 功能 |
|---|---|---|
| `00_TESTING_MASTER_ROADMAP.md` | 活动 | 文档：芯智导学完整测试路线总规划。 |
| `10_LONG_TERM_ITERATION_TESTING.md` | 活动 | 文档：长期测试迭代机制。 |
| `11_CODEX_NIGHT_EXECUTION_INSTRUCTION.md` | 活动 | 文档：Codex 全测试阶段执行总指令。 |
| `T0_BASELINE_AND_DATA_FREEZE.md` | 活动 | 文档：T0：测试环境与数据基线冻结。 |
| `T1_336_FULL_BASELINE.md` | 活动 | 文档：T1：336-case 当前架构全量 Baseline。 |
| `T2_FAILURE_ANALYSIS.md` | 活动 | 文档：T2：Failure Attribution 与 Top Failure Patterns。 |
| `T3_TARGETED_TEST_SUITES.md` | 活动 | 文档：T3：Targeted 专项测试集建设。 |
| `T4_OPTIMIZATION_REPLAY.md` | 活动 | 文档：T4：定向优化 Replay / Counterfactual Test。 |
| `T5_EXPANDED_BENCHMARK.md` | 活动 | 文档：T5：Expanded Benchmark 500–800 cases。 |
| `T6_HIDDEN_HOLDOUT.md` | 活动 | 文档：T6：Hidden Holdout 泛化测试。 |
| `T7_ROBUSTNESS_AND_STRESS.md` | 活动 | 文档：T7：Robustness / Fault / Stress Test。 |
| `T8_REAL_PROVIDER_EVAL.md` | 活动 | 文档：T8：Real Provider Controlled Evaluation。 |
| `T9_FINAL_ACCEPTANCE.md` | 活动 | 文档：T9：Final Acceptance Benchmark。 |

### `docs/xinzhi_harness_maturity_circuit_v1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01_H0_baseline_freeze.md` | 活动 | 文档：H0：冻结 5cb699c 稳定基线。 |
| `02_H1_trace_projection.md` | 活动 | 文档：H1：Unified Trace / Span Projection。 |
| `03_H2_semantic_eval.md` | 活动 | 文档：H2：Semantic Eval Harness。 |
| `04_H3_capability_spec.md` | 活动 | 文档：H3：CapabilitySpec Metadata 增强。 |
| `05_C0_circuit_standalone_baseline.md` | 活动 | 文档：C0：Circuit Rendering Standalone Baseline。 |
| `06_C1_circuit_runtime_off_on.md` | 活动 | 文档：C1：Circuit Tool 接 Runtime，先 OFF / ON。 |
| `07_C2_svg_artifact.md` | 活动 | 文档：C2：SVG Artifact 集成。 |
| `08_C3_auto_policy_plan_pattern.md` | 活动 | 文档：C3：AUTO Render + Plan Pattern。 |
| `09_C4_browser_product_acceptance.md` | 活动 | 文档：C4：Circuit Browser Product Acceptance。 |
| `10_H4_tool_guard_pilot.md` | 活动 | 文档：H4：Tool Guard Pilot（仅 Circuit）。 |
| `11_final_regression_release_gate.md` | 活动 | 文档：R：最终回归与 Release Gate。 |
| `12_git_commit_and_rollback_policy.md` | 活动 | 文档：Git Commit 与回滚纪律。 |
| `13_codex_master_instruction.md` | 活动 | 文档：Codex 总执行指令。 |
| `README.md` | 活动 | 文档：芯智导学：Harness Maturity + Circuit Rendering Integration v1。 |

### `docs/xinzhi_tonight_global_hardening`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01_framework_gap_audit.md` | 活动 | 文档：01 全局框架漏洞审计任务。 |
| `02_global_fix_execution_plan.md` | 活动 | 文档：02 全局性修复执行计划。 |
| `03_extended_real_world_scenarios.md` | 活动 | 文档：03 真实用户问答场景扩展矩阵。 |
| `04_multimodal_memory_intelligence_hardening.md` | 活动 | 文档：04 多模态、记忆与回答智能性加固。 |
| `05_regression_quality_gates.md` | 活动 | 文档：05 全局回归与质量门禁。 |
| `06_git_commit_closeout.md` | 活动 | 文档：06 Git 提交与今晚收口要求。 |
| `07_codex_master_instruction.md` | 活动 | 文档：07 给 Codex 的今晚总指令。 |
| `README.md` | 活动 | 文档：芯智导学：今晚全局可靠性加固目标包。 |

### `evaluation`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 活动 | 文档：Evaluation assets。 |

### `evaluation/automatic_routing`

| 文件 | 状态 | 功能 |
|---|---|---|
| `cases.json` | 活动 | 结构化数据集；包含 70 个顶层条目。 |

### `evaluation/baselines`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agentic_v1_real_baseline.json` | 活动 | 结构化配置或数据；顶层字段：schema_version、baseline_id、generated_at、evidence_level、real_provider_status、dataset。 |
| `current_system_manifest.json` | 活动 | 结构化配置或数据；顶层字段：schema_version、captured_at、repository、evaluation_dataset、component_versions、provider_and_model。 |

### `evaluation/cases/academic_solver`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ae.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |
| `ct.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |
| `de.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |
| `ss.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |

### `evaluation/cases/agent_runtime`

| 文件 | 状态 | 功能 |
|---|---|---|
| `synthetic_runtime.yaml` | 活动 | 结构化配置或数据；顶层字段：dataset、metrics、cases。 |

### `evaluation/cases/boundary`

| 文件 | 状态 | 功能 |
|---|---|---|
| `insufficient_and_misroute.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |

### `evaluation/cases/commercial_scenarios`

| 文件 | 状态 | 功能 |
|---|---|---|
| `six_scenarios.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |

### `evaluation/cases/contest_scenarios`

| 文件 | 状态 | 功能 |
|---|---|---|
| `synthetic_contest.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |

### `evaluation/cases/expanded_benchmark_v2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `expanded.yaml` | 活动 | 结构化配置或数据文件（内容需由对应加载器校验）。 |

### `evaluation/cases/expanded_benchmark_v2/attachments`

| 文件 | 状态 | 功能 |
|---|---|---|
| `diagram_00.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `diagram_01.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `diagram_02.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `diagram_03.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `diagram_04.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `diagram_05.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `diagram_06.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `diagram_07.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `evaluation/cases/knowledge_qa`

| 文件 | 状态 | 功能 |
|---|---|---|
| `electronic_courses.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |

### `evaluation/cases/learning_loop/CT`

| 文件 | 状态 | 功能 |
|---|---|---|
| `synthetic_learning.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |

### `evaluation/cases/task_reliability`

| 文件 | 状态 | 功能 |
|---|---|---|
| `synthetic_reliability.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |

### `evaluation/cases/teaching_foundation`

| 文件 | 状态 | 功能 |
|---|---|---|
| `synthetic_phase1.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |

### `evaluation/cases/teaching_loop_phase2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `synthetic_phase2.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |

### `evaluation/cases/teaching_loop_phase3`

| 文件 | 状态 | 功能 |
|---|---|---|
| `synthetic_phase3.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |

### `evaluation/circuit_theory`

| 文件 | 状态 | 功能 |
|---|---|---|
| `benchmark_manifest.json` | 活动 | 结构化配置或数据；顶层字段：benchmark_id、course_id、solver_id、version、case_groups、metrics。 |
| `README.md` | 活动 | 文档：电路理论回归评测脚手架。 |
| `regression_report_template.md` | 活动 | 文档：Academic Solver 电路理论回归报告。 |

### `evaluation/circuit_theory/cases/easy`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.gitkeep` | 活动 | 保留空目录结构的占位文件。 |
| `CT_EASY_001.sample.json` | 活动 | 结构化配置或数据；顶层字段：case_id、difficulty、input_type、question、attachments、expected。 |

### `evaluation/circuit_theory/cases/hard`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.gitkeep` | 活动 | 保留空目录结构的占位文件。 |
| `CT_HARD_001.sample.json` | 活动 | 结构化配置或数据；顶层字段：case_id、difficulty、input_type、question、attachments、expected。 |

### `evaluation/circuit_theory/cases/image`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.gitkeep` | 活动 | 保留空目录结构的占位文件。 |
| `CT_IMAGE_001.template.json` | 活动 | 结构化配置或数据；顶层字段：case_id、difficulty、input_type、question、attachments、expected。 |

### `evaluation/circuit_theory/cases/medium`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.gitkeep` | 活动 | 保留空目录结构的占位文件。 |
| `CT_MEDIUM_001.sample.json` | 活动 | 结构化配置或数据；顶层字段：case_id、difficulty、input_type、question、attachments、expected。 |

### `evaluation/circuit_theory/schemas`

| 文件 | 状态 | 功能 |
|---|---|---|
| `benchmark_case.schema.json` | 活动 | 结构化配置或数据；顶层字段：$schema、title、type、required、properties。 |

### `evaluation/circuit_theory/scripts`

| 文件 | 状态 | 功能 |
|---|---|---|
| `run_mock_benchmark.py` | 活动 | Python 模块；定义 wait_for_terminal、main。 |
| `summarize_results.py` | 活动 | Python 模块；定义 main。 |
| `validate_cases.py` | 活动 | Python 模块；定义 validate_case、main。 |

### `evaluation/demo_cases`

| 文件 | 状态 | 功能 |
|---|---|---|
| `demo_run_report.md` | 活动 | 文档：阶段 2.1 演示运行记录。 |
| `image_cases.md` | 活动 | 文档：单图片题演示案例。 |
| `text_cases.md` | 活动 | 文档：文字题演示案例。 |

### `evaluation/knowledge_retrieval`

| 文件 | 状态 | 功能 |
|---|---|---|
| `benchmark_manifest.json` | 活动 | 结构化配置或数据；顶层字段：name、status、courses、minimum_cases_per_course、metrics、runs。 |
| `README.md` | 活动 | 文档：三课程本地检索评测草稿。 |

### `evaluation/knowledge_retrieval/cases/AE`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE_RET_001.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `AE_RET_002.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `AE_RET_003.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `AE_RET_004.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `AE_RET_005.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |

### `evaluation/knowledge_retrieval/cases/CT`

| 文件 | 状态 | 功能 |
|---|---|---|
| `CT_RET_001.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `CT_RET_002.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `CT_RET_003.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `CT_RET_004.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `CT_RET_005.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |

### `evaluation/knowledge_retrieval/cases/DE`

| 文件 | 状态 | 功能 |
|---|---|---|
| `DE_RET_001.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `DE_RET_002.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `DE_RET_003.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `DE_RET_004.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |
| `DE_RET_005.json` | 活动 | 结构化配置或数据；顶层字段：case_id、course_id、query、expected_sources、forbidden_courses、tags。 |

### `evaluation/knowledge_retrieval/results`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.gitkeep` | 活动 | 保留空目录结构的占位文件。 |
| `baseline_lexical_v1.json` | 活动 | 结构化配置或数据；顶层字段：run_id、retrieval_mode、generated_at、case_status、case_count、corpus。 |
| `local_lexical_v2.json` | 活动 | 结构化配置或数据；顶层字段：run_id、retrieval_mode、generated_at、case_status、case_count、corpus。 |

### `evaluation/knowledge_retrieval/schemas`

| 文件 | 状态 | 功能 |
|---|---|---|
| `retrieval_case.schema.json` | 活动 | 结构化配置或数据；顶层字段：$schema、title、type、additionalProperties、required、properties。 |

### `evaluation/knowledge_retrieval/scripts`

| 文件 | 状态 | 功能 |
|---|---|---|
| `compare_runs.py` | 活动 | Python 模块；定义 main。 |
| `run_retrieval_benchmark.py` | 活动 | Python 模块；定义 discover_path、load_cases、portable_corpus_path、percentile_95、percentile_50 等。 |
| `summarize_results.py` | 活动 | Python 模块；定义 main。 |
| `validate_cases.py` | 活动 | Python 模块；定义 validate_case、main。 |

### `evaluation/manifests`

| 文件 | 状态 | 功能 |
|---|---|---|
| `dataset_manifest.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、datasets。 |

### `evaluation/math`

| 文件 | 状态 | 功能 |
|---|---|---|
| `katex_render_failures.jsonl` | 活动 | 仓库配置、资产或占位文件。 |
| `math_corpus_failures.jsonl` | 活动 | 仓库配置、资产或占位文件。 |
| `math_corpus_inventory.json` | 活动 | 结构化配置或数据；顶层字段：schema_version、source_root、markdown_count、formula_count、formula_counts、risk_counts。 |
| `math_corpus_samples.jsonl` | 活动 | 仓库配置、资产或占位文件。 |

### `evaluation/math_circuit`

| 文件 | 状态 | 功能 |
|---|---|---|
| `performance_baseline.json` | 活动 | 结构化配置或数据；顶层字段：schema_version、source_root、math_formula_count、corpus_scan_ms、math_normalization_ms、circuit_fixture_count。 |

### `evaluation/model_agents`

| 文件 | 状态 | 功能 |
|---|---|---|
| `cases.yaml` | 活动 | 结构化配置或数据；顶层字段：cases。 |

### `evaluation/private_cases`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 活动 | 文档：私有评测数据目录。 |

### `evaluation/rubrics`

| 文件 | 状态 | 功能 |
|---|---|---|
| `default.yaml` | 活动 | 结构化配置或数据；顶层字段：version、description、weights。 |

### `evaluation/runtime_cases`

| 文件 | 状态 | 功能 |
|---|---|---|
| `academic_solver_parity_manifest_v1.json` | 活动 | 结构化配置或数据；顶层字段：suite_version、suite_id、purpose、thresholds、case_profiles、data_policy。 |
| `academic_solver_v1.json` | 活动 | 结构化配置或数据；顶层字段：case_version、case_id、expected_status、required_node_statuses、required_handler_ids、max_iterations。 |
| `general_question_v1.json` | 活动 | 结构化配置或数据；顶层字段：case_version、case_id、expected_status、required_node_statuses、required_handler_ids、max_iterations。 |
| `research_analysis_v1.json` | 活动 | 结构化配置或数据；顶层字段：case_version、case_id、expected_status、required_node_statuses、required_handler_ids、max_iterations。 |
| `runtime_plan_proposals_v2.json` | 活动 | 结构化配置或数据；顶层字段：suite_id、suite_version、require_semantic_alignment、cases。 |

### `evaluation/schemas`

| 文件 | 状态 | 功能 |
|---|---|---|
| `evaluation_case.schema.json` | 活动 | 结构化配置或数据；顶层字段：$schema、title、type、required、properties、additionalProperties。 |
| `evaluation_rubric.schema.json` | 活动 | 结构化配置或数据；顶层字段：$schema、title、type、properties、additionalProperties。 |

### `evaluation/targeted`

| 文件 | 状态 | 功能 |
|---|---|---|
| `generation_verification_contracts.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、suite_id、title、source_catalog、source_catalog_scope、evidence_level。 |
| `routing_boundary_learning.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、suite_id、title、source_catalog、source_catalog_scope、evidence_level。 |
| `task_creation_idempotency.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、suite_id、title、source_catalog、source_catalog_scope、evidence_level。 |
| `teaching_timeout_recovery.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、suite_id、title、source_catalog、source_catalog_scope、evidence_level。 |
| `tool_boundary_selection.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、suite_id、title、source_catalog、source_catalog_scope、evidence_level。 |
| `visual_fixture_acceptance.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、suite_id、title、source_catalog、source_catalog_scope、evidence_level。 |

### `infra/searxng`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.env.example` | 活动 | 仓库配置、资产或占位文件。 |
| `docker-compose.yml` | 活动 | 结构化配置或数据；顶层字段：name、services、volumes。 |
| `README.md` | 活动 | 文档：Local SearXNG。 |

### `infra/searxng/core-config`

| 文件 | 状态 | 功能 |
|---|---|---|
| `settings.yml` | 活动 | 结构化配置或数据；顶层字段：use_default_settings、general、search、server、valkey、outgoing。 |

### `knowledge_config`

| 文件 | 状态 | 功能 |
|---|---|---|
| `knowledge_base_index_config.example.yaml` | 活动 | 结构化配置或数据；顶层字段：version、multimodal_level、sources、parsing、retrieval、images。 |
| `README.md` | 活动 | 文档：本地知识库元数据覆盖层。 |

### `knowledge_config/corrections`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE.yaml` | 活动 | 结构化配置或数据；顶层字段：rules。 |
| `COMM.yaml` | 活动 | 结构化配置或数据；顶层字段：rules。 |
| `CT.yaml` | 活动 | 结构化配置或数据；顶层字段：rules。 |
| `DE.yaml` | 活动 | 结构化配置或数据；顶层字段：rules。 |
| `DSP.yaml` | 活动 | 结构化配置或数据；顶层字段：rules。 |
| `SS.yaml` | 活动 | 结构化配置或数据；顶层字段：rules。 |

### `knowledge_config/courses`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE.yaml` | 活动 | 结构化配置或数据；顶层字段：course_id、course_name、document_patterns、chapter_aliases、excluded_paths。 |
| `COMM.yaml` | 活动 | 结构化配置或数据；顶层字段：course_id、course_name、document_patterns、chapter_aliases、excluded_paths。 |
| `CT.yaml` | 活动 | 结构化配置或数据；顶层字段：course_id、course_name、document_patterns、chapter_aliases、retrieval_topic_boosts、excluded_paths。 |
| `DE.yaml` | 活动 | 结构化配置或数据；顶层字段：course_id、course_name、document_patterns、chapter_aliases、retrieval_topic_boosts、excluded_paths。 |
| `DSP.yaml` | 活动 | 结构化配置或数据；顶层字段：course_id、course_name、document_patterns、chapter_aliases、excluded_paths。 |
| `SS.yaml` | 活动 | 结构化配置或数据；顶层字段：course_id、course_name、document_patterns、chapter_aliases、excluded_paths。 |

### `knowledge_config/synonyms`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE.yaml` | 活动 | 结构化配置或数据；顶层字段：运算放大器、负反馈、场效应管、滤波器。 |
| `COMM.yaml` | 活动 | 结构化配置或数据；顶层字段：加性高斯白噪声、信噪比、误码率、脉冲编码调制、正交振幅调制。 |
| `CT.yaml` | 活动 | 结构化配置或数据；顶层字段：戴维南、结点、相量、互感、串联谐振。 |
| `DE.yaml` | 活动 | 结构化配置或数据；顶层字段：触发器、施密特触发电路、回差电压、卡诺图、传输门、格雷码。 |
| `DSP.yaml` | 活动 | 结构化配置或数据；顶层字段：离散傅里叶变换、快速傅里叶变换、有限冲激响应、无限冲激响应、Z变换。 |
| `SS.yaml` | 活动 | 结构化配置或数据；顶层字段：线性时不变系统、卷积、傅里叶变换、拉普拉斯变换、Z变换。 |

### `local_knowledge`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 活动 | 文档：本地知识库挂载点。 |

### `local_knowledge/AE`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.gitkeep` | 活动 | 保留空目录结构的占位文件。 |

### `local_knowledge/COMM`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.gitkeep` | 活动 | 保留空目录结构的占位文件。 |

### `local_knowledge/CT`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.gitkeep` | 活动 | 保留空目录结构的占位文件。 |

### `local_knowledge/DE`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.gitkeep` | 活动 | 保留空目录结构的占位文件。 |

### `local_knowledge/DSP`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.gitkeep` | 活动 | 保留空目录结构的占位文件。 |

### `local_knowledge/SS`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.gitkeep` | 活动 | 保留空目录结构的占位文件。 |

### `scripts`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Repository automation helpers that are importable by tests. |
| `agent_cli.py` | 活动 | Python 模块；定义 _print、_summary、_dry_run、build_parser、_csv 等。 |
| `analyze_runtime_browser_acceptance.py` | 活动 | Aggregate redacted authenticated Runtime browser-acceptance reports. |
| `analyze_runtime_paired_samples.py` | 活动 | Analyze repeated, authorized Legacy/Runtime E2E reports offline. |
| `audit_course_assets.py` | 活动 | Python 模块；定义 _load_yaml、_case_count、_knowledge_inventory、_contest_package_report、_course_asset_manifest 等。 |
| `audit_math_corpus.py` | 活动 | Audit course Markdown formulas without changing the source corpus. |
| `audit_readiness_consistency.py` | 活动 | Python 模块；定义 _compare、_course_report、_boundary_report、build_consistency_report、parse_args 等。 |
| `audit_runtime_trace.py` | 活动 | Audit a serialized Agent Runtime checkpoint trace without invoking tools. |
| `auth_management_browser_acceptance.js` | 活动 | 静态前端交互逻辑：auth management browser acceptance。 |
| `benchmark_agent_runtime.py` | 活动 | Local synthetic benchmark for conversation-context overhead. |
| `benchmark_auto_routing.py` | 活动 | Python 模块；定义 percentile_95、main。 |
| `benchmark_circuit_rendering_v2.py` | 活动 | Python 模块；定义 BenchmarkCase、_make_ct_case、_make_ae_case、_make_de_case、coverage_cases 等。 |
| `benchmark_math_circuit.py` | 活动 | Record a reproducible local performance baseline for the overnight core. |
| `benchmark_scenario_catalog.py` | 活动 | Python 模块；定义 percentile、benchmark、main。 |
| `browser_server_guard.js` | 活动 | 静态前端交互逻辑：browser server guard。 |
| `check.ps1` | 活动 | 跨平台运行脚本：check。 |
| `check.sh` | 活动 | 跨平台运行脚本：check。 |
| `check_environment.py` | 活动 | Python 模块；定义 main。 |
| `check_external_provider_runtime.py` | 活动 | Run a low-intensity live smoke check for configured retrieval providers. |
| `check_math_compatibility.py` | 活动 | Run structural math checks and a bounded real KaTeX compatibility sample. |
| `check_repo_drift.py` | 活动 | Repository directory-drift check. |
| `check_runtime_readiness_projection.py` | 活动 | Validate the read-only Runtime readiness projections. |
| `check_runtime_release_preflight.py` | 活动 | Run a provider-free, fail-closed Runtime release preflight. |
| `check_sensitive_files.py` | 活动 | Python 模块；定义 tracked_files、scan、main。 |
| `cleanup_local_artifacts.py` | 活动 | Python 模块；定义 RetentionPolicy、load_policies、_protected_latest_runs、candidates、_size 等。 |
| `collect_learning_runtime_semantic_sidecar.py` | 活动 | Bind an independent semantic judgement to a LearningLoop pair. |
| `collect_runtime_canary.py` | 活动 | Package an authorized Legacy/Runtime pair into a release-gate artifact. |
| `collect_runtime_semantic_evidence.py` | 活动 | Collect a deterministic semantic evidence sidecar from a paired suite. |
| `compare_evaluation_reports.py` | 活动 | Python 模块；定义 load、main。 |
| `compare_runtime_legacy.py` | 活动 | Compare serialized Legacy and Runtime results without executing anything. |
| `create_admin.py` | 活动 | Create the first local administrator without exposing a password in logs. |
| `create_synthetic_runtime_plan_proposal_fixture.py` | 活动 | Create a provider-free adaptive plan proposal suite for CI. |
| `create_synthetic_solver_parity_fixture.py` | 活动 | Create a provider-free Solver parity suite for CI smoke gating. |
| `demo_cli.py` | 活动 | Python 模块；定义 request_json、preflight、_check_routes、_check_rag_status、_check_agent_status 等。 |
| `dev.ps1` | 活动 | 跨平台运行脚本：dev。 |
| `dev.sh` | 活动 | 跨平台运行脚本：dev。 |
| `docker_dev.ps1` | 活动 | 跨平台运行脚本：docker dev。 |
| `docker_dev.sh` | 活动 | 跨平台运行脚本：docker dev。 |
| `docker_down.ps1` | 活动 | 跨平台运行脚本：docker down。 |
| `docker_down.sh` | 活动 | 跨平台运行脚本：docker down。 |
| `download_model_cache.py` | 活动 | Download a public ModelScope model into a local Transformers directory. |
| `evaluate_model_agents.py` | 活动 | Python 模块；定义 parse_args、load_cases、run、validate_result、get_path 等。 |
| `evaluate_planner_shadow.py` | 活动 | Python 模块；定义 load_cases、evaluate_case、_rate、evaluate、render_markdown 等。 |
| `evaluate_runtime_canary.py` | 活动 | Evaluate serialized Legacy/Runtime pairs without invoking a Provider. |
| `evaluate_runtime_plan_proposals.py` | 活动 | Evaluate adaptive Runtime plan proposals without invoking a Provider. |
| `evaluate_runtime_trace.py` | 活动 | Evaluate a serialized Agent Runtime trace against a versioned case. |
| `evaluate_solver_parity.py` | 活动 | Evaluate paired Legacy/Runtime solver outputs offline. |
| `export_openapi.py` | 活动 | Python 模块；定义 export_openapi、main。 |
| `generate_expanded_benchmark_v2.py` | 活动 | Generate the deterministic, provider-free T5 benchmark catalog. |
| `generate_ocr_review_queue.py` | 活动 | Python 模块；定义 _builder、parse_args、main。 |
| `generate_repository_catalog.py` | 活动 | Generate the deterministic, Git-scoped repository file catalog. |
| `import_evaluation_cases.py` | 活动 | Python 模块；定义 load_rows、main。 |
| `init_db.ps1` | 活动 | 跨平台运行脚本：init db。 |
| `init_db.sh` | 活动 | 跨平台运行脚本：init db。 |
| `knowledge_base_cli.py` | 活动 | Python 模块；定义 builder_from_settings、selected_courses、rag_components、command_audit、command_build 等。 |
| `maintain_evaluation_attachments.py` | 活动 | Python 模块；定义 parse_args、_json_default、run。 |
| `math_renderer_smoke.js` | 活动 | 静态前端交互逻辑：math renderer smoke。 |
| `migrate_legacy_index.py` | 活动 | Python 模块；定义 parser、main。 |
| `move_orphan_images.py` | 活动 | Python 模块；定义 _is_within、_load_jsonl、collect_moves、execute、main。 |
| `multimodal_browser_acceptance.js` | 活动 | 静态前端交互逻辑：multimodal browser acceptance。 |
| `package_learning_runtime_pair.py` | 活动 | Package a redacted Legacy/Runtime LearningLoop development pair. |
| `package_learning_runtime_pair_bundle.py` | 活动 | Package multiple redacted LearningLoop Legacy/Runtime pairs. |
| `package_runtime_e2e_evidence.py` | 活动 | Package controlled Runtime E2E artifacts into offline release evidence. |
| `promote_error_pool.py` | 活动 | Python 模块；定义 parse_args、main。 |
| `rag_cpu_profile.ps1` | 活动 | 跨平台运行脚本：rag cpu profile。 |
| `rebuild_index.py` | 活动 | Python 配置或执行模块。 |
| `release_a_cold_matrix.ps1` | 活动 | 跨平台运行脚本：release a cold matrix。 |
| `render_katex_samples.js` | 活动 | 静态前端交互逻辑：render katex samples。 |
| `research_analysis_demo.py` | 活动 | Run the four local research-analysis MVPs against synthetic, non-sensitive data. |
| `run_commercial_scenario_preflight.py` | 活动 | Python 模块；定义 percentile、run。 |
| `run_e2e_soak.py` | 活动 | Run a bounded local end-to-end soak test for the web application. |
| `run_evaluation.py` | 活动 | Python 模块；定义 parse_args、validate_paid_guard、validate_cases、_evaluation_schema_revision、evaluation_settings 等。 |
| `run_evaluation_loop.py` | 活动 | Python 模块；定义 parse_args、_load_cases、analyze、main。 |
| `run_learning_runtime_authorized_dev_e2e.py` | 活动 | Capture a redacted public-API LearningLoop Runtime development run. |
| `run_phase_g_baseline.py` | 活动 | Run the bounded Phase G provider-free baseline. |
| `run_phase_h_benchmark.py` | 活动 | Run the available full benchmark and produce bounded Phase H summaries. |
| `run_phase_j_robustness.py` | 活动 | Run bounded provider-free concurrency checks for Phase J. |
| `run_regression.py` | 活动 | Python 模块；定义 main。 |
| `run_runtime_authorized_dev_e2e.py` | 活动 | Capture small, authorized Runtime development E2E pairs. |
| `run_runtime_teacher_browser_acceptance.js` | 活动 | 静态前端交互逻辑：run runtime teacher browser acceptance。 |
| `run_web_ui_browser_acceptance.js` | 活动 | 静态前端交互逻辑：run web ui browser acceptance。 |
| `smoke_test_models.py` | 活动 | Python 模块；定义 ResultRow、parser、response_row、run、text_call 等。 |
| `soak_circuit_rendering_v2.py` | 活动 | Run a provider-free CircuitIR rendering soak with bounded memory evidence. |
| `start_demo.ps1` | 活动 | 跨平台运行脚本：start demo。 |
| `stop.ps1` | 活动 | 跨平台运行脚本：stop。 |
| `stop.sh` | 活动 | 跨平台运行脚本：stop。 |
| `student_browser_smoke.js` | 活动 | 静态前端交互逻辑：student browser smoke。 |
| `team_launcher.py` | 活动 | Python 模块；定义 LaunchError、RuntimeCheck、ProcessInfo、SingleInstanceLaunchLock、_process_is_running 等。 |
| `test.ps1` | 活动 | 跨平台运行脚本：test。 |
| `test.sh` | 活动 | 跨平台运行脚本：test。 |
| `validate_commercial_scenarios.py` | 活动 | Python 模块；定义 validate。 |
| `validate_config.py` | 活动 | Python 模块；定义 safe_status、agent_status、validate、main。 |
| `validate_contest_cases.py` | 活动 | Python 模块；定义 validate。 |
| `validate_evaluation_cases.py` | 活动 | Python 模块；定义 main。 |
| `validate_external_sources.py` | 活动 | Python 模块；定义 _public_http_url、validate。 |
| `validate_ocr_review_decisions.py` | 活动 | Python 模块；定义 _load_json、_load_yaml、main。 |
| `validate_planner_controlled_takeover.py` | 活动 | Python 模块；定义 run。 |
| `validate_research_pilot.py` | 活动 | Validate a local research-analysis pilot package before API execution. |
| `validate_scenarios.py` | 活动 | Python 模块；定义 validate。 |
| `xzd_supervisor.ps1` | 活动 | 跨平台运行脚本：xzd supervisor。 |

### `submission/contest_package`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01_participation_info.md` | 活动 | 文档：01 参赛信息。 |
| `02_governance_and_safety.md` | 活动 | 文档：02 伦理与安全边界。 |
| `03_demo_user_guide.md` | 活动 | 文档：03 Demo 使用说明。 |
| `04_product_solution.md` | 活动 | 文档：04 产品方案。 |
| `05_source_and_model_notes.md` | 活动 | 文档：05 源码与模型说明。 |
| `06_validation_report.md` | 活动 | 文档：06 效果验证报告（本地工程证据）。 |
| `07_test_scripts_and_materials.md` | 活动 | 文档：07 测试脚本与辅助材料。 |
| `08_user_pilot_log.md` | 活动 | 文档：08 用户试用记录模板。 |
| `09_evidence_matrix.md` | 活动 | 文档：证据矩阵（草案）。 |
| `10_deployment_and_operations.md` | 活动 | 文档：10 部署、权限与运维说明（草案）。 |
| `package_manifest.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、package_status、official_rules_verified、official_score_claims_allowed、demo_cases_included、real_user_outcomes_included。 |
| `README.md` | 活动 | 文档：竞赛材料包（工作骨架）。 |

### `tests/regression/cases`

| 文件 | 状态 | 功能 |
|---|---|---|
| `cloud_timeout.json` | 活动 | 结构化配置或数据；顶层字段：case_id、input、expected_course、expected_intent、expected_status、required_keywords。 |
| `follow_up.json` | 活动 | 结构化配置或数据；顶层字段：case_id、input、session_context、expected_course、expected_intent、expected_status。 |
| `knowledge_qa.json` | 活动 | 结构化配置或数据；顶层字段：case_id、input、expected_course、expected_intent、required_keywords、forbidden_claims。 |
| `solver_boundary.json` | 活动 | 结构化配置或数据；顶层字段：case_id、input、expected_course、expected_intent、expected_agent、expected_status。 |
| `solver_route.json` | 活动 | 结构化配置或数据；顶层字段：case_id、input、expected_course、expected_intent、expected_agent、expected_status。 |

### `真实测试题`

| 文件 | 状态 | 功能 |
|---|---|---|
| `analyze_evaluation_report.py` | 活动 | Python 模块；定义 load_json、load_cases、load_results、case_role、case_cohorts 等。 |
| `apply_manual_judgements.py` | 活动 | Python 模块；定义 latest_report、answer_sha256、apply_reviews、parse_args、main。 |
| `build_balanced_suite.py` | 活动 | Python 模块；定义 load_cases、normalized_text_hash、stable_order_key、with_role、chapter_of 等。 |
| `build_curated_answer_sets.py` | 活动 | Python 模块；定义 answer、load_supplemental、reference_answer、reference_solution、derived_case 等。 |
| `EVALUATION_STRATEGY.md` | 活动 | 文档：六门课程智能体评估指标与可视化策略。 |
| `extract_course_exercises.py` | 活动 | Python 模块；定义 ExerciseRegion、ParsedQuestion、project_relative、canonical_token、canonical_problem_key 等。 |
| `normalize_dataset.py` | 活动 | Python 模块；定义 read_text、root_relative、audit_relative、natural_key、clean_markdown 等。 |
| `organize_real_question_bank.py` | 活动 | 整理原始真实题库，排除补充、派生和合成评测题。 |
| `README.md` | 活动 | 文档：六门课程测试题统一格式。 |
| `run_api_tests.py` | 活动 | Python 模块；定义 load_cases、select_cases、request_preview、attachment_from_upload、write_report 等。 |
| `run_full_evaluation.py` | 活动 | Python 模块；定义 RealQuestionEvaluationRunner、parse_args、validate_args、load_cases、select_cases 等。 |
| `validate_balanced_suite.py` | 活动 | Python 模块；定义 load_json、load_cases、load_jsonl、normalized_text_hash、sha256 等。 |
| `validate_curated_answer_sets.py` | 活动 | Python 模块；定义 load_json、load_cases、load_jsonl、validate_project_contract、validate_common 等。 |
| `validate_dataset.py` | 活动 | Python 模块；定义 sha256、load_json、load_jsonl、validate_case、load_cases_wrapper 等。 |
| `validate_evaluation_metrics.py` | 活动 | Python 模块；定义 synthetic_case、synthetic_result、assert_real_suite_contract、main。 |
| `validate_judgement_strategy.py` | 活动 | Python 模块；定义 main。 |

### `真实题库_已整理`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 活动 | 文档：真实题库（已整理）。 |

### `真实题库_已整理/已核验_Q&A/AE`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE-1-5-3.md` | 活动 | 文档：AE-1-5-3 模拟电子技术 题1.5.3。 |
| `AE-1-5-4.md` | 活动 | 文档：AE-1-5-4 模拟电子技术 题1.5.4。 |
| `AE-1-5-5.md` | 活动 | 文档：AE-1-5-5 模拟电子技术 题1.5.5。 |
| `AE-10-1-1.md` | 活动 | 文档：AE-10-1-1 模拟电子技术 题10.1.1。 |
| `AE-10-1-2.md` | 活动 | 文档：AE-10-1-2 模拟电子技术 题10.1.2。 |
| `AE-10-3-2.md` | 活动 | 文档：AE-10-3-2 模拟电子技术 题10.3.2。 |
| `AE-11-2-2.md` | 活动 | 文档：AE-11-2-2 模拟电子技术 题11.2.2。 |
| `AE-11-2-6.md` | 活动 | 文档：AE-11-2-6 模拟电子技术 题11.2.6。 |
| `AE-2-1-1.md` | 活动 | 文档：AE-2-1-1 模拟电子技术 题2.1.1。 |
| `AE-2-1-3.md` | 活动 | 文档：AE-2-1-3 模拟电子技术 题2.1.3。 |
| `AE-2-3-7.md` | 活动 | 文档：AE-2-3-7 模拟电子技术 题2.3.7。 |
| `AE-2-4-1.md` | 活动 | 文档：AE-2-4-1 模拟电子技术 题2.4.1。 |
| `AE-3-4-1.md` | 活动 | 文档：AE-3-4-1 模拟电子技术 题3.4.1。 |
| `AE-3-4-14.md` | 活动 | 文档：AE-3-4-14 模拟电子技术 题3.4.14。 |
| `AE-3-5-2.md` | 活动 | 文档：AE-3-5-2 模拟电子技术 题3.5.2。 |
| `AE-4-1-2.md` | 活动 | 文档：AE-4-1-2 模拟电子技术 题4.1.2。 |
| `AE-4-1-3.md` | 活动 | 文档：AE-4-1-3 模拟电子技术 题4.1.3。 |
| `AE-4-4-2.md` | 活动 | 文档：AE-4-4-2 模拟电子技术 题4.4.2。 |
| `AE-4-5-2.md` | 活动 | 文档：AE-4-5-2 模拟电子技术 题4.5.2。 |
| `AE-4-7-4.md` | 活动 | 文档：AE-4-7-4 模拟电子技术 题4.7.4。 |
| `AE-5-1-2.md` | 活动 | 文档：AE-5-1-2 模拟电子技术 题5.1.2。 |
| `AE-5-1-3.md` | 活动 | 文档：AE-5-1-3 模拟电子技术 题5.1.3。 |
| `AE-5-2-6.md` | 活动 | 文档：AE-5-2-6 模拟电子技术 题5.2.6。 |
| `AE-5-4-1.md` | 活动 | 文档：AE-5-4-1 模拟电子技术 题5.4.1。 |
| `AE-6-1-5.md` | 活动 | 文档：AE-6-1-5 模拟电子技术 题6.1.5。 |
| `AE-6-2-1.md` | 活动 | 文档：AE-6-2-1 模拟电子技术 题6.2.1。 |
| `AE-6-3-1.md` | 活动 | 文档：AE-6-3-1 模拟电子技术 题6.3.1。 |
| `AE-7-1-1.md` | 活动 | 文档：AE-7-1-1 模拟电子技术 题7.1.1。 |
| `AE-7-2-1.md` | 活动 | 文档：AE-7-2-1 模拟电子技术 题7.2.1。 |
| `AE-7-2-7.md` | 活动 | 文档：AE-7-2-7 模拟电子技术 题7.2.7。 |
| `AE-8-1-3.md` | 活动 | 文档：AE-8-1-3 模拟电子技术 题8.1.3。 |
| `AE-8-3-1.md` | 活动 | 文档：AE-8-3-1 模拟电子技术 题8.3.1。 |
| `AE-8-3-6.md` | 活动 | 文档：AE-8-3-6 模拟电子技术 题8.3.6。 |
| `AE-8-3-7.md` | 活动 | 文档：AE-8-3-7 模拟电子技术 题8.3.7。 |
| `AE-8-3-8.md` | 活动 | 文档：AE-8-3-8 模拟电子技术 题8.3.8。 |
| `AE-8-5-2.md` | 活动 | 文档：AE-8-5-2 模拟电子技术 题8.5.2。 |
| `AE-9-4-1.md` | 活动 | 文档：AE-9-4-1 模拟电子技术 题9.4.1。 |
| `AE-9-4-2.md` | 活动 | 文档：AE-9-4-2 模拟电子技术 题9.4.2。 |
| `AE-9-4-6.md` | 活动 | 文档：AE-9-4-6 模拟电子技术 题9.4.6。 |

### `真实题库_已整理/已核验_Q&A/CT`

| 文件 | 状态 | 功能 |
|---|---|---|
| `CT-C01-Q01.md` | 活动 | 文档：CT-C01-Q01 电路理论 第1章 题1-1。 |
| `CT-C04-Q03.md` | 活动 | 文档：CT-C04-Q03 电路理论 第4章 题4-3。 |

### `真实题库_已整理/已核验_Q&A/DE`

| 文件 | 状态 | 功能 |
|---|---|---|
| `DE-1-3-2.md` | 活动 | 文档：DE-1-3-2 数字电子技术 题1.3.2。 |
| `DE-1-4-4.md` | 活动 | 文档：DE-1-4-4 数字电子技术 题1.4.4。 |
| `DE-10-1-1.md` | 活动 | 文档：DE-10-1-1 数字电子技术 题10.1.1。 |
| `DE-10-1-2.md` | 活动 | 文档：DE-10-1-2 数字电子技术 题10.1.2。 |
| `DE-11-1-1.md` | 活动 | 文档：DE-11-1-1 数字电子技术 题11.1.1。 |
| `DE-2-1-1.md` | 活动 | 文档：DE-2-1-1 数字电子技术 题2.1.1。 |
| `DE-2-1-2.md` | 活动 | 文档：DE-2-1-2 数字电子技术 题2.1.2。 |
| `DE-3-2-10.md` | 活动 | 文档：DE-3-2-10 数字电子技术 题3.2.10。 |
| `DE-3-2-11.md` | 活动 | 文档：DE-3-2-11 数字电子技术 题3.2.11。 |
| `DE-3-2-4.md` | 活动 | 文档：DE-3-2-4 数字电子技术 题3.2.4。 |
| `DE-3-2-8.md` | 活动 | 文档：DE-3-2-8 数字电子技术 题3.2.8。 |
| `DE-4-4-2.md` | 活动 | 文档：DE-4-4-2 数字电子技术 题4.4.2。 |
| `DE-4-4-3.md` | 活动 | 文档：DE-4-4-3 数字电子技术 题4.4.3。 |
| `DE-4-4-9.md` | 活动 | 文档：DE-4-4-9 数字电子技术 题4.4.9。 |
| `DE-5-2-1.md` | 活动 | 文档：DE-5-2-1 数字电子技术 题5.2.1。 |
| `DE-5-2-4.md` | 活动 | 文档：DE-5-2-4 数字电子技术 题5.2.4。 |
| `DE-5-4-2.md` | 活动 | 文档：DE-5-4-2 数字电子技术 题5.4.2。 |
| `DE-5-5-1.md` | 活动 | 文档：DE-5-5-1 数字电子技术 题5.5.1。 |
| `DE-6-1-1.md` | 活动 | 文档：DE-6-1-1 数字电子技术 题6.1.1。 |
| `DE-6-1-4.md` | 活动 | 文档：DE-6-1-4 数字电子技术 题6.1.4。 |
| `DE-6-1-7.md` | 活动 | 文档：DE-6-1-7 数字电子技术 题6.1.7。 |
| `DE-6-3-2.md` | 活动 | 文档：DE-6-3-2 数字电子技术 题6.3.2。 |
| `DE-7-1-1.md` | 活动 | 文档：DE-7-1-1 数字电子技术 题7.1.1。 |
| `DE-7-1-4.md` | 活动 | 文档：DE-7-1-4 数字电子技术 题7.1.4。 |
| `DE-7-2-5.md` | 活动 | 文档：DE-7-2-5 数字电子技术 题7.2.5。 |
| `DE-8-1-1.md` | 活动 | 文档：DE-8-1-1 数字电子技术 题8.1.1。 |
| `DE-8-1-2.md` | 活动 | 文档：DE-8-1-2 数字电子技术 题8.1.2。 |
| `DE-8-1-3.md` | 活动 | 文档：DE-8-1-3 数字电子技术 题8.1.3。 |
| `DE-9-1-1.md` | 活动 | 文档：DE-9-1-1 数字电子技术 题9.1.1。 |
| `DE-9-1-2.md` | 活动 | 文档：DE-9-1-2 数字电子技术 题9.1.2。 |
| `DE-9-2-2.md` | 活动 | 文档：DE-9-2-2 数字电子技术 题9.2.2。 |
| `DE-9-3-2.md` | 活动 | 文档：DE-9-3-2 数字电子技术 题9.3.2。 |

### `真实题库_已整理/已核验_Q&A/SS`

| 文件 | 状态 | 功能 |
|---|---|---|
| `SS-C01-Q01.md` | 活动 | 文档：SS-C01-Q01 例1-1 信号的功率和能量。 |
| `SS-C01-Q02.md` | 活动 | 文档：SS-C01-Q02 例1-7 信号的周期性。 |
| `SS-C01-Q03.md` | 活动 | 文档：SS-C01-Q03 习题1-1 连续时间信号变换作图。 |
| `SS-C01-Q04.md` | 活动 | 文档：SS-C01-Q04 习题1-3 信号的奇部和偶部。 |
| `SS-C01-Q05.md` | 活动 | 文档：SS-C01-Q05 习题1-7 连续时间系统性质判定。 |
| `SS-C01-Q06.md` | 活动 | 文档：SS-C01-Q06 例1-13 两个离散时间系统的级联。 |
| `SS-C02-Q01.md` | 活动 | 文档：SS-C02-Q01 例2-1 离散时间序列卷积。 |
| `SS-C02-Q02.md` | 活动 | 文档：SS-C02-Q02 例2-4 两个有限长矩形序列的卷积。 |
| `SS-C02-Q03.md` | 活动 | 文档：SS-C02-Q03 例2-8 冲激响应作用下的连续时间卷积。 |
| `SS-C02-Q04.md` | 活动 | 文档：SS-C02-Q04 例2-10 两个矩形脉冲的卷积。 |
| `SS-C02-Q05.md` | 活动 | 文档：SS-C02-Q05 习题2-9 连续时间LTI系统的因果性与稳定性。 |
| `SS-C02-Q06.md` | 活动 | 文档：SS-C02-Q06 习题2-11 差分方程的递归求解。 |
| `SS-C03-Q01.md` | 活动 | 文档：SS-C03-Q01 例3-1 由傅里叶级数系数合成连续时间信号。 |
| `SS-C03-Q02.md` | 活动 | 文档：SS-C03-Q02 例3-4 双极性矩形周期信号的傅里叶级数。 |
| `SS-C03-Q03.md` | 活动 | 文档：SS-C03-Q03 例3-9 周期冲激序列的离散时间傅里叶级数。 |
| `SS-C03-Q04.md` | 活动 | 文档：SS-C03-Q04 习题3-4 利用微分性质求三角波傅里叶级数。 |
| `SS-C03-Q05.md` | 活动 | 文档：SS-C03-Q05 习题3-8 离散时间周期信号的傅里叶级数系数。 |
| `SS-C03-Q06.md` | 活动 | 文档：SS-C03-Q06 例3-16 周期序列通过离散时间LTI滤波器。 |
| `SS-C04-Q01.md` | 活动 | 文档：SS-C04-Q01 例4-1 指数信号的连续时间傅里叶变换。 |
| `SS-C04-Q02.md` | 活动 | 文档：SS-C04-Q02 例4-4 利用综合式求傅里叶反变换。 |
| `SS-C04-Q03.md` | 活动 | 文档：SS-C04-Q03 例4-6 利用傅里叶变换性质表示变换。 |
| `SS-C04-Q04.md` | 活动 | 文档：SS-C04-Q04 例4-10 相乘性质与帕斯瓦尔定理。 |
| `SS-C04-Q05.md` | 活动 | 文档：SS-C04-Q05 习题4-6 利用卷积性质求连续时间卷积。 |
| `SS-C04-Q06.md` | 活动 | 文档：SS-C04-Q06 例4-19 由系统频率响应和输出求输入。 |
| `SS-C05-Q01.md` | 活动 | 文档：SS-C05-Q01 例5-1 求序列的傅里叶变换并画幅度频谱。 |
| `SS-C05-Q02.md` | 活动 | 文档：SS-C05-Q02 例5-3 周期序列的傅里叶变换。 |
| `SS-C05-Q03.md` | 活动 | 文档：SS-C05-Q03 例5-4 用定义求傅里叶逆变换。 |
| `SS-C05-Q04.md` | 活动 | 文档：SS-C05-Q04 例5-6 利用傅里叶变换性质表示变换。 |
| `SS-C05-Q05.md` | 活动 | 文档：SS-C05-Q05 例5-19 由差分方程求系统频率响应和冲激响应。 |
| `SS-C05-Q06.md` | 活动 | 文档：SS-C05-Q06 例5-20 由输入输出求频率响应和差分方程。 |
| `SS-C06-Q01.md` | 活动 | 文档：SS-C06-Q01 SS-C06-Q01 原题：例6-1 由可恢复采样频率确定信号带宽。 |
| `SS-C06-Q02.md` | 活动 | 文档：SS-C06-Q02 SS-C06-Q02 原题：例6-2 判断不同采样时间间隔能否恢复信号。 |
| `SS-C06-Q03.md` | 活动 | 文档：SS-C06-Q03 SS-C06-Q03 原题：例6-3 确定三个连续时间信号的奈奎斯特频率。 |
| `SS-C06-Q04.md` | 活动 | 文档：SS-C06-Q04 SS-C06-Q04 原题：例6-4 信号运算后的奈奎斯特频率。 |
| `SS-C06-Q05.md` | 活动 | 文档：SS-C06-Q05 SS-C06-Q05 原题：例6-5 延迟冲激串采样后的理想重建滤波器。 |
| `SS-C06-Q06.md` | 活动 | 文档：SS-C06-Q06 SS-C06-Q06 原题：例6-6 两个带限信号相乘后的最大采样时间间隔。 |
| `SS-C07-Q01.md` | 活动 | 文档：SS-C07-Q01 SS-C07-Q01 原题：例7-2 由定义求双边拉普拉斯变换及ROC。 |
| `SS-C07-Q02.md` | 活动 | 文档：SS-C07-Q02 SS-C07-Q02 原题：例7-9 用部分分式展开求拉普拉斯逆变换。 |
| `SS-C07-Q03.md` | 活动 | 文档：SS-C07-Q03 SS-C07-Q03 原题：例7-10 用极零点几何法判断滤波特性。 |
| `SS-C07-Q04.md` | 活动 | 文档：SS-C07-Q04 SS-C07-Q04 原题：例7-16 由系统函数极点判断稳定参数范围。 |
| `SS-C07-Q05.md` | 活动 | 文档：SS-C07-Q05 SS-C07-Q05 原题：例7-20 用单边拉普拉斯变换求RL电路响应。 |
| `SS-C07-Q06.md` | 活动 | 文档：SS-C07-Q06 SS-C07-Q06 原题：习题7-8 根据极零图列ROC并判断因果稳定性。 |
| `SS-C08-Q01.md` | 活动 | 文档：SS-C08-Q01 SS-C08-Q01 原题：例8-2 用定义求z变换及ROC。 |
| `SS-C08-Q02.md` | 活动 | 文档：SS-C08-Q02 SS-C08-Q02 原题：例8-9 部分分式展开求逆z变换。 |
| `SS-C08-Q03.md` | 活动 | 文档：SS-C08-Q03 SS-C08-Q03 原题：例8-12 极零图几何法判断频率特性。 |
| `SS-C08-Q04.md` | 活动 | 文档：SS-C08-Q04 SS-C08-Q04 原题：例8-13 矩形序列及差分性质。 |
| `SS-C08-Q05.md` | 活动 | 文档：SS-C08-Q05 SS-C08-Q05 原题：例8-18 由系统框图求差分方程与稳定性。 |
| `SS-C08-Q06.md` | 活动 | 文档：SS-C08-Q06 SS-C08-Q06 原题：例8-20 单边z变换求系统全响应。 |

### `真实题库_已整理/来源索引`

| 文件 | 状态 | 功能 |
|---|---|---|
| `原始排除记录.json` | 活动 | 结构化配置或数据；顶层字段：source_manifest、excluded_cases、output_policy、excluded_ai_or_derived_inputs。 |
| `已核验真实题库.json` | 活动 | 结构化配置或数据文件（内容需由对应加载器校验）。 |
| `无答案真实题目.json` | 活动 | 结构化数据集；包含 2 个顶层条目。 |
| `真实题目答案清单.json` | 活动 | 结构化数据集；包含 121 个顶层条目。 |

### `真实题库_已整理/附件/答案/AE-3-4-14`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图3.4.14_二极管的小信号交流等效电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/AE-4-7-4`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图解4.7.4_三种放大电路互联组成的放大电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/AE-5-2-6`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图5.2.6_小信号等效电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `模电测试集_图题5.2.6_小信号等效电路_副本14.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/AE-6-2-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图6.2.1_某种电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `模电测试集_图题6.2.1_电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-10-1-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch32_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-3-2-10`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch09_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch09_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-3-2-4`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch06_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch06_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-3-2-8`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch07_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch07_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-4-4-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch10_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch10_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-4-4-3`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch11_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch12_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-4-4-9`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch12_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch13_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-5-2-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch14_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-5-2-4`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch15_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-5-4-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch16_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch16_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-5-5-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch17_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch17_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-6-1-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch18_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-6-1-4`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch20_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch21_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-6-1-7`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch21_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-6-3-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch22_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch22_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-7-2-5`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch25_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-8-1-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch26_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-8-1-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch27_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-8-1-3`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch27_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-9-1-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch28_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch28_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-9-1-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch28_03.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-9-2-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch29_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch29_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/DE-9-3-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `ch30_01.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `ch30_02.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C01-Q03`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q03_original_answer_a.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q03_original_answer_b.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q03_original_answer_c.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q03_original_answer_d.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q03_original_answer_e.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q03_original_answer_f.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C01-Q04`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q04_original_answer_a.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q04_original_answer_bc.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C01-Q05`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q05_original_solution_p37.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q05_original_solution_p38.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q05_original_solution_p39.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q05_original_solution_p40.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C01-Q06`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q06_original_fig1-3.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q06_original_fig1-4.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C02-Q03`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q03_original_fig2-2.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C02-Q04`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q04_original_fig2-3.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C02-Q06`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q06_original_solution.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C04-Q01`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q01_original_fig4-5.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C05-Q01`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q01_original_fig5-2.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C06-Q06`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q06_original_fig6-2.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C07-Q03`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q03_original_fig7-3.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q03_original_fig7-4.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C07-Q05`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q05_original_fig7-10.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C07-Q06`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q06_original_fig7-17.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C08-Q03`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q03_original_fig8-2.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q03_original_fig8-3.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/答案/SS-C08-Q05`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q05_original_fig8-4.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-1-5-5`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图1.5.5_电流放大电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-10-3-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图解10.3.1_压控电压源型二阶低通滤波电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-11-2-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图11.2.2_有温度补偿的稳压管基准电压源.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-11-2-6`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图11.2.6_具有跟踪特性的正负电压输出的稳压电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-2-1-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图2.1.1_运算放大器电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-2-3-7`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图题2.3.7_同相和反相放大电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-2-4-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图2.4.1_反相加法器.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-3-4-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图题3.4.1_某种电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-3-4-14`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图3.4.14_电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-3-5-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图题3.5.2_稳压电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-4-4-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图4.4.2_PMOS放大电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-4-5-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图4.5.2_源极跟随器电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `模电测试集_图4.5.2_源极跟随器电路_副本11.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-5-2-6`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图题5.2.6_小信号等效电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-6-1-5`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图6.1.5_某放大电路中dotA_v的幅频响应.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-7-1-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图题7.1.1_MOS管电流源电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-7-2-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图7.2.1_源极耦合差分式放大电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-7-2-7`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图7.2.9a_射极耦合差分式放大电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-8-1-3`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图8.1.3_两电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-8-3-6`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图8.3.6_多级放大电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-8-5-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图8.5.2_电流并联负反馈.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-9-4-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图9.4.1_单电源互补对称功放电路.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/AE-9-4-6`

| 文件 | 状态 | 功能 |
|---|---|---|
| `模电测试集_图9.4.6_集成电路的输出级.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/CT-C01-Q01`

| 文件 | 状态 | 功能 |
|---|---|---|
| `image01.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/CT-C04-Q03`

| 文件 | 状态 | 功能 |
|---|---|---|
| `image01.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-10-1-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `10_1_2.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-3-2-11`

| 文件 | 状态 | 功能 |
|---|---|---|
| `3_8_3题3_2_11.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-3-2-4`

| 文件 | 状态 | 功能 |
|---|---|---|
| `3_8_3题3_2_4.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-3-2-8`

| 文件 | 状态 | 功能 |
|---|---|---|
| `3_8_3题3_2_8.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-5-2-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `5_6_7题5_2_1.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-5-2-4`

| 文件 | 状态 | 功能 |
|---|---|---|
| `5_6_7题5_2_4.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-5-4-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `5_6_7题5_4_2.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-5-5-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `5_6_7题5_5_1.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-6-1-7`

| 文件 | 状态 | 功能 |
|---|---|---|
| `6_7_11题6_1_7.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-6-3-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `6_7_11题6_3_2.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-8-1-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `8_4_3题8_1_1.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-9-1-1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `9_4_9题9_1_1.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-9-1-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `9_4_9题9_1_2.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-9-2-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `9_4_9题9_2_2.jpg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/DE-9-3-2`

| 文件 | 状态 | 功能 |
|---|---|---|
| `9_4_9题9_3_2.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C01-Q03`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q03_original_fig1-5.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C01-Q04`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q04_original_fig1-7.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C02-Q06`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q06_original_fig2-11.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C03-Q05`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q05_original_fig3-5.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C03-Q06`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q06_original_fig3-1.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C04-Q05`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q05_original_fig4-13.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C06-Q06`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q06_original_fig6-2.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C07-Q03`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q03_original_fig7-3.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q03_original_fig7-4.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C07-Q05`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q05_original_fig7-10.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C07-Q06`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q06_original_fig7-17.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C08-Q03`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q03_original_fig8-2.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q03_original_fig8-3.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `真实题库_已整理/附件/题目/SS-C08-Q05`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q05_original_fig8-4.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `组员反馈`

| 文件 | 状态 | 功能 |
|---|---|---|
| `学习智能体测试题_完整包_v1.zip` | 活动 | 仓库配置、资产或占位文件。 |
| `组员二反馈.html` | 活动 | 静态前端页面：测试集。 |

### `组员反馈/组员一反馈`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01_题目清单.md` | 活动 | 文档：学习智能体第一轮测试题（14题）。 |
| `02_标准答案与评分锚点.md` | 活动 | 文档：学习智能体第一轮测试题：标准答案与评分锚点。 |
| `03_题源与改编说明.md` | 活动 | 文档：题源与改编说明。 |
| `README.txt` | 活动 | 仓库配置、资产或占位文件。 |
| `芯智导学_学习智能体综合测试报告_2026-08-17.docx` | 活动 | 仓库配置、资产或占位文件。 |

### `组员反馈/组员一反馈/images`

| 文件 | 状态 | 功能 |
|---|---|---|
| `Q01_signal_convolution.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q02_signal_spectrum_modulation.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q03_signal_bandpass_sampling.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q04_circuit_max_power.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q05_circuit_dependent_source.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q06_analog_bjt_amplifier.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q07_analog_instrumentation_amp.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q08_digital_R2R_DAC.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `Q09_digital_555_schmitt.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
