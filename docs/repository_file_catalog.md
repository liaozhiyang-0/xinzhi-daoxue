# 仓库逐文件目录（自动生成）

> 本文档只覆盖 `git ls-files --cached --others --exclude-standard` 可见的可发布文件，
> 因而不会读取或列出 `.env`、教材原文、向量索引、上传文件、数据库、模型缓存和测试临时文件。
> 文件职责由路径、模块文档字符串、Markdown 标题和结构化文件顶层字段确定；它是导航清单，不替代源码。

- 可发布文件总数：**615**
- 活动文件：**601**
- 历史隔离文件：**14**
- 重新生成：`python scripts/generate_repository_catalog.py`
- 漂移检查：`python scripts/generate_repository_catalog.py --check`

## 顶层范围

| 路径 | 文件数 | 职责 |
|---|---:|---|
| `.dockerignore` | 1 | Docker 构建上下文排除规则。 |
| `.env.example` | 1 | 无密钥的环境变量模板；本机真实值写入被忽略的 `.env`。 |
| `.gitattributes` | 1 | Git 文本属性与跨平台换行规则。 |
| `.github` | 1 | GitHub Actions 持续集成。 |
| `.gitignore` | 1 | 本地密钥、教材、索引、缓存、上传物与运行数据排除规则。 |
| `agent_configs` | 4 | Agent 注册表、冻结工作流与课程包配置。 |
| `AGENTS.md` | 1 | 仓库工程、安全、验证和发布约束。 |
| `apps` | 337 | FastAPI 主应用、静态前端和 Worker 边界。 |
| `archive_legacy` | 14 | 退出活动架构的历史资料与代码隔离区。 |
| `config` | 3 | 跨运行环境的基础配置。 |
| `docker-compose.yml` | 1 | PostgreSQL、Redis、MinIO、Qdrant 与 API 的本地编排。 |
| `docs` | 120 | 现行架构、运行、评测、知识库与验收文档。 |
| `evaluation` | 59 | 可复现评测数据集、基线、模式与报告模板。 |
| `knowledge_config` | 11 | 课程资料元数据、OCR 覆盖和分块策略。 |
| `local_knowledge` | 4 | 可提交的小型示例知识与目录占位；非教材原文。 |
| `pytest.ini` | 1 | 根目录 Pytest 发现与运行配置。 |
| `README.md` | 1 | 项目入口说明、能力边界、配置和启动指引。 |
| `ruff.toml` | 1 | Ruff 静态检查和格式规则。 |
| `scripts` | 44 | 启动、诊断、迁移、索引、评测和发布辅助脚本。 |
| `tests` | 5 | 仓库级配置和静态边界测试。 |
| `xzd.cmd` | 1 | Windows CMD 统一启动器入口。 |
| `xzd.ps1` | 1 | Windows PowerShell 统一启动器入口。 |
| `xzd.sh` | 1 | Linux/macOS 统一启动器入口。 |
| `打开芯智导学.cmd` | 1 | Windows 双击启动并打开学生工作台的便捷入口。 |

## 文件类型统计

| 扩展名 | 数量 |
|---|---:|
| `.py` | 316 |
| `.md` | 105 |
| `.png` | 38 |
| `.json` | 37 |
| `.yaml` | 29 |
| `.woff2` | 20 |
| `[无扩展名]` | 13 |
| `.js` | 12 |
| `.ps1` | 10 |
| `.html` | 9 |
| `.sh` | 8 |
| `.css` | 7 |
| `.cmd` | 2 |
| `.ini` | 2 |
| `.toml` | 2 |
| `.yml` | 2 |
| `.example` | 1 |
| `.mako` | 1 |
| `.svg` | 1 |

## 逐目录文件清单

### `仓库根目录`

| 文件 | 状态 | 功能 |
|---|---|---|
| `.dockerignore` | 活动 | Docker 构建上下文排除规则。 |
| `.env.example` | 活动 | 无密钥的环境变量模板；本机真实值写入被忽略的 `.env`。 |
| `.gitattributes` | 活动 | Git 文本属性与跨平台换行规则。 |
| `.gitignore` | 活动 | 本地密钥、教材、索引、缓存、上传物与运行数据排除规则。 |
| `AGENTS.md` | 活动 | 仓库工程、安全、验证和发布约束。 |
| `docker-compose.yml` | 活动 | PostgreSQL、Redis、MinIO、Qdrant 与 API 的本地编排。 |
| `pytest.ini` | 活动 | 根目录 Pytest 发现与运行配置。 |
| `README.md` | 活动 | 项目入口说明、能力边界、配置和启动指引。 |
| `ruff.toml` | 活动 | Ruff 静态检查和格式规则。 |
| `xzd.cmd` | 活动 | Windows CMD 统一启动器入口。 |
| `xzd.ps1` | 活动 | Windows PowerShell 统一启动器入口。 |
| `xzd.sh` | 活动 | Linux/macOS 统一启动器入口。 |
| `打开芯智导学.cmd` | 活动 | Windows 双击启动并打开学生工作台的便捷入口。 |

### `.github/workflows`

| 文件 | 状态 | 功能 |
|---|---|---|
| `backend-ci.yml` | 活动 | 结构化配置或数据；顶层字段：name、True、jobs。 |

### `agent_configs`

