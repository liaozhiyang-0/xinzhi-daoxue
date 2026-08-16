from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from time import perf_counter

from app.agents import AgentRegistry
from app.core.errors import AppError, ProviderCancelledError
from app.providers.base import AgentProvider
from app.runtime import (
    AgentRun,
    RuntimeNodeError,
    RuntimeRunSuspended,
)
from app.services.internal_agent_execution import InternalAgentExecutionService
from app.services.runtime_launch_policy import RuntimeLaunchPolicy
from app.services.runtime_task_components import RuntimeTaskComponents

logger = logging.getLogger(__name__)


def _runtime_failure_message(error_code: str) -> str:
    """Translate internal Runtime failures into actionable user text."""

    if error_code in {"model_provider_not_configured", "not_configured"}:
        return "当前所需模型尚未配置，请完成配置后再重试。"
    if error_code in {
        "model_provider_error",
        "provider_error",
        "provider_timeout",
        "model_provider_unavailable",
        "model_timeout",
    }:
        return "模型服务暂时不可用，请稍后重试。"
    if error_code in {
        "subagent_child_result_missing",
        "provider_runtime_result_missing",
        "runtime_node_error",
    }:
        return "任务执行未生成完整结果，请稍后重试。"
    return "任务执行未完成，请查看任务详情后决定是否重试。"

def utc_now() -> datetime:
    return datetime.now(UTC)


