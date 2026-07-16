from __future__ import annotations

from typing import Any

from app.contracts import AgentRequest, AgentResult
from app.core.config import Settings
from app.core.errors import NotPublishedError
from app.providers.base import AgentProvider

NOT_PUBLISHED_MESSAGE = (
    "SOLVER_CT 工作流尚未发布外部 API，真实调用暂不可用。"
    "本地阶段不发送任何讯飞星辰 HTTP 请求。"
)


class XingchenCloudProvider(AgentProvider):
    """Boundary for the future public API; network transport is deliberately absent."""

    provider_name = "xingchen"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def is_available(self) -> bool:
        return False

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        stream: bool = True,
    ) -> AgentResult:
        del agent_id, request, stream
        raise NotPublishedError(NOT_PUBLISHED_MESSAGE)

    async def cancel(self, run_id: str) -> None:
        del run_id
        raise NotPublishedError(
            "DEFERRED：工作流尚未发布 API，暂无云端取消能力"
        )

    async def get_status(self, run_id: str) -> dict[str, Any]:
        del run_id
        raise NotPublishedError(
            "DEFERRED：工作流尚未发布 API，暂无云端状态查询能力"
        )
