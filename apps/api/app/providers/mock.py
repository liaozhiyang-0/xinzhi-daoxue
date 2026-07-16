from __future__ import annotations

from typing import Any

from app.contracts import AgentRequest, AgentResult, Artifact
from app.providers.base import AgentProvider


class MockAgentProvider(AgentProvider):
    """Deterministic provider for local development and CI."""

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        stream: bool = True,
    ) -> AgentResult:
        answer = "这是 Mock Provider 返回的本地演示结果，不代表讯飞星辰真实解题输出。"
        artifact = Artifact(
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content={"answer": answer, "provider": "mock"},
            confidence=0.5,
        )
        return AgentResult(
            agent_id=agent_id,
            provider="mock",
            answer=answer,
            structured_result={
                "provider": "mock",
                "echo": request.canonical_input,
                "stream_requested": stream,
            },
            artifacts=[artifact],
            warnings=["mock_result"],
            confidence=0.5,
            metrics={
                "provider": "mock",
                "latency_ms": 0,
                "model_calls": 0,
                "tool_calls": 0,
                "retrieval_calls": 0,
            },
        )

    async def cancel(self, run_id: str) -> None:
        return None

    async def get_status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "completed", "provider": "mock"}
