from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.contracts.agent import AgentRequest, Intent
from app.contracts.orchestration import (
    AgentRequestV2,
    InputType,
    OrchestrationIntent,
)
from app.contracts.scenarios import ScenarioCatalogDocument, ScenarioDefinition


class ScenarioCatalogError(ValueError):
    """Raised when a scenario cannot be loaded or applied to a request."""


class ScenarioCatalog:
    """Validated, immutable-at-runtime catalog for product scenarios."""

    _RESERVED_METADATA_KEYS = frozenset(
        {
            "scenario_id",
            "scenario_version",
            "scenario_name",
            "scenario_agent_id",
            "scenario_retrieval_profile",
            "scenario_evidence_policy",
            "scenario_contract",
            "scenario_case_id",
            "_scenario_catalog_bound",
        }
    )

    def __init__(self, path: Path) -> None:
        self.path = path
        self.document = self._load(path)
        self._by_id = {item.id: item for item in self.document.scenarios}

    @staticmethod
    def _load(path: Path) -> ScenarioCatalogDocument:
        try:
            raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ScenarioCatalogError(f"无法加载场景目录: {path}") from exc
        try:
            document = ScenarioCatalogDocument.model_validate(raw)
        except ValueError as exc:
            raise ScenarioCatalogError(f"场景目录格式无效: {path}") from exc
        ids = [item.id for item in document.scenarios]
        if len(ids) != len(set(ids)):
            raise ScenarioCatalogError("场景目录存在重复 id")
        for item in document.scenarios:
            if item.enabled and not item.demo_cases:
                raise ScenarioCatalogError(
                    f"启用场景缺少结构化演示案例: {item.id}"
                )
            for demo_case in item.demo_cases:
                if demo_case.expected_agent != item.agent_id:
                    raise ScenarioCatalogError(
                        f"演示案例预期 Agent 与场景不一致: {item.id}/{demo_case.id}"
                    )
                if demo_case.role not in item.roles:
                    raise ScenarioCatalogError(
                        f"演示案例角色不在场景 roles 中: {item.id}/{demo_case.id}"
                    )
                if demo_case.course.upper() not in item.courses:
                    raise ScenarioCatalogError(
                        f"演示案例课程不在场景 courses 中: {item.id}/{demo_case.id}"
                    )
        try:
            for item in document.scenarios:
                for intent in item.intents:
                    OrchestrationIntent(intent)
                for input_mode in item.input_modes:
                    InputType(input_mode)
        except ValueError as exc:
            raise ScenarioCatalogError("场景目录包含未知意图或输入类型") from exc
        return document

    def list(
        self,
        *,
        course: str | None = None,
        role: str | None = None,
        enabled_only: bool = True,
    ) -> list[ScenarioDefinition]:
        normalized_course = course.upper() if course else None
        normalized_role = role.lower() if role else None
        values = []
        for item in self.document.scenarios:
            if enabled_only and not item.enabled:
                continue
            if normalized_course and normalized_course not in item.courses:
                continue
            if normalized_role and normalized_role not in item.roles:
                continue
            values.append(item)
        return values

    def get(self, scenario_id: str) -> ScenarioDefinition:
        item = self._by_id.get(scenario_id)
        if item is None or not item.enabled:
            raise ScenarioCatalogError(f"场景不存在或未启用: {scenario_id}")
        return item

    @staticmethod
    def _contract_course(course: str | None, demo_course: str) -> str:
        """Bind the contract to the active course, not the demo's course."""

        normalized = str(course or "").strip().upper()
        return (
            normalized
            if normalized not in {"", "AUTO", "UNKNOWN"}
            else demo_course.upper()
        )

    @staticmethod
    def _course_resolution(
        course: str | None, demo_course: str
    ) -> dict[str, Any]:
        requested = str(course or "").strip().upper()
        if requested not in {"", "AUTO", "UNKNOWN"}:
            return {
                "requested": requested,
                "resolved": requested,
                "source": "explicit_request",
                "confirmation_required": False,
            }
        return {
            "requested": requested or "UNKNOWN",
            "resolved": demo_course.upper(),
            "source": "demo_case_fallback",
            "confirmation_required": True,
        }

    def enrich_request(self, payload: AgentRequestV2) -> AgentRequestV2:
        if payload.scenario_id is None:
            metadata = {
                key: value
                for key, value in payload.metadata.items()
                if key not in self._RESERVED_METADATA_KEYS
            }
            return payload if metadata == payload.metadata else payload.model_copy(
                update={"metadata": metadata}
            )
        scenario = self.get(payload.scenario_id)
        course = payload.course_hint.value if payload.course_hint else None
        if course and course not in scenario.courses:
            raise ScenarioCatalogError(f"场景 {scenario.id} 不支持课程 {course}")
        if payload.input_type.value not in scenario.input_modes:
            raise ScenarioCatalogError(
                f"场景 {scenario.id} 不支持输入类型 {payload.input_type.value}"
            )
        metadata = dict(payload.metadata)
        demo_case = self._select_demo_case(
            scenario, payload.metadata.get("scenario_case_id")
        )
        contract_course = self._contract_course(course, demo_case.course)
        course_resolution = self._course_resolution(course, demo_case.course)
        metadata.update(
            {
                "scenario_id": scenario.id,
                "scenario_version": scenario.version,
                "scenario_name": scenario.name,
                "scenario_agent_id": scenario.agent_id,
                "scenario_retrieval_profile": scenario.retrieval_profile,
                "scenario_evidence_policy": scenario.evidence_policy.model_dump(
                    mode="json"
                ),
                "scenario_contract": {
                    "demo_case_id": demo_case.id,
                    "role": demo_case.role,
                    "course": contract_course,
                    "course_resolution": course_resolution,
                    "course_confirmation_required": course_resolution[
                        "confirmation_required"
                    ],
                    "expected_agent": demo_case.expected_agent,
                    "expected_output": list(demo_case.expected_output),
                    "business_context": demo_case.business_context,
                    "evidence_requirements": list(demo_case.evidence_requirements),
                    "review_boundary": demo_case.review_boundary,
                    "acceptance_conditions": list(demo_case.acceptance_conditions),
                    **(
                        {"formula_output_contract": demo_case.formula_output_contract}
                        if demo_case.formula_output_contract is not None
                        else {}
                    ),
                    **(
                        {"visual_acceptance": demo_case.visual_acceptance}
                        if demo_case.visual_acceptance is not None
                        else {}
                    ),
                },
                "_scenario_catalog_bound": True,
            }
        )
        if demo_case.visual_acceptance is not None:
            metadata["visual_acceptance"] = demo_case.visual_acceptance
        default_intent = OrchestrationIntent(scenario.intents[0])
        return payload.model_copy(
            update={
                "metadata": metadata,
                "intent_hint": payload.intent_hint or default_intent,
            }
        )

    @staticmethod
    def _select_demo_case(
        scenario: ScenarioDefinition, requested_case_id: Any
    ) -> Any:
        """Select an explicit case while preserving the first-case default."""

        normalized = str(requested_case_id or "").strip()
        if not normalized:
            return scenario.demo_cases[0]
        for demo_case in scenario.demo_cases:
            if demo_case.id == normalized:
                return demo_case
        raise ScenarioCatalogError(
            f"场景 {scenario.id} 不支持演示案例 {normalized}"
        )

    def enrich_legacy_request(self, payload: AgentRequest) -> AgentRequest:
        """Bind the same scenario contract for the legacy task API."""

        if payload.scenario_id is None:
            options = {
                key: value
                for key, value in payload.options.items()
                if key not in self._RESERVED_METADATA_KEYS
            }
            return payload if options == payload.options else payload.model_copy(
                update={"options": options}
            )

        scenario = self.get(payload.scenario_id)
        course = payload.course_id.upper()
        if course not in {"", "AUTO", "UNKNOWN"} and course not in scenario.courses:
            raise ScenarioCatalogError(
                f"场景 {scenario.id} 不支持课程 {course}"
            )
        input_type = str(payload.options.get("input_type", ""))
        if not input_type:
            has_text = bool(
                payload.canonical_input.get("text")
                or payload.canonical_input.get("question")
            )
            content_types = [item.content_type for item in payload.attachments]
            has_pdf = "application/pdf" in content_types
            has_images = any(item.startswith("image/") for item in content_types)
            if not content_types:
                input_type = "text"
            elif has_pdf and not has_images and not has_text:
                input_type = "pdf"
            elif has_images and not has_pdf and not has_text:
                input_type = "image"
            else:
                input_type = "mixed"
        if input_type not in scenario.input_modes:
            raise ScenarioCatalogError(
                f"场景 {scenario.id} 不支持输入类型 {input_type}"
            )
        # Scenario roles describe the intended example audience only.  They do
        # not restrict authenticated users: the product now exposes one
        # unified question workspace for teaching, learning, and research.
        options = dict(payload.options)
        demo_case = self._select_demo_case(
            scenario, payload.options.get("scenario_case_id")
        )
        contract_course = self._contract_course(payload.course_id, demo_case.course)
        course_resolution = self._course_resolution(
            payload.course_id, demo_case.course
        )
        options.update(
            {
                "scenario_id": scenario.id,
                "scenario_version": scenario.version,
                "scenario_name": scenario.name,
                "scenario_agent_id": scenario.agent_id,
                "scenario_retrieval_profile": scenario.retrieval_profile,
                "scenario_evidence_policy": scenario.evidence_policy.model_dump(
                    mode="json"
                ),
                "scenario_contract": {
                    "demo_case_id": demo_case.id,
                    "role": demo_case.role,
                    "course": contract_course,
                    "course_resolution": course_resolution,
                    "course_confirmation_required": course_resolution[
                        "confirmation_required"
                    ],
                    "expected_agent": demo_case.expected_agent,
                    "expected_output": list(demo_case.expected_output),
                    "business_context": demo_case.business_context,
                    "evidence_requirements": list(demo_case.evidence_requirements),
                    "review_boundary": demo_case.review_boundary,
                    "acceptance_conditions": list(demo_case.acceptance_conditions),
                    **(
                        {"formula_output_contract": demo_case.formula_output_contract}
                        if demo_case.formula_output_contract is not None
                        else {}
                    ),
                    **(
                        {"visual_acceptance": demo_case.visual_acceptance}
                        if demo_case.visual_acceptance is not None
                        else {}
                    ),
                },
                "_scenario_catalog_bound": True,
            }
        )
        if demo_case.visual_acceptance is not None:
            options["visual_acceptance"] = demo_case.visual_acceptance
        return payload.model_copy(
            update={
                "options": options,
                "intent": Intent(scenario.intents[0]),
            }
        )
