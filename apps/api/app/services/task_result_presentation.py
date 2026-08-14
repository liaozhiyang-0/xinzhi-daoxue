from __future__ import annotations

from collections.abc import Sequence
from time import perf_counter
from typing import Literal

from app.agents import AgentDefinition
from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentValidationResult,
    EvidencePacketV1,
    EvidenceSourceV1,
    EvidenceViewItem,
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
        self._synchronize_evidence_projection(
            result=result,
            request=request,
            bundle=bundle,
            evidence_view=evidence_view,
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

    @staticmethod
    def _synchronize_evidence_projection(
        *,
        result: AgentResult,
        request: AgentRequest,
        bundle: WorkflowContextBundle | None,
        evidence_view: Sequence[EvidenceViewItem],
    ) -> None:
        """Keep persisted evidence metadata aligned with visible evidence cards."""

        if not evidence_view:
            return
        structured = result.structured_result
        structured["knowledge_hit_count"] = len(evidence_view)
        current_packet = structured.get("evidence_packet")
        if isinstance(current_packet, dict) and current_packet.get("sources"):
            return
        query = next(
            (
                str(request.canonical_input[key])
                for key in ("question", "text", "query")
                if request.canonical_input.get(key)
            ),
            "",
        )
        sources: list[EvidenceSourceV1] = []
        if bundle is not None and bundle.evidence_items:
            for hit in bundle.evidence_items:
                course_id = getattr(hit.course_id, "value", hit.course_id)
                source_id = hit.evidence_id
                support_level: Literal[
                    "potentially_relevant", "supports_claim"
                ] = (
                    "supports_claim"
                    if source_id in bundle.used_evidence_ids
                    else "potentially_relevant"
                )
                sources.append(
                    EvidenceSourceV1(
                        source_id=source_id,
                        document_id=hit.document_id,
                        chunk_id=hit.chunk_id,
                        course_id=str(course_id),
                        chapter=hit.chapter or None,
                        section=hit.section or None,
                        title=hit.title or None,
                        content_excerpt=hit.content[:1_200],
                        source_ref=hit.source_ref or None,
                        retrieval_score=hit.score,
                        rerank_score=hit.score_components.get("rerank_score"),
                        score_components=hit.score_components,
                        document_checksum=hit.document_checksum or None,
                        support_level=support_level,
                        image_refs=[
                            image.resource_uri for image in hit.related_images
                        ],
                    )
                )
        else:
            for item in evidence_view:
                sources.append(
                    EvidenceSourceV1(
                        source_id=item.evidence_id,
                        document_id="",
                        chunk_id="",
                        course_id=item.course_id or None,
                        chapter=item.chapter or None,
                        section=item.section or None,
                        title=item.title or None,
                        content_excerpt=item.summary,
                        source_ref=item.source_ref or None,
                        support_level=(
                            "supports_claim"
                            if item.used_by_answer
                            else "potentially_relevant"
                        ),
                        image_refs=[
                            image.resource_uri for image in item.related_images
                        ],
                    )
                )
        if not sources:
            return
        structured["evidence_packet"] = EvidencePacketV1(
            query=query,
            course_id=(bundle.course_id if bundle is not None else result.course_id),
            retrieval_status=(
                bundle.rag_status if bundle is not None else result.rag_status
            ),
            evidence_sufficiency=(
                bundle.evidence_status
                if bundle is not None
                else result.evidence_status
            ),
            sources=sources,
            warnings=list(bundle.warnings) if bundle is not None else [],
        ).model_dump(mode="json")
