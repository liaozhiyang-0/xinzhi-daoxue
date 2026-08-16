"""Provider boundary for the local Runtime-only execution model."""

from __future__ import annotations

from typing import Any

from app.contracts import AgentRequest, AgentResult
from app.core.errors import ProviderError
from app.providers.base import AgentProvider


class LocalAgentProvider(AgentProvider):
    """Explicit local provider used when no Runtime handler is selected.

    Business agents execute through their registered Runtime service.  This
    boundary intentionally never performs a second model call; reaching it
    means the registry is missing a local execution contract.
    """

    provider_name = "local"

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        stream: bool = True,
    ) -> AgentResult:
        del request, stream
        raise ProviderError(
            f"local_runtime_handler_missing: no Runtime handler for {agent_id}"
        )

    async def cancel(self, run_id: str) -> None:
        del run_id

    async def get_status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "local", "provider": self.provider_name}