| 文件 | 状态 | 功能 |
|---|---|---|
| `mock_profiles.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、profiles。 |
| `registry.yaml` | 活动 | 结构化配置或数据；顶层字段：scenes、session_context、agents、routing。 |

### `agent_configs/course_packs`

| 文件 | 状态 | 功能 |
|---|---|---|
| `course_ct_v1.yaml` | 活动 | 结构化配置或数据；顶层字段：course_id、course_name、domain_id、version、knowledge_spaces、agents。 |

### `agent_configs/workflows`

| 文件 | 状态 | 功能 |
|---|---|---|
| `solver_ct_v1.yaml` | 活动 | 结构化配置或数据；顶层字段：workflow_id、display_name、version、provider、publication_status、course_pack。 |

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

### `apps/api/app`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | 芯智导学 FastAPI application package. |
| `dependencies.py` | 活动 | Python 模块；定义 get_settings_from_app、get_provider、get_knowledge_base、get_rag_retrieval、get_db。 |
| `main.py` | 活动 | Python 模块；定义 error_payload、create_app。 |

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
| `contracts.py` | 活动 | Python 模块；定义 CourseClassification、IntentClassification、QueryRewrite、CircuitPlan、LessonPrepDraft 等。 |
| `hub.py` | 活动 | Python 模块；定义 InternalAgentDefinition、InternalAgentHub。 |

### `apps/api/app/agents/solver_ct`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `local_graph.py` | 活动 | Python 模块；定义 CircuitProblem、SolverExecution、LocalCircuitSolverGraph。 |

### `apps/api/app/api`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | HTTP API package. |

### `apps/api/app/api/v1`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Version 1 API routes. |
| `agents.py` | 活动 | Python 模块；定义 AgentDryRunRequest、_lifecycle_status、list_agent_status、show_agent、dry_run_agent。 |
| `artifacts.py` | 活动 | Python 模块；定义 get_artifact。 |
| `debug_agents.py` | 活动 | Python 模块；定义 AgentDebugRequest、AgentCompareRequest、_ensure_debug、_agent_request、_result_payload 等。 |
| `debug_execution.py` | 活动 | Python 模块；定义 _redact、get_metrics_summary、get_execution。 |
| `debug_rag.py` | 活动 | Python 模块；定义 DebugRunRequest、CompareRequest、EvalRequest、_default_prewarm_models、PrewarmRequest 等。 |
| `debug_traces.py` | 活动 | Python 模块；定义 get_trace。 |
| `evaluation.py` | 活动 | Python 模块；定义 _require_enabled、list_suites、latest_report。 |
| `files.py` | 活动 | Python 模块；定义 upload_file、get_file。 |
| `health.py` | 活动 | Python 模块；定义 health。 |
| `internal_agents.py` | 活动 | Python 模块；定义 list_internal_agents。 |
| `knowledge.py` | 活动 | Python 模块；定义 list_sources、search_knowledge、evaluate_query、rag_search、rag_health 等。 |
| `learning.py` | 活动 | Python 模块；定义 learning_action、learning_states。 |
| `memories.py` | 活动 | Python 模块；定义 list_memories、create_memory、update_memory、delete_memory、restore_memory 等。 |
| `models.py` | 活动 | Python 模块；定义 list_models、model_health。 |
| `orchestration.py` | 活动 | Python 模块；定义 _local_handler_available、_attachments、_submit、create_chat、stream_chat 等。 |
| `router.py` | 活动 | Python 配置或执行模块。 |
| `sessions.py` | 活动 | Python 模块；定义 create_session、list_sessions、search_sessions、get_session、update_session 等。 |
| `tasks.py` | 活动 | Python 模块；定义 task_read、create_task、_with_conversation_context、get_task、get_task_events 等。 |

### `apps/api/app/capabilities`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `base.py` | 活动 | Python 模块；定义 CapabilityResult、BaseCapability。 |
| `registry.py` | 活动 | Python 模块；定义 CapabilityRegistry、default_capability_registry。 |

### `apps/api/app/contracts`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `agent.py` | 活动 | Python 模块；定义 utc_now、new_id、UserRole、Scene、Intent 等。 |
| `api.py` | 活动 | Python 模块；定义 SessionCreate、SessionRead、SessionUpdate、SessionTaskHistoryItem、TaskRead 等。 |
| `conversation.py` | 活动 | Python 模块；定义 MessageRole、MessageStatus、MessageVisibility、ConversationMessage、SessionWorkingState 等。 |
| `knowledge.py` | 活动 | Python 模块；定义 KnowledgeCourseId、DocumentManifest、KnowledgeChunk、CitationSupport、KnowledgeSearchRequest 等。 |
| `learning.py` | 活动 | Python 模块；定义 LearnerKnowledgeState、AnswerReviewResult、PracticeProblem、LearningActionRequest、LearningActionResponse。 |
| `math_content.py` | 活动 | Python 模块；定义 MathBlockType、MathSegmentType、MathExpression、RichTextSegment、MathRichContent。 |
| `memory.py` | 活动 | Python 模块；定义 MemoryType、MemoryStatus、MemoryScope、MemoryCreate、MemoryUpdate 等。 |
| `model.py` | 活动 | Python 模块；定义 ModelUsage、ModelResponse、ProviderHealth、ImageInput、ModelStreamEvent。 |
| `orchestration.py` | 活动 | Python 模块；定义 ExecutionStatus、InputType、ExecutionMode、TaskFamily、CourseCode 等。 |
| `routing.py` | 活动 | Python 模块；定义 RouteStatus、RouteCandidate、RouteDecision。 |
| `runtime.py` | 活动 | Python 模块；定义 RAGInteractionMode、WorkflowContextBundle、EvidenceViewItem、TaskExecutionSummary、TaskPresentation 等。 |
| `solver.py` | 活动 | Python 模块；定义 AcademicProblem、ToolResult、VerificationIssue、VerificationReport、SolutionPatch 等。 |

### `apps/api/app/core`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Core configuration, logging and errors. |
| `config.py` | 活动 | Python 模块；定义 Settings、get_settings。 |
| `errors.py` | 活动 | Python 模块；定义 AppError、ConfigurationError、ProviderError、ProviderTimeoutError、ProviderCancelledError 等。 |
| `internal_workflows.py` | 活动 | Python 模块；定义 internal_workflow_models_configured。 |
| `logging.py` | 活动 | Python 模块；定义 set_request_id、reset_request_id、mask_sensitive_text、redact、configure_logging。 |
| `redaction.py` | 活动 | Python 模块；定义 redact_sensitive_text。 |

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
| `reporting.py` | 活动 | Python 模块；定义 build_statistics、write_report、render_markdown、_group_summary、_ratio 等。 |
| `runner.py` | 活动 | Python 模块；定义 EvaluationRunner。 |

### `apps/api/app/evaluation/scorers`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `core.py` | 活动 | Python 模块；定义 normalize_text、ParsedQuantity、EvaluationScorer。 |

### `apps/api/app/integrations`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | External integration boundaries. |

### `apps/api/app/models`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `entities.py` | 活动 | Python 模块；定义 utc_now、db_id、TaskStatus、SessionModel、TaskModel 等。 |

### `apps/api/app/multimodal`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `file_parser.py` | 活动 | Python 模块；定义 detect_input_type。 |
| `image_batch.py` | 活动 | Python 模块；定义 ImageItemResult、ImageBatchProcessor。 |
| `image_composer.py` | 活动 | Python 模块；定义 SourceImage、PreparedImageBatch、MultiImageComposer。 |
| `image_encoder.py` | 活动 | Python 模块；定义 ImageEncoder。 |
| `pdf_processor.py` | 活动 | Python 模块；定义 PDFPage、PDFExtraction、PDFProcessor。 |
| `result_merger.py` | 活动 | Python 模块；定义 merge_multimodal_results。 |

### `apps/api/app/observability`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `model_tracer.py` | 活动 | Python 模块；定义 ModelCallRecord、ModelTracer。 |
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
| `academic_solver_graph.py` | 活动 | Python 模块；定义 AcademicProblemSolverGraph。 |

### `apps/api/app/providers`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `base.py` | 活动 | Python 模块；定义 AgentProvider。 |
| `development_mock.py` | 活动 | Python 模块；定义 DevelopmentMockProvider。 |
| `factory.py` | 活动 | Python 模块；定义 get_agent_provider、get_provider_availability。 |
| `mock.py` | 活动 | Python 模块；定义 MockAgentProvider。 |
| `xingchen.py` | 活动 | Python 模块；定义 extract_input_text、build_workflow_payload、get_single_image、classify_input、parse_upload_url 等。 |

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

### `apps/api/app/providers/vision`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `base.py` | 活动 | Python 模块；定义 VisionResult、VisionProvider。 |
| `iflytek_vision.py` | 活动 | Python 模块；定义 IFlytekVisionProvider。 |

### `apps/api/app/providers/workflow`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `base.py` | 活动 | Python 模块；定义 WorkflowResult、WorkflowProvider。 |
| `xingchen.py` | 活动 | Python 模块；定义 XingchenWorkflowProvider。 |

### `apps/api/app/repositories`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Python 包边界与对外导出。 |
| `artifacts.py` | 活动 | Python 模块；定义 ArtifactRepository。 |
| `conversations.py` | 活动 | Python 模块；定义 ConversationRepository。 |
| `files.py` | 活动 | Python 模块；定义 FileRepository。 |
| `memories.py` | 活动 | Python 模块；定义 MemoryRepository。 |
| `runtime_context.py` | 活动 | Python 模块；定义 RuntimeContextRepository。 |
| `sessions.py` | 活动 | Python 模块；定义 SessionRepository。 |
| `tasks.py` | 活动 | Python 模块；定义 TaskRepository。 |

### `apps/api/app/services`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Application services. |
| `academic_solver_service.py` | 活动 | Python 模块；定义 AcademicProblemSolverService。 |
| `agent_result_governance.py` | 活动 | Python 模块；定义 AgentResultValidatorRegistry、BusinessResultRendererRegistry。 |
| `agent_runtime.py` | 活动 | Python 模块；定义 MappedAgentInput、ParsedWorkflowOutput、AgentInputMapper、WorkflowOutputParserRegistry、AgentExecutionPlanner 等。 |
| `agent_scaffold.py` | 活动 | Python 模块；定义 AgentScaffoldSpec、AgentScaffoldService。 |
| `citation_validator.py` | 活动 | Python 模块；定义 CitationValidationResult、CitationValidator。 |
| `context_assembly.py` | 活动 | Python 模块；定义 ContextAssemblyService。 |
| `context_budget.py` | 活动 | Python 模块；定义 BudgetDecision、ContextBudgetManager。 |
| `context_cache.py` | 活动 | Python 模块；定义 ContextAssemblyCache。 |
| `conversation_message_service.py` | 活动 | Python 模块；定义 ConversationMessageService。 |
| `course_pack.py` | 活动 | Python 模块；定义 load_course_pack。 |
| `event_service.py` | 活动 | Python 模块；定义 append_task_event。 |
| `general_question_service.py` | 活动 | Python 模块；定义 GeneralQuestionService。 |
| `health.py` | 活动 | Python 模块；定义 _database_status、_redis_status、_minio_status、build_health。 |
| `high_risk_verification.py` | 活动 | Python 模块；定义 HighRiskVerificationService。 |
| `internal_agent_execution.py` | 活动 | Python 模块；定义 InternalAgentExecutionService。 |
| `knowledge_audit.py` | 活动 | Python 模块；定义 stable_id、checksum_file、posix_relative、source_uri、image_uri 等。 |
| `knowledge_base.py` | 活动 | Python 模块；定义 IndexedChunk、CourseMetadata、RetrievalTopicBoost、normalize_query、tokenize 等。 |
| `knowledge_index.py` | 活动 | Python 模块；定义 ChunkRecord、BuildResult、_split_long_block、markdown_blocks、semantic_chunks 等。 |
| `knowledge_qa_service.py` | 活动 | Python 模块；定义 KnowledgeQAExecution、KnowledgeQAService。 |
| `knowledge_resources.py` | 活动 | Python 模块；定义 resolve_course_resource、resolve_kb_image_uri。 |
| `learning_loop.py` | 活动 | Python 模块；定义 LearningLoopService。 |
| `math_formatting_service.py` | 活动 | Python 模块；定义 _ProcessedChunk、MathFormattingService。 |
| `math_symbol_dictionary.py` | 活动 | Python 配置或执行模块。 |
| `memory_service.py` | 活动 | Python 模块；定义 MemoryService。 |
| `model_registry.py` | 活动 | Python 模块；定义 ModelDefinition、ModelRoute、ModelRegistry。 |
| `model_service.py` | 活动 | Python 模块；定义 ModelService。 |
| `practice_generation.py` | 活动 | Python 模块；定义 PracticeGenerationService。 |
| `query_rewrite.py` | 活动 | Python 模块；定义 rewrite_retrieval_query。 |
| `rag_debug.py` | 活动 | Python 模块；定义 utc_iso、DebugTraceStore、RAGDebugService。 |
| `rag_index.py` | 活动 | Python 模块；定义 IndexVersionInfo、RAGBuildResult、load_jsonl、MultimodalRAGIndexer。 |
| `rag_providers.py` | 活动 | Python 模块；定义 ProviderHealth、TextEmbeddingProvider、ImageEmbeddingProvider、RerankerProvider、resolve_device 等。 |
| `rag_retrieval.py` | 活动 | Python 模块；定义 RetrievalPolicy、policy_for、_Candidate、RAGRetrievalService。 |
| `rag_runtime.py` | 活动 | Python 模块；定义 create_text_embedding_provider、create_image_embedding_provider、create_reranker_provider、create_vector_store。 |
| `request_materials.py` | 活动 | Python 模块；定义 RequestMaterialExtractor。 |
| `retrieval_context.py` | 活动 | Python 模块；定义 EvidenceQuality、EvidenceQualityEvaluator、RetrievalContextService。 |
| `runtime_safety.py` | 活动 | Python 模块；定义 sanitize_runtime_text、contains_sensitive_information。 |
| `session_compaction.py` | 活动 | Python 模块；定义 SessionCompactionService。 |
| `session_context.py` | 活动 | Python 模块；定义 SessionContextService。 |
| `session_service.py` | 活动 | Python 模块；定义 SessionService。 |
| `session_working_state.py` | 活动 | Python 模块；定义 SessionWorkingStateService。 |
| `solver_quality_gate.py` | 活动 | Python 模块；定义 SolverQualityGateService。 |
| `storage.py` | 活动 | Python 模块；定义 sanitize_filename、StorageService。 |
| `student_answer_review.py` | 活动 | Python 模块；定义 _tokens、StudentAnswerReviewService。 |
| `task_control_service.py` | 活动 | Python 模块；定义 TaskControlService。 |
| `task_creation_service.py` | 活动 | Python 模块；定义 TaskCreationService。 |
| `task_executor.py` | 活动 | Python 模块；定义 TaskExecutor、LocalTaskExecutor、QueueTaskExecutor。 |
| `task_presentation.py` | 活动 | Python 模块；定义 build_task_views、_evidence_view、_execution_steps。 |
| `task_query_service.py` | 活动 | Python 模块；定义 TaskQueryService。 |
| `task_runner.py` | 活动 | Python 模块；定义 utc_now、elapsed_ms、TaskRunner。 |
| `vector_store.py` | 活动 | Python 模块；定义 VectorSearchHit、VectorStoreAdapter、qdrant_point_id、QdrantVectorStoreAdapter。 |

### `apps/api/app/static/debug`

| 文件 | 状态 | 功能 |
|---|---|---|
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
| `pages.css` | 活动 | 静态前端样式：pages。 |
| `rag.html` | 活动 | 静态前端页面：多模态 RAG 调试 · 芯智导学。 |
| `rag.js` | 活动 | 静态前端交互逻辑：rag。 |
| `student.html` | 活动 | 静态前端页面：智能学习 · 芯智导学。 |
| `student.js` | 活动 | 静态前端交互逻辑：student。 |
| `system.html` | 活动 | 静态前端页面：系统状态 · 芯智导学。 |
| `system.js` | 活动 | 静态前端交互逻辑：system。 |
| `ui-core.js` | 活动 | 静态前端交互逻辑：ui-core。 |
| `workspace-v2.css` | 活动 | 静态前端样式：workspace-v2。 |
| `workspace.html` | 活动 | 静态前端页面：智能任务工作台 · 芯智导学。 |
| `workspace.js` | 活动 | 静态前端交互逻辑：workspace。 |

### `apps/api/app/static/debug/assets`

| 文件 | 状态 | 功能 |
|---|---|---|
| `demo-circuit.svg` | 活动 | 界面验收、测试或文档使用的图像资产。 |

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
| `rag_fakes.py` | 活动 | Python 模块；定义 _normalize、DeterministicFakeTextEmbeddingProvider、DeterministicFakeImageEmbeddingProvider、DeterministicFakeReranker。 |
| `test_agent_registry.py` | 活动 | 回归测试：agent registry。 |
| `test_agent_result_governance.py` | 活动 | 回归测试：agent result governance。 |
| `test_agent_runtime.py` | 活动 | 回归测试：agent runtime。 |
| `test_agent_runtime_foundation.py` | 活动 | 回归测试：agent runtime foundation。 |
| `test_agent_scaffold.py` | 活动 | 回归测试：agent scaffold。 |
| `test_attachment_contract.py` | 活动 | 回归测试：attachment contract。 |
| `test_automatic_routing_fixture.py` | 活动 | 回归测试：automatic routing fixture。 |
| `test_background_task_runner.py` | 活动 | 回归测试：background task runner。 |
| `test_cloud_learn_contract.py` | 活动 | 回归测试：cloud learn contract。 |
| `test_config_validation.py` | 活动 | 回归测试：config validation。 |
| `test_contracts.py` | 活动 | 回归测试：contracts。 |
| `test_course_pack_loader.py` | 活动 | 回归测试：course pack loader。 |
| `test_debug_knowledge_qa.py` | 活动 | 回归测试：debug knowledge qa。 |
| `test_debug_page.py` | 活动 | 回归测试：debug page。 |
| `test_development_mock_agents.py` | 活动 | 回归测试：development mock agents。 |
| `test_embedding_compatibility.py` | 活动 | 回归测试：embedding compatibility。 |
| `test_evaluation_api.py` | 活动 | 回归测试：evaluation api。 |
| `test_evaluation_framework.py` | 活动 | 回归测试：evaluation framework。 |
| `test_event_sequence.py` | 活动 | 回归测试：event sequence。 |
| `test_evidence_quality.py` | 活动 | 回归测试：evidence quality。 |
| `test_execution_debug_api.py` | 活动 | 回归测试：execution debug api。 |
| `test_explanation_artifact.py` | 活动 | 回归测试：explanation artifact。 |
| `test_file_metadata.py` | 活动 | 回归测试：file metadata。 |
| `test_file_upload.py` | 活动 | 回归测试：file upload。 |
| `test_general_question_service.py` | 活动 | 回归测试：general question service。 |
| `test_heading_boost.py` | 活动 | 回归测试：heading boost。 |
| `test_health.py` | 活动 | 回归测试：health。 |
| `test_high_risk_verification.py` | 活动 | 回归测试：high risk verification。 |
| `test_internal_agent_execution.py` | 活动 | 回归测试：internal agent execution。 |
| `test_internal_agents.py` | 活动 | 回归测试：internal agents。 |
| `test_kb_citation_integrity.py` | 活动 | 回归测试：kb citation integrity。 |
| `test_knowledge_api.py` | 活动 | 回归测试：knowledge api。 |
| `test_knowledge_base_service.py` | 活动 | 回归测试：knowledge base service。 |
| `test_knowledge_index_pipeline.py` | 活动 | 回归测试：knowledge index pipeline。 |
| `test_knowledge_lifecycle.py` | 活动 | 回归测试：knowledge lifecycle。 |
| `test_knowledge_qa_service.py` | 活动 | 回归测试：knowledge qa service。 |
| `test_learning_loop.py` | 活动 | 回归测试：learning loop。 |
| `test_legacy_cleanup.py` | 活动 | 回归测试：legacy cleanup。 |
| `test_local_solver_graph.py` | 活动 | 回归测试：local solver graph。 |
| `test_math_formatting_service.py` | 活动 | 回归测试：math formatting service。 |
| `test_migrations.py` | 活动 | 回归测试：migrations。 |
| `test_mock_provider.py` | 活动 | 回归测试：mock provider。 |
| `test_model_agent_evaluation.py` | 活动 | 回归测试：model agent evaluation。 |
| `test_model_api_integration.py` | 活动 | 回归测试：model api integration。 |
| `test_model_providers.py` | 活动 | 回归测试：model providers。 |
| `test_model_registry_service.py` | 活动 | 回归测试：model registry service。 |
| `test_model_security.py` | 活动 | 回归测试：model security。 |
| `test_models_api.py` | 活动 | 回归测试：models api。 |
| `test_multimodal_batch.py` | 活动 | 回归测试：multimodal batch。 |
| `test_multimodal_rag.py` | 活动 | 回归测试：multimodal rag。 |
| `test_openapi_export.py` | 活动 | 回归测试：openapi export。 |
| `test_orchestration_api.py` | 活动 | 回归测试：orchestration api。 |
| `test_orchestration_contracts.py` | 活动 | 回归测试：orchestration contracts。 |
| `test_path_traversal_rejected.py` | 活动 | 回归测试：path traversal rejected。 |
| `test_pdf_processor.py` | 活动 | 回归测试：pdf processor。 |
| `test_professional_tools.py` | 活动 | 回归测试：professional tools。 |
| `test_provider_factory.py` | 活动 | 回归测试：provider factory。 |
| `test_query_normalization.py` | 活动 | 回归测试：query normalization。 |
| `test_rag_debug_api.py` | 活动 | 回归测试：rag debug api。 |
| `test_real_evaluation_framework.py` | 活动 | 回归测试：real evaluation framework。 |
| `test_real_rag_models.py` | 活动 | 回归测试：real rag models。 |
| `test_real_xingchen_learn.py` | 活动 | 回归测试：real xingchen learn。 |
| `test_real_xingchen_solver.py` | 活动 | 回归测试：real xingchen solver。 |
| `test_result_deduplication.py` | 活动 | 回归测试：result deduplication。 |
| `test_result_diversity.py` | 活动 | 回归测试：result diversity。 |
| `test_retrieval_benchmark.py` | 活动 | 回归测试：retrieval benchmark。 |
| `test_retrieval_context_packet.py` | 活动 | 回归测试：retrieval context packet。 |
| `test_score_threshold.py` | 活动 | 回归测试：score threshold。 |
| `test_sensitive_files_not_tracked.py` | 活动 | 回归测试：sensitive files not tracked。 |
| `test_sensitive_values_not_logged.py` | 活动 | 回归测试：sensitive values not logged。 |
| `test_solver_not_used_for_ae_de.py` | 活动 | 回归测试：solver not used for ae de。 |
| `test_solver_quality_gate.py` | 活动 | 回归测试：solver quality gate。 |
| `test_spark_llm_provider.py` | 活动 | 回归测试：spark llm provider。 |
| `test_sse_event_order.py` | 活动 | 回归测试：sse event order。 |
| `test_sse_events.py` | 活动 | 回归测试：sse events。 |
| `test_sse_reconnect.py` | 活动 | 回归测试：sse reconnect。 |
| `test_stage_2_2_registry.py` | 活动 | 回归测试：stage 2 2 registry。 |
| `test_student_web.py` | 活动 | 回归测试：student web。 |
| `test_supervisor.py` | 活动 | 回归测试：supervisor。 |
| `test_synonym_expansion.py` | 活动 | 回归测试：synonym expansion。 |
| `test_task_api.py` | 活动 | 回归测试：task api。 |
| `test_task_cancel.py` | 活动 | 回归测试：task cancel。 |
| `test_task_creation_is_non_blocking.py` | 活动 | 回归测试：task creation is non blocking。 |
| `test_task_executor_reliability.py` | 活动 | 回归测试：task executor reliability。 |
| `test_task_idempotency.py` | 活动 | 回归测试：task idempotency。 |
| `test_task_presentation.py` | 活动 | 回归测试：task presentation。 |
| `test_task_retry.py` | 活动 | 回归测试：task retry。 |
| `test_task_router.py` | 活动 | 回归测试：task router。 |
| `test_task_runner_uses_routed_agent.py` | 活动 | 回归测试：task runner uses routed agent。 |
| `test_task_state_transitions.py` | 活动 | 回归测试：task state transitions。 |
| `test_team_launcher.py` | 活动 | 回归测试：team launcher。 |
| `test_unified_web_ui.py` | 活动 | 回归测试：unified web ui。 |
| `test_universal_academic_solver.py` | 活动 | 回归测试：universal academic solver。 |
| `test_workflow_provider.py` | 活动 | 回归测试：workflow provider。 |
| `test_xingchen_cloud_policy.py` | 活动 | 回归测试：xingchen cloud policy。 |
| `test_xingchen_export_parser.py` | 活动 | 回归测试：xingchen export parser。 |
| `test_xingchen_export_redaction.py` | 活动 | 回归测试：xingchen export redaction。 |
| `test_xingchen_minimal.py` | 活动 | 回归测试：xingchen minimal。 |
| `test_xingchen_not_published.py` | 活动 | 回归测试：xingchen not published。 |

### `apps/api/tests/fixtures`

| 文件 | 状态 | 功能 |
|---|---|---|
| `math_rendering_cases.json` | 活动 | 结构化数据集；包含 20 个顶层条目。 |
| `rag_eval_cases.json` | 活动 | 结构化数据集；包含 65 个顶层条目。 |

### `apps/api/tests/fixtures/agents`

| 文件 | 状态 | 功能 |
|---|---|---|
| `workflow_contract_cases.json` | 活动 | 结构化数据集；包含 15 个顶层条目。 |

### `apps/worker`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 活动 | 文档：Worker 预留。 |

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

### `config`

| 文件 | 状态 | 功能 |
|---|---|---|
| `learning_mastery.yaml` | 活动 | 结构化配置或数据；顶层字段：version、initial_score、initial_confidence、correct_delta、partial_delta、incorrect_delta。 |
| `model_routes.yaml` | 活动 | 结构化配置或数据；顶层字段：routes。 |
| `models.yaml` | 活动 | 结构化配置或数据；顶层字段：models。 |

### `docs`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agent_extension_guide.md` | 活动 | 文档：Agent 扩展指南。 |
| `agent_registry.md` | 活动 | 文档：Agent Registry。 |
| `api_reference.md` | 活动 | 文档：API Reference。 |
| `architecture_consolidation_audit.md` | 活动 | 文档：架构融合审计。 |
| `architecture_migration_audit.md` | 活动 | 文档：架构迁移审计。 |
| `capability_pack_design.md` | 活动 | 文档：CapabilityPack 设计。 |
| `course_pack_design.md` | 活动 | 文档：CoursePack 设计。 |
| `developer_code_navigation.md` | 活动 | 文档：芯智导学代码级开发手册。 |
| `development_guide.md` | 活动 | 文档：Development Guide。 |
| `evaluation_framework.md` | 活动 | 文档：多学科评测框架。 |
| `high_risk_verification.md` | 活动 | 文档：HIGH_RISK 校验与局部补丁。 |
| `langgraph_boundaries.md` | 活动 | 文档：LangGraph 使用边界。 |
| `legacy_cleanup_report.md` | 活动 | 文档：旧文件与功能清理记录。 |
| `local_orchestration_architecture.md` | 活动 | 文档：本地编排架构。 |
| `math_rendering_pipeline.md` | 活动 | 文档：数学公式规范化、传输与渲染。 |
| `migration_roadmap.md` | 活动 | 文档：Migration Roadmap。 |
| `model_api_configuration.md` | 活动 | 文档：国产多模型 API 配置。 |
| `rag_pipeline.md` | 活动 | 文档：RAG Pipeline。 |
| `repository_architecture_guide.md` | 活动 | 文档：芯智导学仓库完整梳理。 |
| `repository_file_catalog.md` | 活动 | 本脚本生成的 Git 范围逐文件清单。 |
| `solver_ct_migration.md` | 活动 | 文档：SolverCT 兼容迁移。 |
| `testing_guide.md` | 活动 | 文档：Testing Guide。 |
| `universal_academic_solver.md` | 活动 | 文档：通用多学科专业问题求解引擎。 |
| `xingchen_integration.md` | 活动 | 文档：讯飞模型与星辰集成。 |

