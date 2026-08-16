from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any

from app.contracts import AgentRequest, AgentResult, Artifact, RunMetrics
from app.core.errors import ProviderCancelledError, ProviderError
from app.providers.base import AgentProvider


class MockAgentProvider(AgentProvider):
    """Deterministic provider used only for local development and tests."""

    provider_name = "mock"

    def __init__(self) -> None:
        self._cancelled_runs: set[str] = set()

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        stream: bool = True,
    ) -> AgentResult:
        started = perf_counter()
        delay = float(request.options.get("mock_delay_seconds", 0))
        if request.options.get("mock_force_failure"):
            raise ProviderError("Mock Provider 按请求触发失败")

        elapsed = 0.0
        while elapsed < delay:
            if request.task_id in self._cancelled_runs:
                raise ProviderCancelledError("Mock 任务已取消")
            step = min(0.05, delay - elapsed)
            await asyncio.sleep(step)
            elapsed += step

        if request.task_id in self._cancelled_runs:
            raise ProviderCancelledError("Mock 任务已取消")

        answer = (
            "这是本地 Mock Provider 的演示结果，不是远程模型真实输出。"
            "它仅用于验证任务、事件、文件和产物链路。"
        )
        artifact = Artifact(
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content={"answer": answer, "provider": "mock", "mock": True},
            confidence=None,
        )
        latency_ms = int((perf_counter() - started) * 1000)
        return AgentResult(
            agent_id=agent_id,
            provider=self.provider_name,
            answer=answer,
            structured_result={
                "provider": "mock",
                "mock": True,
                "echo": request.canonical_input,
                "stream_requested": stream,
            },
            artifacts=[artifact],
            warnings=[
                "mock_result",
            "当前为本地 Mock 演示结果，不是远程模型真实输出",
            ],
            confidence=None,
            metrics=RunMetrics(provider_latency_ms=latency_ms),
        )

    async def cancel(self, run_id: str) -> None:
        self._cancelled_runs.add(run_id)

    async def get_status(self, run_id: str) -> dict[str, Any]:
        status = "cancelled" if run_id in self._cancelled_runs else "local"
        return {"run_id": run_id, "status": status, "provider": self.provider_name}
