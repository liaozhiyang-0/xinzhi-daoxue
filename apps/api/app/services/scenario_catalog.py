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
                "_scenario_catalog_bound": True,
            }
        )
        default_intent = OrchestrationIntent(scenario.intents[0])
        return payload.model_copy(
            update={
                "metadata": metadata,
                "intent_hint": payload.intent_hint or default_intent,
            }
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
                f"鍦烘櫙 {scenario.id} 涓嶆敮鎸佽绋?{course}"
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
                f"鍦烘櫙 {scenario.id} 涓嶆敮鎸佽緭鍏ョ被鍨?{input_type}"
            )
        if payload.user_role.value not in scenario.roles:
            raise ScenarioCatalogError(
                "scenario role is not authorized: "
                f"{payload.user_role.value} not in {', '.join(scenario.roles)}"
            )
        options = dict(payload.options)
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
                "_scenario_catalog_bound": True,
            }
        )
        return payload.model_copy(
            update={
                "options": options,
                "intent": Intent(scenario.intents[0]),
            }
        )