### `docs/api`

| 文件 | 状态 | 功能 |
|---|---|---|
| `openapi.json` | 活动 | 结构化配置或数据文件（内容需由对应加载器校验）。 |

### `docs/architecture`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agent_runtime_foundation.md` | 活动 | 文档：Agent Runtime Foundation v1。 |
| `automatic_agent_routing_architecture.md` | 活动 | 文档：自然语言自动调度架构。 |
| `multi_agent_runtime_architecture.md` | 活动 | 文档：多工作流本地运行架构。 |
| `README.md` | 活动 | 文档：架构文档索引。 |
| `web_ui_architecture.md` | 活动 | 文档：芯智导学统一 Web UI 架构。 |
| `workflow_rag_integration_architecture.md` | 活动 | 文档：工作流与 RAG 融合架构。 |

### `docs/baseline`

| 文件 | 状态 | 功能 |
|---|---|---|
| `solver_ct_known_issues.md` | 活动 | 文档：SOLVER_CT v1.0 已知事项。 |
| `solver_ct_node_inventory.md` | 活动 | 文档：SOLVER_CT v1.0 节点清单。 |
| `solver_ct_release_checklist.md` | 活动 | 文档：本地阶段 0—1.5 发布检查清单。 |
| `solver_ct_v1.0_baseline.md` | 活动 | 文档：SOLVER_CT v1.0 冻结基线。 |