class TaskRuntimeLifecycle:
    """Own the persisted task prepare, execute, terminal, and shutdown flow."""

    def __init__(self, components: RuntimeTaskComponents) -> None:
        self.rag_retrieval = components.rag_retrieval
        self.runtime_hooks = components.runtime_hooks
        self.runtime_lifecycle = components.runtime_lifecycle
        self.runtime_canary_release = components.runtime_canary_release
        self.runtime_release_authorizations = (
            components.runtime_release_authorizations
        )
        self.runtime_boundary = components.runtime_boundary
        self.task_failures = components.task_failures
        self.completion = components.completion
        self.post_processing = components.post_processing
        self.preparation = components.preparation
        self._runtime_launch_policy = components.runtime_launch_policy
        self.runtime_execution = components.runtime_execution
        self.task_leases = components.task_leases
        self.external_retrieval_gateway = components.external_retrieval_gateway
        self._provider = components.preparation.provider
        self._agent_registry = components.preparation.agent_registry
        self._internal_agents = components.preparation.internal_agents
        self._shutting_down = False
        self.execution_owner = self.task_leases.execution_owner

    @property
    def runtime_launch_policy(self) -> RuntimeLaunchPolicy:
        """Expose the launch policy while keeping preparation in sync.

        The migrated engine is assembled from several focused services, but
        older callers and tests still configure the policy on the engine
        facade.  Treat that facade as the single write boundary so a policy
        replacement cannot leave request preparation using a stale object.
        """

        return self._runtime_launch_policy

    @runtime_launch_policy.setter
    def runtime_launch_policy(self, value: RuntimeLaunchPolicy) -> None:
        self._runtime_launch_policy = value
        if hasattr(self, "preparation"):
            self.preparation.launch_policy = value

    @property
    def provider(self) -> AgentProvider:
        """Expose the configured provider and propagate test/runtime swaps."""

        return self._provider

    @provider.setter
    def provider(self, value: AgentProvider) -> None:
        self._provider = value
        if not hasattr(self, "preparation"):
            return
        self.preparation.provider = value
        request_preparation = self.runtime_boundary.request_preparation
        fallback_router = getattr(request_preparation, "fallback_router", None)
        if fallback_router is not None:
            fallback_router.provider = value
        for service in self.runtime_boundary.business_registry.services():
            if hasattr(service, "provider"):
                service.provider = value
        if hasattr(self.task_failures, "provider_name"):
            provider_name = getattr(value, "provider_name", "")
            if isinstance(provider_name, str) and provider_name:
                self.task_failures.provider_name = provider_name

    @property
    def internal_agents(self) -> InternalAgentExecutionService | None:
        """Return the shared internal-agent boundary used by Runtime services."""

        return self._internal_agents

    @internal_agents.setter
    def internal_agents(
        self, value: InternalAgentExecutionService | None
    ) -> None:
        """Replace the shared boundary for tests and controlled hot swaps.

        Runtime services keep references to the same boundary for preparation,
        direct business execution, and child runs. Updating only an attribute
        on ``RuntimeTaskEngine`` would leave those references stale and cause
        the task to fall through to the mock/provider path.
        """

        self._internal_agents = value
        self.preparation.internal_agents = value
        for service in self.runtime_boundary.business_registry.services():
            if hasattr(service, "internal_agents"):
                service.internal_agents = value
            child_run = getattr(service, "child_run_service", None)
            if child_run is not None and hasattr(child_run, "internal_agents"):
                child_run.internal_agents = value

    def _business_service(self, agent_id: str) -> object | None:
        for service in self.runtime_boundary.business_registry.services():
            if getattr(service, "agent_id", None) == agent_id:
                return service
        return None

    @property
    def general_question_runtime(self) -> object | None:
        """Compatibility view of the registered general-question Runtime."""

        return self._business_service("GENERAL_QUESTION_V1")

    @property
    def knowledge_qa_runtime(self) -> object | None:
        """Compatibility view of the registered knowledge-QA Runtime."""

        return self._business_service("LEARN_01_LOCAL_RETRIEVAL_V1")

    @property
    def research_analysis_runtime(self) -> object | None:
        """Compatibility view of the registered data-analysis Runtime."""

        return self._business_service("RESEARCH_03_DATA_ANALYSIS_V1")

    @property
    def generic_goal_runtime(self) -> object | None:
        """Compatibility view of the wildcard Goal Runtime."""

        return self._business_service("*")

    @property
    def agent_registry(self) -> AgentRegistry:
        """Expose the registry retained by the request-preparation service."""

        return self._agent_registry

    def prepare_shutdown(self) -> None:
        self._shutting_down = True

    async def shutdown(self) -> None:
        await self.post_processing.shutdown()
        await self.external_retrieval_gateway.shutdown()
        if self.rag_retrieval is not None:
            await asyncio.to_thread(self.rag_retrieval.close)

    async def execute(self, task_id: str) -> None:
        runtime_run: AgentRun | None = None
        runner_started = perf_counter()
        started_at = utc_now()
        lease_task: asyncio.Task[None] | None = None
        try:
            prepared = await self.preparation.prepare(
                task_id,
                started_at=started_at,
                now=utc_now(),
            )
            if prepared is None:
                return
            runtime_run = prepared.runtime_run
            lease_task = asyncio.create_task(
                self.task_leases.heartbeat(task_id),
                name=f"xzd-lease-{task_id}",
            )

            outcome = await self.runtime_execution.execute(
                prepared,
                runner_started=runner_started,
            )
            await self.completion.commit(
                task_id,
                prepared,
                outcome,
                started_at=started_at,
                completed_at=utc_now(),
            )

        except RuntimeRunSuspended as exc:
            logger.info(
                "runtime_run_suspended task_id=%s run_id=%s status=%s",
                task_id,
                exc.run_id,
                exc.status.value,
            )
            return
        except ProviderCancelledError as exc:
            await self.task_failures.cancel(task_id, exc.message)
        except asyncio.CancelledError:
            if self._shutting_down:
                await self.task_failures.requeue_after_shutdown(task_id)
            else:
                logger.info("runtime_task_cancelled task_id=%s", task_id)
            raise
        except Exception as exc:
            logger.exception(
                "runtime_task_unhandled task_id=%s error_type=%s",
                task_id,
                type(exc).__name__,
            )
            if isinstance(exc, AppError):
                message = exc.message
                code = exc.code
            elif isinstance(exc, RuntimeNodeError):
                code = exc.error_code or "runtime_node_error"
                message = _runtime_failure_message(code)
            else:
                message = "任务执行失败，请稍后重试。"
                code = "background_task_error"
            await self.task_failures.fail(
                task_id,
                message,
                code,
            )
        finally:
            if lease_task is not None:
                lease_task.cancel()
                await asyncio.gather(lease_task, return_exceptions=True)
            if runtime_run is not None:
                self.runtime_hooks.discard(runtime_run.run_id)
