from __future__ import annotations

from typing import Any

from app.contracts import AgentRequest, GoalContract
from app.contracts.planner import PlannerBudget
from app.services.multimodal_policy import (
    enrich_multimodal_request,
    get_multimodal_capability_hint,
)


class UnifiedRequestPreparationService:
    """Build one goal envelope for both public task ingress adapters.

    Scenario and route metadata are accepted only as hints.  This service does
    not select an Agent, compile a Runtime plan, call a provider, or mutate a
    route.
    """

    def build_goal(self, request: AgentRequest) -> GoalContract:
        request = enrich_multimodal_request(request)
        options = request.options
        routing = options.get("_routing")
        routing_data = routing if isinstance(routing, dict) else {}
        recognition = routing_data.get("intent_recognition")
        recognition_data = recognition if isinstance(recognition, dict) else {}
        scenario_contract = options.get("scenario_contract")
        scenario_data = (
            scenario_contract if isinstance(scenario_contract, dict) else {}
        )
        modalities = self._modalities(request)
        desired_output = self._string_list(
            options.get("desired_output")
            or scenario_data.get("expected_output")
        )
        evidence = self._string_list(
            options.get("evidence_requirements")
            or scenario_data.get("evidence_requirements")
        )
        constraints: dict[str, Any] = {}
        for key in (
            "task_subtype",
            "secondary_intents",
            "requires_pipeline",
            "response_depth",
            "review_boundary",
            "course_confirmation_required",
            "evidence_state",
            "available_workers",
            "available_tools",
        ):
            value = options.get(key, scenario_data.get(key))
            if value not in (None, "", [], {}):
                constraints[key] = value
        has_images = any(
            attachment.content_type.startswith("image/")
            for attachment in request.attachments
        )
        capability_hint = get_multimodal_capability_hint(request)
        if has_images:
            constraints["multimodal_capability_hint"] = capability_hint.model_dump(
                mode="json"
            )
        budget = self._budget(options.get("budget"))
        task_family = str(
            options.get("task_family_hint")
            or recognition_data.get("task_family")
            or routing_data.get("task_subtype")
            or request.intent.value
        )
        return GoalContract(
            goal_id=request.task_id,
            normalized_goal=request.input_text(),
            user_role=request.user_role,
            course_context=request.course_id or "AUTO",
            task_family_hint=task_family,
            input_modalities=modalities,
            constraints=constraints,
            desired_output=desired_output,
            evidence_requirements=evidence,
            risk_level=str(options.get("risk_level", "low")),
            budget=budget,
            attachment_refs=list(request.attachments),
            multimodal_intent=capability_hint.intent if has_images else "UNKNOWN",
            multimodal_capability_hint=(
                capability_hint.model_dump(mode="json") if has_images else {}
            ),
            session_context_ref=str(
                options.get("session_context_ref") or request.session_id
            ),
            scenario_hint=str(request.scenario_id or ""),
        )

    def attach(self, request: AgentRequest) -> AgentRequest:
        request = enrich_multimodal_request(request)
        goal = self.build_goal(request)
        options = dict(request.options)
        options["_goal_contract"] = goal.model_dump(mode="json")
        options["goal_id"] = goal.goal_id
        return request.model_copy(update={"options": options})

    @staticmethod
    def _modalities(request: AgentRequest) -> list[str]:
        values: list[str] = []
        if request.input_text():
            values.append("text")
        for attachment in request.attachments:
            if attachment.content_type.startswith("image/"):
                values.append("image")
            elif attachment.content_type == "application/pdf":
                values.append("pdf")
            else:
                values.append("document")
        return list(dict.fromkeys(values or ["text"]))

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if not isinstance(value, list):
            return []
        return list(
            dict.fromkeys(
                str(item).strip() for item in value if str(item).strip()
            )
        )

    @staticmethod
    def _budget(value: Any) -> PlannerBudget:
        if not isinstance(value, dict):
            return PlannerBudget()
        allowed = {
            key: value[key]
            for key in (
                "max_model_calls",
                "max_tool_calls",
                "max_subagent_runs",
                "max_parallelism",
            )
            if key in value
        }
        return PlannerBudget.model_validate(allowed)