### `docs/baseline/generated`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 活动 | 文档：SOLVER_CT 导出解析结果。 |

### `docs/deployment`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agent_debug_console_guide.md` | 活动 | 文档：Agent 接入控制台指南。 |
| `conversation_memory_guide.md` | 活动 | 文档：会话与长期记忆部署指南。 |
| `debug_console_ui_guide.md` | 活动 | 文档：Debug 控制台 UI 指南。 |
| `debug_page.md` | 活动 | 文档：本地演示页面。 |
| `execution_debug_console_guide.md` | 活动 | 文档：统一 Execution Debug 使用指南。 |
| `local_development.md` | 活动 | 文档：本地开发指南。 |
| `meeting_auto_routing_demo_guide.md` | 活动 | 文档：会议自然语言自动调度演示指南。 |
| `meeting_demo_guide.md` | 活动 | 文档：会议演示指南。 |
| `meeting_demo_v2_guide.md` | 活动 | 文档：会议演示 V2 指南。 |
| `multi_workflow_frontend_guide.md` | 活动 | 文档：统一多工作流前端指南。 |
| `student_web_ui_guide.md` | 活动 | 文档：学生端 Web UI 指南。 |
| `student_web_v1_guide.md` | 活动 | 文档：学生端 Web v1 指南。 |
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
| `real_evaluation_dataset_guide.md` | 活动 | 文档：真实评测数据集接入指南。 |

