from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any

import httpx

from app.contracts import (
    AgentRequest,
    AgentResult,
    Artifact,
    AttachmentRef,
    RunMetrics,
)
from app.core.config import Settings
from app.core.errors import (
    ValidationAppError,
    XingchenConfigurationError,
    XingchenConnectionError,
    XingchenHttpError,
    XingchenResponseParseError,
    XingchenTimeoutError,
)
from app.core.logging import mask_sensitive_text
from app.providers.base import AgentProvider
from app.services.storage import StorageService

logger = logging.getLogger(__name__)
TEXT_FIELDS = ("text", "question", "problem", "query", "prompt")
IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg"}
DEFAULT_IMAGE_PROMPT = "请识别并解答图片中的电路题，说明关键步骤和最终答案。"


def extract_input_text(request: AgentRequest) -> str:
    for field in TEXT_FIELDS:
        value = request.canonical_input.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    if request.attachments:
        return DEFAULT_IMAGE_PROMPT
    raise ValidationAppError("星辰工作流需要非空文本题目")


def build_workflow_payload(
    settings: Settings,
    request: AgentRequest,
    *,
    image_url: str | None = None,
) -> dict[str, Any]:
    ext = {"caller": "workflow"}
    if settings.xingchen_bot_id.strip():
        ext["bot_id"] = settings.xingchen_bot_id.strip()
    parameters = {"AGENT_USER_INPUT": extract_input_text(request)}
    if image_url:
        parameters["USER_INPUT_image"] = image_url
    return {
        "flow_id": settings.xingchen_solver_ct_flow_id,
        "uid": settings.xingchen_uid,
        "parameters": parameters,
        "ext": ext,
        "stream": False,
    }


def get_single_image(request: AgentRequest) -> AttachmentRef | None:
    if not request.attachments:
        return None
    if len(request.attachments) != 1:
        raise ValidationAppError("星辰图片解题当前只支持单张图片")
    attachment = request.attachments[0]
    if attachment.content_type not in IMAGE_CONTENT_TYPES:
        raise ValidationAppError("星辰图片解题仅支持 PNG、JPG 或 JPEG")
    return attachment


def parse_upload_url(payload: dict[str, Any]) -> str:
    if payload.get("code") != 0:
        raise XingchenHttpError(
            "星辰文件上传返回业务错误",
            details={"upstream_code": payload.get("code")},
        )
    data = payload.get("data")
    url = data.get("url") if isinstance(data, dict) else None
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        raise XingchenResponseParseError("星辰文件上传响应缺少有效 data.url")
    return url


