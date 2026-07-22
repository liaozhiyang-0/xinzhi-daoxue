from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx

from app.agents import AgentRegistry
from app.contracts import ExecutionStatus
from app.core.config import Settings
from app.core.errors import NotConfiguredError, ProviderError, ProviderTimeoutError
from app.providers.workflow.base import WorkflowProvider, WorkflowResult
from app.providers.xingchen import (
    parse_json_answer,
    parse_sse_answer,
    standardize_answer,
)


class XingchenWorkflowProvider(WorkflowProvider):
    """Generic workflow boundary using the repository's verified Xingchen contract."""

    provider_name = "xingchen"

    def __init__(
        self,
        settings: Settings,
        registry: AgentRegistry,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.client = client
        self._owns_client = client is None

    def _client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=self.settings.xingchen_timeout_seconds
            )
        return self.client

    def _allowed_flow_ids(self) -> set[str]:
        return {
            flow_id
            for item in self.registry.list_agents()
            if (flow_id := self.registry.resolve_flow_id(item.agent_id, self.settings))
        }

    async def invoke_workflow(
        self,
        workflow_id: str,
        payload: dict[str, Any],
        timeout_seconds: int | None = None,
    ) -> WorkflowResult:
        if workflow_id not in self._allowed_flow_ids():
            raise NotConfiguredError("星辰 workflow_id 未在 Agent Registry 中配置")
        if not (
            self.settings.xingchen_enabled
            and self.settings.xingchen_api_key.get_secret_value()
            and self.settings.xingchen_api_secret.get_secret_value()
        ):
            raise NotConfiguredError("星辰 Provider 凭据未配置")
        started = perf_counter()
        body = {
            "flow_id": workflow_id,
            "uid": self.settings.xingchen_uid,
            "parameters": payload,
            "ext": {"caller": "workflow"},
            "stream": False,
        }
        try:
            response = await self._client().post(
                self.settings.xingchen_base_url.rstrip("/")
                + self.settings.xingchen_workflow_path,
                headers={
                    "Authorization": "Bearer "
                    + self.settings.xingchen_api_key.get_secret_value()
                    + ":"
                    + self.settings.xingchen_api_secret.get_secret_value(),
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=(
                    timeout_seconds or self.settings.workflow_default_timeout_seconds
                ),
            )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError("星辰工作流请求超时") from exc
        except httpx.RequestError as exc:
            raise ProviderError("无法连接星辰工作流 API") from exc
        if not response.is_success:
            raise ProviderError(
                "星辰工作流 HTTP 请求失败",
                details={"http_status": response.status_code},
            )
        content_type = response.headers.get("content-type", "").lower()
        answer = (
            parse_sse_answer(response.text)
            if "text/event-stream" in content_type
            else parse_json_answer(response.json())
        )
        normalized = standardize_answer(answer, input_type="text")
        return WorkflowResult(
            status=ExecutionStatus.SUCCESS,
            workflow_id=workflow_id,
            answer_text=str(normalized.get("answer_text", answer)),
            structured_result=normalized,
            elapsed_ms=int((perf_counter() - started) * 1000),
        )

    async def aclose(self) -> None:
        if self._owns_client and self.client is not None:
            await self.client.aclose()
            self.client = None