### `docs/implementation`

| 文件 | 状态 | 功能 |
|---|---|---|
| `learning_quality_loop.md` | 活动 | 文档：学习质量闭环实现说明。 |

### `docs/knowledge`

| 文件 | 状态 | 功能 |
|---|---|---|
| `evidence_interaction_guide.md` | 活动 | 文档：证据交互指南。 |
| `knowledge_base_integration_guide.md` | 活动 | 文档：本地多模态知识库构建与接入指南。 |
| `local_knowledge_base_assessment.md` | 活动 | 文档：电路理论、模电、数电本地知识库审计。 |
| `local_knowledge_base_integration.md` | 活动 | 文档：本地知识库接入说明。 |
| `multimodal_rag_integration_guide.md` | 活动 | 文档：多模态 RAG 集成指南。 |
| `rag_debug_site_guide.md` | 活动 | 文档：芯智导学多模态 RAG 调试台使用指南。 |

### `docs/presentations`

| 文件 | 状态 | 功能 |
|---|---|---|
| `xinzhi_project_meeting_20260723.html` | 活动 | 静态前端页面：芯智导学｜项目进展、架构与下一阶段计划。 |

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
| `frontend_visual_refinement_report.md` | 活动 | 文档：前端视觉精修报告。 |
| `internal_agent_model_evaluation_report.md` | 活动 | 文档：内部模型 Agent 首轮评测报告。 |
| `knowledge_base_audit_report.md` | 活动 | 文档：本地知识库审计报告。 |
| `local_latency_optimization_report.md` | 活动 | 文档：本地延迟优化报告。 |
| `local_routing_latency_report.md` | 活动 | 文档：本地自动调度延迟报告。 |
| `multi_agent_compatibility_report.md` | 活动 | 文档：多 Agent 兼容性报告。 |
| `multimodal_rag_implementation_report.md` | 活动 | 文档：多模态 RAG 实施报告。 |
| `rag_debug_site_screenshot.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `rag_quality_improvement_report.md` | 活动 | 文档：RAG 质量改进报告。 |
| `web_ui_refactor_report.md` | 活动 | 文档：统一 Web UI 重构报告。 |
| `workflow_rag_integration_report.md` | 活动 | 文档：工作流与 RAG 融合实施报告。 |

### `docs/reviews/web_ui_baseline`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agents-before.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `rag-before.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `student-before.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `docs/reviews/web_ui_screenshots`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01-home-light.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `02-home-dark.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `03-student-empty.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `04-student-completed-answer.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `05-student-image-solver.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `06-rag-overview.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `07-rag-retrieval-results.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `08-agent-list.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `09-agent-detail.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `10-system-status.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `11-demo-center.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `12-presentation-mode.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `13-laptop-1366x768.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `14-mobile-390x844.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `docs/reviews/workspace_v2_baseline`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01-home-light.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `02-home-dark.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `03-student-empty.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `docs/reviews/workspace_v2_screenshots`

