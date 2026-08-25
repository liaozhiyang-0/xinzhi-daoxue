from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents import AgentRegistry, TaskRouter
from app.application.tasks import TaskLeaseManager
from app.application.tasks.progress import TaskProgressReporter
from app.courses import CourseRegistry
from app.providers.base import AgentProvider
from app.providers.retrieval.academic import AcademicSearchService
from app.runtime import RuntimeHandlerRegistry, RuntimeSubagentRegistry
from app.services.academic_paper_review import AcademicPaperReviewService
from app.services.academic_search_planner import AcademicSearchPlannerService
from app.services.academic_solver_runtime import AcademicSolverRuntimeService
from app.services.academic_writing_runtime import AcademicWritingRuntimeService
from app.services.agent_result_governance import (
    AgentResultValidatorRegistry,
    BusinessResultRendererRegistry,
)
from app.services.agent_runtime import AgentExecutionPlanner
from app.services.assignment_review_runtime import AssignmentReviewRuntimeService
from app.services.context_assembly import ContextAssemblyService
from app.services.external_research_runtime import ExternalResearchRuntimeService
from app.services.external_retrieval import (
    ExternalContentFetcher,
)
from app.services.external_retrieval_execution import (
    ExternalRetrievalExecutionService,
)
from app.services.external_retrieval_gateway import ExternalRetrievalGateway
from app.services.fallback_routing import FallbackRoutingService
from app.services.general_model_fallback_runtime import (
    GeneralModelFallbackRuntimeService,
)
from app.services.general_question_runtime import GeneralQuestionRuntimeService
from app.services.generic_goal_runtime import GenericGoalRuntimeService
from app.services.internal_agent_execution import InternalAgentExecutionService
from app.services.knowledge_base import KnowledgeBaseService
from app.services.knowledge_qa_runtime import KnowledgeQARuntimeService
from app.services.knowledge_qa_service import KnowledgeQAService
from app.services.learning_outcome import LearningOutcomeService
from app.services.lesson_prep_runtime import LessonPrepRuntimeService
from app.services.math_formatting_service import MathFormattingService
from app.services.overall_routing import OverallRoutingService
from app.services.rag_retrieval import RAGRetrievalService
from app.services.reflection_policy import (
    ReflectionPolicy,
    ReflectionPolicyConfig,
    parse_agent_allowlist,
)
from app.services.reflection_service import (
    InternalCriticWorker,
    InternalRevisionWorker,
    ReflectionService,
)
from app.services.research_analysis_runtime import ResearchAnalysisRuntimeService
from app.services.research_frontier_service import ResearchFrontierService
from app.services.research_knowledge import ResearchKnowledgeService
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from app.services.runtime_child_run import RuntimeChildRunService
from app.services.runtime_execution_boundary import RuntimeExecutionBoundary
from app.services.runtime_goal_intake import RuntimeGoalIntakePolicy
from app.services.runtime_launch_policy import RuntimeLaunchPolicy
from app.services.runtime_persistence_hooks import RuntimePersistenceHooks
from app.services.runtime_release_authorization import (
    RuntimeReleaseAuthorizationRegistry,
)
from app.services.runtime_request_preparation import (
    RuntimeRequestPreparationService,
)
from app.services.runtime_result_pipeline import RuntimeResultPipeline
from app.services.runtime_run_lifecycle import RuntimeRunLifecycleService
from app.services.runtime_task_engine import RuntimeTaskComponents, TaskRuntimeLifecycle
from app.services.scenario_output_contract import ScenarioOutputContractService
from app.services.session_compaction import SessionCompactionService
from app.services.solver_quality_gate import SolverQualityGateService
from app.services.student_attempts import StudentAttemptService
from app.services.task_completion import TaskCompletionService
from app.services.task_failure_service import TaskFailureService
from app.services.task_post_processing import TaskPostProcessingService
from app.services.task_result_commit import TaskResultCommitService
from app.services.task_result_presentation import TaskResultPresentationService
from app.services.task_runtime_execution import TaskRuntimeExecutionService
from app.services.task_runtime_preparation import TaskRuntimePreparationService
from app.services.task_session_commit import TaskSessionCommitService
from app.services.teaching_foundation import TeachingFoundationService
from app.tools.registry import ToolRegistry


def _runtime_service_agent_ids(service: object) -> tuple[str, ...]:
    """Return the primary and alias Agent IDs owned by one Runtime service."""

    values = {str(getattr(service, "agent_id", ""))}
    supported = getattr(service, "supported_agent_ids", ())
    if isinstance(supported, (tuple, list, set, frozenset)):
        values.update(str(item) for item in supported if str(item))
    return tuple(sorted(item for item in values if item))


