from __future__ import annotations

from collections.abc import Sequence
from time import perf_counter
from typing import Any, Literal

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
from app.services.formula_output_contract import evaluate_formula_output_contract
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
        self._synchronize_generation_provenance(result)
        result.structured_result["business_view"] = self.business_renderers.render(
            definition, result, validation
        )
        self._attach_presentation_profile(result, request)
        math_source = dict(result.structured_result)
        math_source["answer_text"] = result.answer
        math_content = self.math_formatting.build_from_structured_result(math_source)
        result.answer = math_content.markdown
        result.math_content = math_content
        result.warnings = list(
            dict.fromkeys(
                [
                    *result.warnings,
                    *(f"math_formatting:{item}" for item in math_content.warnings),
                ]
            )
        )
        math_quality = self.math_formatting.quality_summary(math_content)
        result.structured_result["math_quality"] = math_quality
        formula_contract_config = request.options.get("formula_output_contract")
        if not isinstance(formula_contract_config, dict):
            scenario_contract = result.structured_result.get("scenario_contract")
            formula_contract_config = (
                scenario_contract.get("formula_output_contract")
                if isinstance(scenario_contract, dict)
                else None
            )
        formula_contract = evaluate_formula_output_contract(
            structured_result=result.structured_result,
            answer_text=result.answer,
            contract=formula_contract_config,
            math_quality=math_quality,
        )
        result.structured_result["formula_output_contract"] = formula_contract
        result.structured_result["answer_text"] = math_content.markdown
        result.structured_result["math_content"] = math_content.model_dump(
            mode="json"
        )
        self._apply_math_quality_to_contract(result, math_quality)
        self._apply_formula_contract_to_contract(result, formula_contract)
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
        if "knowledge" not in result.structured_result:
            hits = [
                {
                    **item.model_dump(mode="json"),
                    "excerpt": item.summary,
                }
                for item in evidence_view
            ]
            if not hits:
                raw_citations = result.structured_result.get("citations", [])
                if isinstance(raw_citations, list):
                    hits = [
                        item
                        for item in raw_citations
                        if isinstance(item, dict)
                        and str(item.get("source_ref", "")).startswith("kb://")
                    ]
            if hits:
                result.structured_result["knowledge"] = {"hits": hits}
        return result

    @staticmethod
    def _attach_presentation_profile(
        result: AgentResult, request: AgentRequest
    ) -> None:
        """Project Planner capability metadata without exposing Agent routing."""

        if isinstance(result.structured_result.get("presentation_profile"), dict):
            return
        snapshot = request.options.get("_planner_snapshot")
        if not isinstance(snapshot, dict):
            return
        capability_id = str(
            snapshot.get("planner_capability")
            or snapshot.get("selected_capability")
            or ""
        ).strip()
        if not capability_id:
            return
        result.structured_result["presentation_profile"] = {
            "capability_id": capability_id,
            "source": "planner_snapshot",
            "version": str(snapshot.get("planner_version") or ""),
        }

    @staticmethod
    def _synchronize_generation_provenance(result: AgentResult) -> None:
        """Expose the real model/provider behind a local Runtime adapter.

        ``AgentResult.provider`` describes the route adapter (for example
        ``local_graph``), while model-backed agents record the actual provider
        and model inside their execution record.  The workspace consumes the
        latter for the user-facing provenance panel; keeping this projection
        in the persisted result prevents a successful real call from being
        shown as an untracked or fallback execution.
        """

        structured = result.structured_result
        executions: list[dict[str, str]] = []
        for stage in (
            "vision_execution",
            "model_execution",
            "verification_model_execution",
            "internal_execution",
        ):
            payload = structured.get(stage)
            if not isinstance(payload, dict):
                continue
            provider = str(payload.get("provider") or "").strip()
            model = str(
                payload.get("model") or payload.get("model_route") or ""
            ).strip()
            payload_providers = [
                str(item).strip()
                for item in payload.get("providers", [])
                if str(item).strip()
            ]
            payload_models = [
                str(item).strip()
                for item in payload.get("models", [])
                if str(item).strip()
            ]
            if provider:
                payload_providers = [provider]
            if model:
                payload_models = [model]
            if payload_providers or payload_models:
                execution_count = max(len(payload_providers), len(payload_models), 1)
                for index in range(execution_count):
                    executions.append(
                        {
                            "stage": stage,
                            "provider": (
                                payload_providers[index]
                                if index < len(payload_providers)
                                else ""
                            ),
                            "model": (
                                payload_models[index]
                                if index < len(payload_models)
                                else ""
                            ),
                        }
                    )

        generated_model = str(
            structured.get("generation_model") or ""
        ).strip()
        if generated_model:
            generated_provider = str(result.provider or "").strip()
            executions.append(
                {
                    "stage": "generation",
                    "provider": generated_provider,
                    "model": generated_model,
                }
            )

        providers = list(
            dict.fromkeys(
                item["provider"] for item in executions if item["provider"]
            )
        )
        models = list(
            dict.fromkeys(item["model"] for item in executions if item["model"])
        )
        if providers:
            structured["generation_provider"] = (
                providers[0] if len(providers) == 1 else "multiple"
            )
        elif not str(structured.get("generation_provider") or "").strip():
            fallback_provider = str(result.provider or result.metrics.provider_used)
            if fallback_provider:
                structured["generation_provider"] = fallback_provider
        if models:
            structured["generation_model"] = (
                models[0] if len(models) == 1 else "multiple"
            )
        structured["generation_provenance"] = {
            "providers": providers,
            "models": models,
            "executions": executions,
        }

    @staticmethod
    def _apply_math_quality_to_contract(
        result: AgentResult, math_quality: dict[str, object]
    ) -> None:
        """Propagate rendering uncertainty to publishability and risk views."""

        status = str(math_quality.get("status", "passed"))
        if status == "passed":
            return
        warnings = math_quality.get("warnings", [])
        warning_items = warnings if isinstance(warnings, list) else []
        warning_text = ", ".join(str(item) for item in warning_items if str(item))
        TaskResultPresentationService._apply_quality_gap_to_contract(
            result=result,
            gap="math_rendering",
            risk="数学输出需要复核"
            + (f"（{warning_text}）" if warning_text else ""),
        )

    @staticmethod
    def _apply_formula_contract_to_contract(
        result: AgentResult, formula_contract: dict[str, Any]
    ) -> None:
        status = str(formula_contract.get("status", "not_configured"))
        if status == "passed" or status == "not_configured":
            return
        missing = formula_contract.get("missing", [])
        missing_items = missing if isinstance(missing, list) else []
        risk = "公式输出契约需要复核"
        if missing_items:
            risk += f"（缺少：{', '.join(str(item) for item in missing_items)}）"
        TaskResultPresentationService._apply_quality_gap_to_contract(
            result=result,
            gap="formula_output",
            risk=risk,
        )

    @staticmethod
    def _apply_quality_gap_to_contract(
        *,
        result: AgentResult,
        gap: str,
        risk: str,
    ) -> None:
        result.remaining_risks = list(
            dict.fromkeys(
                [
                    *result.remaining_risks,
                    risk,
                ]
            )
        )
        contract = result.structured_result.get("scenario_contract")
        if not isinstance(contract, dict):
            return
        quality_gaps = [
            str(item) for item in contract.get("quality_gaps", []) if str(item)
        ]
        if gap not in quality_gaps:
            quality_gaps.append(gap)
        updated = {**contract, "quality_gaps": quality_gaps}
        if updated.get("status") == "completed":
            updated["status"] = "completed_with_gaps"
        model_synthesis = updated.get("model_synthesis")
        if isinstance(model_synthesis, dict):
            updated["model_synthesis"] = {
                **model_synthesis,
                "publishable": False,
                "review_reason": gap,
            }
        result.structured_result["scenario_contract"] = updated

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