| 文件 | 状态 | 功能 |
|---|---|---|
| `01-workspace-empty.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `02-ct-knowledge-answer.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `03-context-evidence.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `04-evidence-linked.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `05-process-simple.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `06-answer-info.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `07-ae-knowledge-answer.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `08-de-knowledge-answer.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `09-solver-text.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `10-solver-image-ready.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `11-mock-or-fallback-boundary.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `12-execution-debug.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `13-evidence-flow-comparison.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `14-demo-center.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `15-presentation-1280x720.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `16-workspace-dark.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |
| `17-workspace-mobile.png` | 活动 | 界面验收、测试或文档使用的图像资产。 |

### `docs/workflows`

| 文件 | 状态 | 功能 |
|---|---|---|
| `agent_contract_reference.md` | 活动 | 文档：Agent 契约参考。 |
| `agent_scaffold_guide.md` | 活动 | 文档：Agent 脚手架指南。 |
| `development_mock_agent_guide.md` | 活动 | 文档：开发态 Mock Agent 指南。 |
| `new_agent_integration_guide.md` | 活动 | 文档：新 Agent 接入指南。 |
| `solver_ct_v1_1_integration_changes.md` | 活动 | 文档：SOLVER_CT v1.1 integration 最小修改说明。 |
| `workflow_input_contracts.md` | 活动 | 文档：工作流输入契约。 |
| `workflow_output_validation_guide.md` | 活动 | 文档：工作流输出校验与展示指南。 |