def build_runtime_task_engine(
    session_factory: async_sessionmaker[AsyncSession],
    provider: AgentProvider,
    knowledge_base: KnowledgeBaseService,
    agent_registry: AgentRegistry,
    knowledge_qa: KnowledgeQAService,
    rag_retrieval: RAGRetrievalService | None = None,
    internal_agents: InternalAgentExecutionService | None = None,
    course_registry: CourseRegistry | None = None,
    *,
    context_assembly: ContextAssemblyService | None = None,
    session_compaction: SessionCompactionService | None = None,
    teaching_foundation: TeachingFoundationService | None = None,
    learning_outcome: LearningOutcomeService | None = None,
    external_search: AcademicSearchService | None = None,
    external_fetcher: ExternalContentFetcher | None = None,
    external_paper_reviewer: AcademicPaperReviewService | None = None,
    external_search_planner: AcademicSearchPlannerService | None = None,
    research_frontier: ResearchFrontierService | None = None,
    research_knowledge: ResearchKnowledgeService | None = None,
    overall_router: OverallRoutingService | None = None,
    tool_registry: ToolRegistry | None = None,
    runtime_subagent_registry: RuntimeSubagentRegistry | None = None,
    runtime_handler_registry: RuntimeHandlerRegistry | None = None,
    development_mock_provider: AgentProvider | None = None,
    task_leases: TaskLeaseManager | None = None,
) -> TaskRuntimeLifecycle:
    settings = knowledge_base.settings
    runtime_hooks = RuntimePersistenceHooks(session_factory)
    external_gateway = ExternalRetrievalGateway(
        session_factory,
        ExternalRetrievalExecutionService(
            settings=settings,
            external_search=external_search,
            external_fetcher=external_fetcher,
            external_paper_reviewer=external_paper_reviewer,
            external_search_planner=external_search_planner,
        ),
    )
    canary_release = RuntimeCanaryReleaseRegistry.from_paths(
        settings.agent_runtime_canary_artifacts,
        semantic_paths=settings.agent_runtime_semantic_evidence,
    )
    release_authorizations = RuntimeReleaseAuthorizationRegistry.from_paths(
        settings.agent_runtime_release_authorizations
    )
    child_run = (
        RuntimeChildRunService(
            session_factory,
            internal_agents,
            development_mock_provider=development_mock_provider,
            checkpoint_hook=runtime_hooks.checkpoint,
        )
        if internal_agents is not None
        else None
    )
    # Runtime route refinement is retained only for the explicit shadow
    # compatibility mode. Controlled/active Planner modes receive the
    # immutable preflight route and CanonicalPlan without a second router.
    compatibility_overall_router = (
        overall_router if settings.planner_mode == "shadow" else None
    )
    compatibility_fallback_router = (
        FallbackRoutingService(
            agent_registry,
            TaskRouter(agent_registry, settings),
            provider,
        )
        if settings.planner_mode == "shadow"
        else None
    )
    request_preparation = RuntimeRequestPreparationService(
        AgentExecutionPlanner(agent_registry, settings),
        compatibility_overall_router,
        context_assembly,
        compatibility_fallback_router,
    )
    external_research = (
        ExternalResearchRuntimeService(
            research_frontier,
            policy=agent_registry.get(
                ResearchFrontierService.agent_id
            ).external_retrieval,
            retrieve=external_gateway.retrieve_with_deadline,
            external_event_hook=external_gateway.append_event,
            external_enabled=settings.external_retrieval_enabled,
            enabled=True,
            settings=settings,
        )
        if research_frontier is not None
        else None
    )
    academic_solver = (
        AcademicSolverRuntimeService(
            internal_agents,
            enabled=True,
            tool_registry=tool_registry,
            rag_retrieval=rag_retrieval,
            retrieval_context=knowledge_qa.context_service,
            subagent_registry=runtime_subagent_registry,
            provider_timeout_ms=int(
                settings.academic_solver_timeout_seconds * 1000
            ),
            provider_max_retries=0,
        )
        if internal_agents is not None
        else None
    )
    general_question = (
        GeneralQuestionRuntimeService(
            internal_agents,
            enabled=True,
            auto_enabled=True,
            canary_enabled=True,
            tool_registry=tool_registry,
            rag_retrieval=rag_retrieval,
            retrieval_context=knowledge_qa.context_service,
            subagent_registry=runtime_subagent_registry,
            child_run_service=child_run,
        )
        if internal_agents is not None
        else None
    )
    general_fallback = (
        GeneralModelFallbackRuntimeService(
            internal_agents,
            enabled=True,
            auto_enabled=True,
            canary_enabled=True,
            tool_registry=tool_registry,
            rag_retrieval=rag_retrieval,
            retrieval_context=knowledge_qa.context_service,
            subagent_registry=runtime_subagent_registry,
            child_run_service=child_run,
        )
        if internal_agents is not None
        else None
    )
    lesson_prep = (
        LessonPrepRuntimeService(
            internal_agents,
            enabled=True,
            tool_registry=tool_registry,
            rag_retrieval=rag_retrieval,
            retrieval_context=knowledge_qa.context_service,
            subagent_registry=runtime_subagent_registry,
            child_run_service=child_run,
        )
        if internal_agents is not None
        else None
    )
    assignment_review = (
        AssignmentReviewRuntimeService(
            internal_agents,
            enabled=True,
            tool_registry=tool_registry,
            rag_retrieval=rag_retrieval,
            retrieval_context=knowledge_qa.context_service,
            subagent_registry=runtime_subagent_registry,
            child_run_service=child_run,
        )
        if internal_agents is not None
        else None
    )
    academic_writing = (
        AcademicWritingRuntimeService(
            internal_agents,
            enabled=True,
            tool_registry=tool_registry,
            rag_retrieval=rag_retrieval,
            retrieval_context=knowledge_qa.context_service,
            subagent_registry=runtime_subagent_registry,
            child_run_service=child_run,
        )
        if internal_agents is not None
        else None
    )
    generic_goal = (
        GenericGoalRuntimeService(
            runtime_handler_registry,
            intake_policy=RuntimeGoalIntakePolicy.from_config(
                settings.agent_runtime_goal_capabilities
            ),
        )
        if runtime_handler_registry is not None
        else None
    )
    research_analysis = (
        ResearchAnalysisRuntimeService(internal_agents, enabled=True)
        if internal_agents is not None
        else None
    )
    runtime_lifecycle = RuntimeRunLifecycleService(
        enabled=True,
        timeout_ms=settings.workflow_default_timeout_seconds * 1000,
        max_retries=settings.workflow_max_retries,
    )
    knowledge_runtime = KnowledgeQARuntimeService(knowledge_qa, enabled=True)
    business_services = [
        service
        for service in (
            academic_solver,
            general_question,
            general_fallback,
            lesson_prep,
            assignment_review,
            academic_writing,
            knowledge_runtime,
            external_research,
            generic_goal,
        )
        if service is not None
    ]
    runtime_boundary = RuntimeExecutionBoundary(
        runtime_lifecycle,
        research_analysis,
        request_preparation=request_preparation,
        business_services=business_services,
        # The active composition root never injects the historical Provider
        # execution bridge. Historical data may still be read, but it cannot
        # regain execution authority through this boundary.
        legacy_provider=None,
    )
    launch_policy = RuntimeLaunchPolicy(
        release_gate_required=settings.agent_runtime_release_gate_required,
        local_agents=(
            agent_id
            for service in (*business_services, research_analysis)
            if service is not None
            if getattr(service, "agent_id", "") != "*"
            for agent_id in _runtime_service_agent_ids(service)
        ),
    )
    result_pipeline = RuntimeResultPipeline(
        agent_registry,
        settings,
        AgentResultValidatorRegistry(),
        ScenarioOutputContractService(),
        SolverQualityGateService(),
        course_registry=course_registry,
        teaching_foundation=teaching_foundation,
    )
    reflection_worker = (
        InternalCriticWorker(internal_agents.hub)
        if internal_agents is not None
        else None
    )
    reflection = ReflectionService(
        ReflectionPolicy(
            ReflectionPolicyConfig(
                shadow_enabled=settings.reflection_shadow_enabled,
                revision_enabled=settings.reflection_revision_enabled,
                allowed_agent_ids=parse_agent_allowlist(
                    settings.reflection_canary_agent_ids
                ),
                critic_budget_tokens=settings.reflection_critic_budget_tokens,
                critic_budget_ms=settings.reflection_critic_budget_ms,
            )
        ),
        critic=reflection_worker,
        reviser=(
            InternalRevisionWorker(reflection_worker)
            if reflection_worker is not None
            else None
        ),
    )
    presentation = TaskResultPresentationService(
        BusinessResultRendererRegistry(),
        MathFormattingService(),
    )
    session_commit = TaskSessionCommitService(
        settings,
        learning_outcome=learning_outcome,
        student_attempts=StudentAttemptService(),
        compaction_enabled=session_compaction is not None,
    )
    leases = task_leases or TaskLeaseManager(session_factory, settings)
    task_failures = TaskFailureService(
        session_factory,
        settings,
        runtime_boundary,
        provider_name=provider.provider_name,
    )
    progress = TaskProgressReporter(session_factory)
    post_processing = TaskPostProcessingService(
        session_factory,
        session_compaction=session_compaction,
        research_knowledge=research_knowledge,
    )
    return TaskRuntimeLifecycle(
        RuntimeTaskComponents(
            rag_retrieval=rag_retrieval,
            runtime_hooks=runtime_hooks,
            runtime_lifecycle=runtime_lifecycle,
            runtime_canary_release=canary_release,
            runtime_release_authorizations=release_authorizations,
            runtime_launch_policy=launch_policy,
            runtime_boundary=runtime_boundary,
            task_failures=task_failures,
            completion=TaskCompletionService(
                session_factory,
                presentation,
                session_commit,
                TaskResultCommitService(runtime_boundary),
                task_failures,
                post_processing,
            ),
            post_processing=post_processing,
            preparation=TaskRuntimePreparationService(
                session_factory,
                provider,
                agent_registry,
                internal_agents,
                leases,
                task_failures,
                runtime_boundary,
                launch_policy,
                runtime_lifecycle,
                progress,
            ),
            runtime_execution=TaskRuntimeExecutionService(
                runtime_boundary,
                runtime_hooks,
                result_pipeline,
                progress,
                post_processing,
                plan_proposals_enabled=settings.agent_runtime_plan_proposals_enabled,
                reflection=reflection,
            ),
            task_leases=leases,
            external_retrieval_gateway=external_gateway,
        )
    )
