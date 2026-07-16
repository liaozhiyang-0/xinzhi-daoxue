from __future__ import annotations

import logging
from typing import Any

import httpx

from app.contracts import AgentRequest, AgentResult
from app.core.config import Settings
from app.core.errors import (
    NotConfiguredError,
    ProviderError,
    ProviderTimeoutError,
)
from app.providers.base import AgentProvider

logger = logging.getLogger(__name__)


class XingchenCloudProvider(AgentProvider):
    """讯飞星辰适配器边界。

    正式 URL、鉴权和负载字段尚未提供，因此当前实现只完成配置校验、
    HTTP 客户端、转换入口和异常映射，不猜测云端协议。
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.timeout = httpx.Timeout(
            connect=10.0,
            read=settings.xingchen_timeout_seconds,
            write=30.0,
            pool=10.0,
        )

    @property
    def is_configured(self) -> bool:
        return bool(
            self.settings.xingchen_enabled
            and self.settings.xingchen_base_url
            and self.settings.xingchen_api_key
            and self.settings.xingchen_solver_ct_workflow_id
        )

    def _to_provider_request(
        self, agent_id: str, request: AgentRequest, stream: bool
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise NotConfiguredError("讯飞星辰 Provider 未配置完整")
        raise NotConfiguredError(
            "讯飞星辰正式请求字段尚未提供；请补充 API 文档后实现转换"
        )

    def _from_provider_response(
        self, agent_id: str, payload: dict[str, Any]
    ) -> AgentResult:
        raise NotConfiguredError(
            "讯飞星辰正式响应字段尚未提供；请补充 API 文档后实现转换"
        )

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        stream: bool = True,
    ) -> AgentResult:
        payload = self._to_provider_request(agent_id, request, stream)
        # TODO：待确认正式执行路径和鉴权方式后，在此使用 AsyncClient 发起请求。
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.xingchen_base_url,
                timeout=self.timeout,
            ) as client:
                _ = client
                _ = payload
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("讯飞星辰请求超时") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("讯飞星辰 HTTP 调用失败") from exc
        raise NotConfiguredError("讯飞星辰正式执行路径尚未配置")

    async def cancel(self, run_id: str) -> None:
        raise NotConfiguredError("讯飞星辰取消接口尚未提供")

    async def get_status(self, run_id: str) -> dict[str, Any]:
        raise NotConfiguredError("讯飞星辰状态查询接口尚未提供")