### `evaluation/automatic_routing`

| 文件 | 状态 | 功能 |
|---|---|---|
| `cases.json` | 活动 | 结构化数据集；包含 70 个顶层条目。 |

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

### `evaluation/circuit_theory`

| 文件 | 状态 | 功能 |
|---|---|---|
| `benchmark_manifest.json` | 活动 | 结构化配置或数据；顶层字段：benchmark_id、course_id、solver_id、version、case_groups、metrics。 |
| `README.md` | 活动 | 文档：电路理论回归评测脚手架。 |
| `regression_report_template.md` | 活动 | 文档：SOLVER_CT 回归报告。 |

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
| `run_retrieval_benchmark.py` | 活动 | Python 模块；定义 discover_path、load_cases、portable_corpus_path、percentile_95、source_rank 等。 |
| `summarize_results.py` | 活动 | Python 模块；定义 main。 |
| `validate_cases.py` | 活动 | Python 模块；定义 validate_case、main。 |

### `evaluation/manifests`

| 文件 | 状态 | 功能 |
|---|---|---|
| `dataset_manifest.yaml` | 活动 | 结构化配置或数据；顶层字段：schema_version、datasets。 |

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

### `evaluation/schemas`

| 文件 | 状态 | 功能 |
|---|---|---|
| `evaluation_case.schema.json` | 活动 | 结构化配置或数据；顶层字段：$schema、title、type、required、properties、additionalProperties。 |
| `evaluation_rubric.schema.json` | 活动 | 结构化配置或数据；顶层字段：$schema、title、type、properties、additionalProperties。 |

### `knowledge_config`

| 文件 | 状态 | 功能 |
|---|---|---|
| `knowledge_base_index_config.example.yaml` | 活动 | 结构化配置或数据；顶层字段：version、multimodal_level、sources、parsing、retrieval、images。 |
| `README.md` | 活动 | 文档：本地知识库元数据覆盖层。 |

### `knowledge_config/corrections`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE.yaml` | 活动 | 结构化配置或数据；顶层字段：rules。 |
| `CT.yaml` | 活动 | 结构化配置或数据；顶层字段：rules。 |
| `DE.yaml` | 活动 | 结构化配置或数据；顶层字段：rules。 |

### `knowledge_config/courses`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE.yaml` | 活动 | 结构化配置或数据；顶层字段：course_id、course_name、document_patterns、chapter_aliases、excluded_paths。 |
| `CT.yaml` | 活动 | 结构化配置或数据；顶层字段：course_id、course_name、document_patterns、chapter_aliases、retrieval_topic_boosts、excluded_paths。 |
| `DE.yaml` | 活动 | 结构化配置或数据；顶层字段：course_id、course_name、document_patterns、chapter_aliases、retrieval_topic_boosts、excluded_paths。 |

