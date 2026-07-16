from abc import ABC, abstractmethod
from typing import Any

from app.contracts import AgentRequest, AgentResult


class AgentProvider(ABC):
    provider_name: str

    @abstractmethod
    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        stream: bool = True,
    ) -> AgentResult:
        ...

    @abstractmethod
    async def cancel(self, run_id: str) -> None:
        ...

    @abstractmethod
    async def get_status(self, run_id: str) -> dict[str, Any]:
        ...
