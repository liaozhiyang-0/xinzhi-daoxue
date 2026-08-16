from __future__ import annotations

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.agents import AgentRegistry, TaskRouter
    from app.agents.internal import InternalAgentHub
    from app.capabilities import CapabilityRegistry
    from app.core.config import Settings
    from app.courses import CourseRegistry
    from app.observability import ModelTracer, TraceStore
    from app.orchestrator import GraphFactory, XZDSupervisor
    from app.providers.base import AgentProvider
    from app.providers.llm import DashScopeQwenProvider, IflytekSparkProvider
    from app.runtime import RuntimeHandlerRegistry, RuntimeSubagentRegistry
    from app.services.academic_solver_service import AcademicProblemSolverService
    from app.services.answer_disclosure import AnswerDisclosureService
    from app.services.auth_service import LoginRateLimiter
    from app.services.context_assembly import ContextAssemblyService
    from app.services.context_budget import ContextBudgetManager
    from app.services.context_cache import ContextAssemblyCache
    from app.services.evidence_packet_adapter import EvidencePacketAdapterService
    from app.services.external_retrieval import ExternalContentFetcher
    from app.services.general_question_service import GeneralQuestionService
    from app.services.hint_policy import HintPolicyService
    from app.services.internal_agent_execution import InternalAgentExecutionService
    from app.services.knowledge_base import KnowledgeBaseService
    from app.services.knowledge_ocr_review_cache import (
        KnowledgeOCRReviewSnapshotCache,
    )
    from app.services.knowledge_qa_service import KnowledgeQAService
    from app.services.learning_loop import LearningLoopService
    from app.services.learning_progress_runtime import (
        LearningProgressRuntimeService,
    )
    from app.services.model_registry import ModelRegistry
    from app.services.model_service import ModelService
    from app.services.next_check_question import NextCheckQuestionService
    from app.services.rag_debug import RAGDebugService
    from app.services.rag_retrieval import RAGRetrievalService
    from app.services.research_frontier_service import ResearchFrontierService
    from app.services.research_knowledge import ResearchKnowledgeService
    from app.services.retrieval_context import RetrievalContextService
    from app.services.runtime_agent_readiness import RuntimeAgentReadinessService
    from app.services.scenario_catalog import ScenarioCatalog
    from app.services.scenario_evidence_review import ScenarioEvidenceReviewService
    from app.services.session_compaction import SessionCompactionService
    from app.services.skill_registry import SkillRegistry
    from app.services.solution_packet_adapter import SolutionPacketAdapterService
    from app.services.storage import StorageService
    from app.services.student_verification import StudentVerificationService
    from app.services.task_executor import TaskExecutor
    from app.services.task_queue import TaskQueue
    from app.services.teaching_execution_planner import TeachingExecutionPlanner
    from app.services.teaching_foundation import TeachingFoundationService
    from app.services.teaching_interaction import TeachingInteractionService
    from app.services.teaching_interaction_runtime import (
        TeachingInteractionRuntimeService,
    )
    from app.tools import ToolRegistry


@dataclass(slots=True)
class ApplicationContainer:
    """Typed composition root for the services exposed through ``app.state``.

    The HTTP layer historically accessed these objects as dynamic Starlette
    state attributes.  The container is now the canonical assembly object,
    while :meth:`install` keeps those attributes as a compatibility facade for
    existing routes, tests, and worker integrations.
    """

    settings: Settings
    engine: Any
    session_factory: Any
    provider: AgentProvider
    development_mock_provider: AgentProvider
    agent_contract_results: dict[str, Any]
    agent_registry: AgentRegistry
    task_router: TaskRouter
    trace_store: TraceStore
    spark_provider: IflytekSparkProvider
    qwen_provider: DashScopeQwenProvider
    model_registry: ModelRegistry
    model_tracer: ModelTracer
    model_service: ModelService
    course_registry: CourseRegistry
    capability_registry: CapabilityRegistry
    skill_registry: SkillRegistry
    error_pool: Any
    solution_packets: SolutionPacketAdapterService
    evidence_packets: EvidencePacketAdapterService
    teaching_foundation: TeachingFoundationService
    teaching_planner: TeachingExecutionPlanner
    student_verification: StudentVerificationService
    hint_policy: HintPolicyService
    next_checks: NextCheckQuestionService
    answer_disclosure: AnswerDisclosureService
    teaching_interactions: TeachingInteractionService
    teaching_interaction_runtime: TeachingInteractionRuntimeService
    learning_progress_runtime: LearningProgressRuntimeService
    tool_registry: ToolRegistry
    runtime_subagent_registry: RuntimeSubagentRegistry
    runtime_handler_registry: RuntimeHandlerRegistry
    runtime_agent_readiness: RuntimeAgentReadinessService
    graph_factory: GraphFactory
    graph_checkpointer: Any
    academic_solver: AcademicProblemSolverService
    storage: StorageService
    internal_agent_hub: InternalAgentHub
    general_question: GeneralQuestionService
    research_frontier: ResearchFrontierService
    internal_agent_execution: InternalAgentExecutionService
    supervisor: XZDSupervisor
    knowledge_base: KnowledgeBaseService
    rag_retrieval: RAGRetrievalService
    external_search: Any
    external_fetcher: ExternalContentFetcher
    research_knowledge: ResearchKnowledgeService
    context_service: RetrievalContextService
    knowledge_qa: KnowledgeQAService
    rag_debug: RAGDebugService
    auth_rate_limiter: LoginRateLimiter
    task_engine: Any
    task_coordinator: Any
    task_executor: TaskExecutor
    task_queue: TaskQueue | None
    learning_loop: LearningLoopService
    context_budget: ContextBudgetManager
    context_cache: ContextAssemblyCache
    scenario_catalog: ScenarioCatalog
    scenario_evidence_review: ScenarioEvidenceReviewService
    knowledge_ocr_review_cache: KnowledgeOCRReviewSnapshotCache
    context_assembly: ContextAssemblyService
    session_compaction: SessionCompactionService

    def install(self, app: Any) -> None:
        """Install legacy state attributes without rebuilding a string map."""

        for field in fields(self):
            setattr(app.state, field.name, getattr(self, field.name))