### `knowledge_config/synonyms`

| 文件 | 状态 | 功能 |
|---|---|---|
| `AE.yaml` | 活动 | 结构化配置或数据；顶层字段：运算放大器、负反馈、场效应管、滤波器。 |
| `CT.yaml` | 活动 | 结构化配置或数据；顶层字段：戴维南、结点、相量、互感、串联谐振。 |
| `DE.yaml` | 活动 | 结构化配置或数据；顶层字段：触发器、施密特触发电路、回差电压、卡诺图、传输门、格雷码。 |

### `local_knowledge`

| 文件 | 状态 | 功能 |
|---|---|---|
| `README.md` | 活动 | 文档：本地知识库挂载点。 |

### `local_knowledge/AE`

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

### `scripts`

| 文件 | 状态 | 功能 |
|---|---|---|
| `__init__.py` | 活动 | Repository automation helpers that are importable by tests. |
| `agent_cli.py` | 活动 | Python 模块；定义 _print、_summary、_dry_run、build_parser、_csv 等。 |
| `benchmark_agent_runtime.py` | 活动 | Local synthetic benchmark for conversation-context overhead. |
| `benchmark_auto_routing.py` | 活动 | Python 模块；定义 percentile_95、main。 |
| `check.ps1` | 活动 | 跨平台运行脚本：check。 |
| `check.sh` | 活动 | 跨平台运行脚本：check。 |
| `check_environment.py` | 活动 | Python 模块；定义 main。 |
| `check_sensitive_files.py` | 活动 | Python 模块；定义 tracked_files、scan、main。 |
| `compare_evaluation_reports.py` | 活动 | Python 模块；定义 load、main。 |
| `demo_cli.py` | 活动 | Python 模块；定义 request_json、preflight、_check_routes、_check_rag_status、_check_agent_status 等。 |
| `dev.ps1` | 活动 | 跨平台运行脚本：dev。 |
| `dev.sh` | 活动 | 跨平台运行脚本：dev。 |
| `docker_dev.ps1` | 活动 | 跨平台运行脚本：docker dev。 |
| `docker_dev.sh` | 活动 | 跨平台运行脚本：docker dev。 |
| `docker_down.ps1` | 活动 | 跨平台运行脚本：docker down。 |
| `docker_down.sh` | 活动 | 跨平台运行脚本：docker down。 |
| `evaluate_model_agents.py` | 活动 | Python 模块；定义 parse_args、load_cases、run、validate_result、get_path 等。 |
| `export_openapi.py` | 活动 | Python 模块；定义 export_openapi、main。 |
| `generate_repository_catalog.py` | 活动 | Generate the deterministic, Git-scoped repository file catalog. |
| `import_evaluation_cases.py` | 活动 | Python 模块；定义 load_rows、main。 |
| `init_db.ps1` | 活动 | 跨平台运行脚本：init db。 |
| `init_db.sh` | 活动 | 跨平台运行脚本：init db。 |
| `inspect_xingchen_workflow.py` | 活动 | Python 模块；定义 PublicNode、first_value、find_named_list、sensitive_paths、private_content 等。 |
| `knowledge_base_cli.py` | 活动 | Python 模块；定义 builder_from_settings、selected_courses、rag_components、command_audit、command_build 等。 |
| `math_renderer_smoke.js` | 活动 | 静态前端交互逻辑：math renderer smoke。 |
| `migrate_legacy_index.py` | 活动 | Python 模块；定义 parser、main。 |
| `move_orphan_images.py` | 活动 | Python 模块；定义 _is_within、_load_jsonl、collect_moves、execute、main。 |
| `rag_cpu_profile.ps1` | 活动 | 跨平台运行脚本：rag cpu profile。 |
| `rebuild_index.py` | 活动 | Python 配置或执行模块。 |
| `run_evaluation.py` | 活动 | Python 模块；定义 parse_args、validate_paid_guard、validate_cases、_evaluation_schema_revision、evaluation_settings 等。 |
| `run_regression.py` | 活动 | Python 模块；定义 main。 |
| `run_web_ui_browser_acceptance.js` | 活动 | 静态前端交互逻辑：run web ui browser acceptance。 |
| `smoke_test_models.py` | 活动 | Python 模块；定义 ResultRow、parser、response_row、run、text_call 等。 |
| `start_demo.ps1` | 活动 | 跨平台运行脚本：start demo。 |
| `stop.ps1` | 活动 | 跨平台运行脚本：stop。 |
| `stop.sh` | 活动 | 跨平台运行脚本：stop。 |
| `student_browser_smoke.js` | 活动 | 静态前端交互逻辑：student browser smoke。 |
| `team_launcher.py` | 活动 | Python 模块；定义 LaunchError、parse_dotenv、ensure_env_file、build_host_environment、configuration_summary 等。 |
| `test.ps1` | 活动 | 跨平台运行脚本：test。 |
| `test.sh` | 活动 | 跨平台运行脚本：test。 |
| `validate_completed_workflows.py` | 活动 | Python 模块；定义 cases、run、main。 |
| `validate_config.py` | 活动 | Python 模块；定义 safe_status、validate、main。 |
| `validate_evaluation_cases.py` | 活动 | Python 模块；定义 main。 |
| `xingchen_smoke_test.py` | 活动 | Python 模块；定义 run。 |

### `tests/regression/cases`

| 文件 | 状态 | 功能 |
|---|---|---|
| `cloud_timeout.json` | 活动 | 结构化配置或数据；顶层字段：case_id、input、expected_course、expected_intent、expected_status、required_keywords。 |
| `follow_up.json` | 活动 | 结构化配置或数据；顶层字段：case_id、input、session_context、expected_course、expected_intent、expected_status。 |
| `knowledge_qa.json` | 活动 | 结构化配置或数据；顶层字段：case_id、input、expected_course、expected_intent、required_keywords、forbidden_claims。 |
| `solver_boundary.json` | 活动 | 结构化配置或数据；顶层字段：case_id、input、expected_course、expected_intent、expected_agent、expected_status。 |
| `solver_route.json` | 活动 | 结构化配置或数据；顶层字段：case_id、input、expected_course、expected_intent、expected_agent、expected_status。 |
