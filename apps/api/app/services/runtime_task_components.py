from __future__ import annotations

from dataclasses import dataclass

from app.application.tasks import TaskLeaseManager
from app.services.external_retrieval_gateway import ExternalRetrievalGateway
from app.services.rag_retrieval import RAGRetrievalService
from app.services.runtime_canary_release import RuntimeCanaryReleaseRegistry
from app.services.runtime_execution_boundary import RuntimeExecutionBoundary
from app.services.runtime_launch_policy import RuntimeLaunchPolicy
from app.services.runtime_persistence_hooks import RuntimePersistenceHooks
from app.services.runtime_release_authorization import (
    RuntimeReleaseAuthorizationRegistry,
)
from app.services.runtime_run_lifecycle import RuntimeRunLifecycleService
from app.services.task_completion import TaskCompletionService
from app.services.task_failure_service import TaskFailureService
from app.services.task_post_processing import TaskPostProcessingService
from app.services.task_runtime_execution import TaskRuntimeExecutionService
from app.services.task_runtime_preparation import TaskRuntimePreparationService


@dataclass(frozen=True, slots=True)
class RuntimeTaskComponents:
    """Fully assembled dependencies consumed by the task execution engine."""

    rag_retrieval: RAGRetrievalService | None
    runtime_hooks: RuntimePersistenceHooks
    runtime_lifecycle: RuntimeRunLifecycleService
    runtime_canary_release: RuntimeCanaryReleaseRegistry
    runtime_release_authorizations: RuntimeReleaseAuthorizationRegistry
    runtime_launch_policy: RuntimeLaunchPolicy
    runtime_boundary: RuntimeExecutionBoundary
    task_failures: TaskFailureService
    completion: TaskCompletionService
    post_processing: TaskPostProcessingService
    preparation: TaskRuntimePreparationService
    runtime_execution: TaskRuntimeExecutionService
    task_leases: TaskLeaseManager
    external_retrieval_gateway: ExternalRetrievalGateway
