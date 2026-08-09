from __future__ import annotations

from time import perf_counter

from app.agents import AgentDefinition
from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentValidationResult,
    WorkflowContextBundle,
)
from app.services.agent_result_governance import BusinessResultRendererRegistry
from app.services.math_formatting_service import MathFormattingService
from app.services.task_presentation import build_task_views


class TaskResultPresentationService:
    """Build the stable user-facing result view after deterministic validation."""

    def __init__(
        self,
        business_renderers: BusinessResultRendererRegistry,
        math_formatting: MathFormattingService,
    ) -> None:
        self.business_renderers = business_renderers
        self.math_formatting = math_formatting

    def apply(
        self,
        *,
        definition: AgentDefinition,
        result: AgentResult,
        request: AgentRequest,
        bundle: WorkflowContextBundle | None,
        routing: dict[str, object],
        timings: dict[str, int],
        validation: AgentValidationResult,
    ) -> AgentResult:
        """Apply business, evidence, execution, and math presentation to a result."""
        result.structured_result["business_view"] = self.business_renderers.render(
            definition, result, validation
        )
        presentation_started = perf_counter()
        presentation, execution_summary, evidence_view = build_task_views(
            definition=definition,
            result=result,
            bundle=bundle,
            routing=dict(routing),
            timings=dict(timings),
        )
        result.metrics.presentation_latency_ms = int(
            (perf_counter() - presentation_started) * 1000
        )
        result.structured_result.update(
            {
                "presentation": presentation.model_dump(mode="json"),
                "execution_summary": execution_summary.model_dump(mode="json"),
                "evidence_view": [
                    item.model_dump(mode="json") for item in evidence_view
                ],
                "workflow_context": (
                    bundle.model_dump(mode="json") if bundle is not None else None
                ),
            }
        )
        math_source = dict(result.structured_result)
        math_source["answer_text"] = result.answer
        math_content = self.math_formatting.build_from_structured_result(math_source)
        result.answer = math_content.markdown
        result.math_content = math_content
        result.structured_result["answer_text"] = math_content.markdown
        result.structured_result["math_content"] = math_content.model_dump(mode="json")
        if request.options.get("debug") is True:
            result.structured_result["math_debug"] = (
                self.math_formatting.debug_summary(math_content)
            )
        for artifact in result.artifacts:
            if "answer" in artifact.content:
                artifact.content["answer"] = math_content.markdown
            if "answer_text" in artifact.content:
                artifact.content["answer_text"] = math_content.markdown
            artifact.content["math_content"] = math_content.model_dump(mode="json")
        return result