def _choice_content(payload: dict[str, Any]) -> str:
    if payload.get("code") not in (None, 0):
        raise XingchenHttpError(
            "星辰工作流返回业务错误",
            details={"upstream_code": payload.get("code")},
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise XingchenResponseParseError("星辰响应缺少 choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise XingchenResponseParseError("星辰 choices 格式无效")
    delta = first.get("delta")
    if not isinstance(delta, dict):
        raise XingchenResponseParseError("星辰响应缺少 choices[0].delta")
    content = delta.get("content")
    if not isinstance(content, str):
        raise XingchenResponseParseError("星辰响应缺少最终文本")
    return content


def parse_json_answer(payload: dict[str, Any]) -> str:
    answer = _choice_content(payload).strip()
    if not answer:
        raise XingchenResponseParseError("星辰最终回答为空")
    return answer


def parse_sse_answer(body: str) -> str:
    chunks: list[str] = []
    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise XingchenResponseParseError("星辰 SSE data 不是 JSON") from exc
        if not isinstance(payload, dict):
            raise XingchenResponseParseError("星辰 SSE data 顶层格式无效")
        content = _choice_content(payload)
        if content:
            chunks.append(content)
    answer = "".join(chunks).strip()
    if not answer:
        raise XingchenResponseParseError("星辰 SSE 未包含最终回答")
    return answer


class XingchenCloudProvider(AgentProvider):
    provider_name = "xingchen"

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.client = client

    @property
    def is_available(self) -> bool:
        return self.settings.xingchen_runtime_available

    @property
    def authorization(self) -> str:
        return (
            "Bearer "
            f"{self.settings.xingchen_api_key.get_secret_value()}:"
            f"{self.settings.xingchen_api_secret.get_secret_value()}"
        )

    async def _upload_image(
        self,
        client: httpx.AsyncClient,
        attachment: AttachmentRef,
    ) -> str:
        image = await StorageService(self.settings).read(attachment.storage_key)
        url = (
            self.settings.xingchen_base_url.rstrip("/")
            + self.settings.xingchen_upload_path
        )
        response = await client.post(
            url,
            headers={"Accept": "application/json", "Authorization": self.authorization},
            files={
                "file": (
                    attachment.filename,
                    image,
                    attachment.content_type,
                )
            },
        )
        if not response.is_success:
            raise XingchenHttpError(
                "星辰文件上传 HTTP 请求失败",
                details={"http_status": response.status_code},
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise XingchenResponseParseError("星辰文件上传响应不是 JSON") from exc
        if not isinstance(payload, dict):
            raise XingchenResponseParseError("星辰文件上传 JSON 顶层格式无效")
        return parse_upload_url(payload)

    async def _request_workflow(
        self,
        client: httpx.AsyncClient,
        request: AgentRequest,
    ) -> tuple[httpx.Response, bool]:
        attachment = get_single_image(request)
        image_url = (
            await self._upload_image(client, attachment) if attachment else None
        )
        payload = build_workflow_payload(
            self.settings,
            request,
            image_url=image_url,
        )
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": self.authorization,
        }
        url = (
            self.settings.xingchen_base_url.rstrip("/")
            + self.settings.xingchen_workflow_path
        )
        response = await client.post(url, headers=headers, json=payload)
        return response, attachment is not None

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        stream: bool = False,
    ) -> AgentResult:
        if agent_id != "SOLVER_CT_V1":
            raise ValidationAppError("Xingchen Provider 仅支持 SOLVER_CT_V1")
        if stream:
            raise ValidationAppError("本阶段仅支持星辰 stream=false")
        if not self.settings.xingchen_runtime_available:
            raise XingchenConfigurationError("星辰 Key、Secret 或 Flow ID 配置不完整")

        started = perf_counter()
        try:
            if self.client is None:
                async with httpx.AsyncClient(
                    timeout=self.settings.xingchen_timeout_seconds
                ) as client:
                    response, image_used = await self._request_workflow(
                        client, request
                    )
            else:
                response, image_used = await self._request_workflow(
                    self.client, request
                )
        except httpx.TimeoutException as exc:
            raise XingchenTimeoutError("星辰工作流请求超时") from exc
        except httpx.RequestError as exc:
            raise XingchenConnectionError("无法连接星辰工作流 API") from exc

        if not response.is_success:
            raise XingchenHttpError(
                "星辰工作流 HTTP 请求失败",
                details={"http_status": response.status_code},
            )
        content_type = response.headers.get("content-type", "").lower()
        try:
            if "text/event-stream" in content_type:
                answer = parse_sse_answer(response.text)
            else:
                parsed = response.json()
                if not isinstance(parsed, dict):
                    raise XingchenResponseParseError("星辰 JSON 顶层格式无效")
                answer = parse_json_answer(parsed)
        except (ValueError, XingchenResponseParseError, XingchenHttpError):
            preview = mask_sensitive_text(response.text[:500])
            logger.warning(
                "xingchen_response_parse_failed status=%s content_type=%s preview=%s",
                response.status_code,
                content_type or "unknown",
                preview,
            )
            raise

        source_refs = [
            str(item)
            for item in request.options.get("xingchen_knowledge_sources", [])
        ]
        artifact = Artifact(
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content={
                "mode": "xingchen_workflow",
                "input_type": "image" if image_used else "text",
                "answer": answer,
                "knowledge_sources": source_refs,
            },
            source_refs=source_refs,
            confidence=None,
        )
        latency_ms = int((perf_counter() - started) * 1000)
        return AgentResult(
            agent_id=agent_id,
            provider=self.provider_name,
            answer=answer,
            structured_result={
                "mode": "xingchen_workflow",
                "input_type": "image" if image_used else "text",
                "knowledge_sources": source_refs,
            },
            artifacts=[artifact],
            citations=source_refs,
            confidence=None,
            metrics=RunMetrics(provider_latency_ms=latency_ms),
        )

    async def cancel(self, run_id: str) -> None:
        del run_id

    async def get_status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "unsupported", "provider": "xingchen"}
