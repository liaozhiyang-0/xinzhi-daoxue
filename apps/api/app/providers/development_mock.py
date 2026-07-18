from __future__ import annotations

import asyncio
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

from app.agents import AgentRegistry
from app.contracts import (
    AgentRequest,
    AgentResult,
    Artifact,
    RunMetrics,
    TaskRequestContext,
)
from app.core.config import Settings
from app.core.errors import ValidationAppError
from app.providers.base import AgentProvider
from app.services.agent_runtime import AgentExecutionPlanner, AgentInputMapper

MOCK_WARNING = "当前结果来自开发态Mock，不代表正式云端能力"


class DevelopmentMockProvider(AgentProvider):
    """Definition-driven Mock used only by explicit development actions."""

    provider_name = "mock"

    def __init__(self, settings: Settings, registry: AgentRegistry) -> None:
        self.settings = settings
        self.registry = registry
        self._profiles = self._load_profiles(settings.agent_mock_profiles_path)

    @staticmethod
    def _load_profiles(path: Path) -> dict[str, dict[str, Any]]:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ValueError("无法读取开发态Mock profiles") from exc
        profiles = payload.get("profiles") if isinstance(payload, dict) else None
        if not isinstance(profiles, dict):
            raise ValueError("Mock profiles必须包含profiles映射")
        return {
            str(name): dict(value)
            for name, value in profiles.items()
            if isinstance(value, dict)
        }

    def profile_exists(self, profile: str) -> bool:
        return profile in self._profiles

    def is_allowed(self, agent_id: str) -> bool:
        definition = self.registry.get(agent_id)
        return bool(
            self.settings.app_env in {"development", "test"}
            and self.settings.allow_agent_mocks
            and definition.development.mock_enabled
            and self.profile_exists(definition.development.mock_profile)
        )

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        stream: bool = False,
    ) -> AgentResult:
        del stream
        definition = self.registry.get(agent_id)
        if not self.is_allowed(agent_id) or not request.options.get(
            "allow_agent_mock", False
        ):
            return self._planned_result(definition.agent_id, request)

        input_mode = AgentExecutionPlanner._input_mode(request)
        context = TaskRequestContext.from_agent_request(request, input_mode=input_mode)
        mapped = AgentInputMapper().map(
            definition,
            context,
            retrieval_context=str(request.options.get("retrieved_context", "")),
        )
        profile_name = definition.development.mock_profile
        profile = self._profiles[profile_name]
        started = perf_counter()
        latency_ms = min(
            definition.development.mock_latency_ms,
            self.settings.agent_mock_max_latency_ms,
        )
        if latency_ms:
            await asyncio.sleep(latency_ms / 1000)

        business_data = profile.get("business_data", {})
        if not isinstance(business_data, dict):
            raise ValidationAppError("Mock profile business_data必须是映射")
        answer = str(profile.get("answer_text", "开发态Mock已完成协议响应。"))
        structured = {
            "status": str(profile.get("status", "success")),
            "answer_text": answer,
            "business_data": dict(business_data),
            "confidence": profile.get("confidence"),
            "warnings": [MOCK_WARNING],
            "mock_used": True,
            "mock_profile": profile_name,
            "cloud_status": "not_called",
            "mapped_field_lengths": mapped.field_lengths,
        }
        actual_latency_ms = int((perf_counter() - started) * 1000)
        artifact = Artifact(
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content={
                "answer": answer,
                "business_data": business_data,
                "provider": "mock",
                "mock": True,
                "mock_profile": profile_name,
            },
        )
        return AgentResult(
            agent_id=agent_id,
            agent_version=definition.version,
            provider="mock",
            course_id=request.course_id,
            intent=request.intent.value,
            answer=answer,
            structured_result=structured,
            artifacts=[artifact],
            warnings=[MOCK_WARNING, "mock_result"],
            confidence=(
                float(profile["confidence"])
                if isinstance(profile.get("confidence"), (int, float))
                else None
            ),
            metrics=RunMetrics(provider_latency_ms=actual_latency_ms),
            business_data=dict(business_data),
            request_id=str(request.options.get("request_id", request.task_id)),
            task_id=request.task_id,
            cloud_status="not_called",
            timings={"mock_ms": actual_latency_ms},
            mock_used=True,
            mock_profile=profile_name,
        )

    @staticmethod
    def _planned_result(agent_id: str, request: AgentRequest) -> AgentResult:
        answer = "该工作流仍处于计划或本地协议准备阶段，未调用云端或Mock。"
        return AgentResult(
            agent_id=agent_id,
            provider="none",
            course_id=request.course_id,
            intent=request.intent.value,
            answer=answer,
            structured_result={
                "status": "planned",
                "answer_text": answer,
                "business_data": {},
                "mock_used": False,
                "cloud_status": "not_called",
            },
            warnings=["planned_agent_not_executed"],
            cloud_status="not_called",
            request_id=str(request.options.get("request_id", request.task_id)),
            task_id=request.task_id,
        )

    async def cancel(self, run_id: str) -> None:
        del run_id

    async def get_status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "local", "provider": "mock"}
