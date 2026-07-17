from __future__ import annotations

import json
import logging
from time import perf_counter
from typing import Any

import httpx

from app.agents.registry import AgentRegistry
from app.contracts import AgentRequest, AgentResult, Artifact, AttachmentRef
from app.core.config import Settings
from app.core.errors import (
    NotConfiguredError,
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
STRUCTURED_LIST_FIELDS = (
    "key_equations",
    "assumptions",
    "remaining_risks",
    "key_points",
    "examples",
    "common_mistakes",
    "recommended_reading",
)
STRUCTURED_TEXT_FIELDS = (
    "answer_text",
    "problem_summary",
    "final_answer",
    "knowledge_summary",
)


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
    agent_id: str = "SOLVER_CT_V1",
    image_url: str | None = None,
    registry: AgentRegistry | None = None,
) -> dict[str, Any]:
    active_registry = registry or AgentRegistry()
    flow_id = active_registry.resolve_flow_id(agent_id, settings)
    if not flow_id:
        raise XingchenConfigurationError(f"{agent_id} 对应云端工作流尚未启用")
    ext = {"caller": "workflow"}
    if settings.xingchen_bot_id.strip():
        ext["bot_id"] = settings.xingchen_bot_id.strip()
    parameters = {"AGENT_USER_INPUT": extract_input_text(request)}
    if image_url:
        parameters["USER_INPUT_image"] = image_url
    return {
        "flow_id": flow_id,
        "uid": settings.xingchen_uid,
        "parameters": parameters,
        "ext": ext,
        "stream": False,
    }


def get_single_image(request: AgentRequest) -> AttachmentRef | None:
    if not request.attachments:
        return None
    if len(request.attachments) != 1:
        raise ValidationAppError(
            "当前版本暂只支持单张图片，请将完整题目整理为一张截图。"
        )
    attachment = request.attachments[0]
    if attachment.content_type == "application/pdf":
        raise ValidationAppError("当前版本暂不直接解析 PDF，请先转换为单张清晰图片。")
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
    content = delta.get("content") if isinstance(delta, dict) else None
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
        chunks.append(_choice_content(payload))
    answer = "".join(chunks).strip()
    if not answer:
        raise XingchenResponseParseError("星辰 SSE 未包含最终回答")
    return answer


def json_object_from_answer(answer: str) -> dict[str, Any] | None:
    candidate = answer.strip()
    if candidate.startswith("```") and candidate.endswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3:
            candidate = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def standardize_answer(answer: str, *, input_type: str) -> dict[str, Any]:
    structured: dict[str, Any] = {
        "answer_text": answer,
        "problem_summary": "",
        "key_equations": [],
        "final_answer": "",
        "assumptions": [],
        "remaining_risks": [],
        "confidence": None,
    }
    payload = json_object_from_answer(answer)
    if payload is not None:
        for field in STRUCTURED_TEXT_FIELDS:
            value = payload.get(field)
            if isinstance(value, str):
                structured[field] = value.strip()
        for field in STRUCTURED_LIST_FIELDS:
            value = payload.get(field)
            if isinstance(value, list):
                structured[field] = [str(item) for item in value if str(item).strip()]
        confidence = payload.get("confidence")
        if (
            isinstance(confidence, (int, float))
            and not isinstance(confidence, bool)
            and 0 <= confidence <= 1
        ):
            structured["confidence"] = float(confidence)
    structured["input_type"] = input_type
    return structured


class XingchenCloudProvider(AgentProvider):
    provider_name = "xingchen"

    def __init__(
        self,
        settings: Settings,
        *,
        registry: AgentRegistry | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry or AgentRegistry()
        self.client = client

    @property
    def is_configured(self) -> bool:
        return self.settings.xingchen_credentials_available

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
        timeout_seconds: float,
    ) -> str:
        image = await StorageService(self.settings).read(attachment.storage_key)
        url = (
            self.settings.xingchen_base_url.rstrip("/")
            + self.settings.xingchen_upload_path
        )
        response = await client.post(
            url,
            headers={"Accept": "application/json", "Authorization": self.authorization},
            files={"file": (attachment.filename, image, attachment.content_type)},
            timeout=timeout_seconds,
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
        agent_id: str,
        request: AgentRequest,
        timeout_seconds: float,
    ) -> tuple[httpx.Response, bool]:
        attachment = get_single_image(request)
        image_url = (
            await self._upload_image(client, attachment, timeout_seconds)
            if attachment
            else None
        )
        payload = build_workflow_payload(
            self.settings,
            request,
            agent_id=agent_id,
            image_url=image_url,
            registry=self.registry,
        )
        url = (
            self.settings.xingchen_base_url.rstrip("/")
            + self.settings.xingchen_workflow_path
        )
        response = await client.post(
            url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": self.authorization,
            },
            json=payload,
            timeout=timeout_seconds,
        )
        return response, attachment is not None

    async def run(
        self,
        agent_id: str,
        request: AgentRequest,
        stream: bool = False,
    ) -> AgentResult:
        if stream:
            raise ValidationAppError("本阶段仅支持星辰 stream=false")
        if not self.settings.xingchen_credentials_available:
            raise NotConfiguredError("星辰 Key 或 Secret 配置不完整")
        if not self.registry.is_callable(agent_id, self.settings):
            raise XingchenConfigurationError(f"{agent_id} 对应云端工作流尚未启用")

        started = perf_counter()
        timeout = self.registry.timeout_seconds(agent_id, self.settings)
        try:
            if self.client is None:
                async with httpx.AsyncClient() as client:
                    response, image_used = await self._request_workflow(
                        client, agent_id, request, timeout
                    )
            else:
                response, image_used = await self._request_workflow(
                    self.client, agent_id, request, timeout
                )
        except httpx.TimeoutException as exc:
            message = (
                "专业工作流响应超时，请稍后重新提交。"
                if agent_id == "SOLVER_CT_V1"
                else "星辰工作流响应超时，请稍后重新提交。"
            )
            raise XingchenTimeoutError(message) from exc
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
            logger.warning(
                "xingchen_response_parse_failed status=%s content_type=%s preview=%s",
                response.status_code,
                content_type or "unknown",
                mask_sensitive_text(response.text[:500]),
            )
            raise

        input_type = "image" if image_used else "text"
        structured = standardize_answer(answer, input_type=input_type)
        source_refs = [
            str(item) for item in request.options.get("xingchen_knowledge_sources", [])
        ]
        artifact = Artifact(
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content={
                "mode": self.registry.get(agent_id).mode,
                "answer": str(structured["answer_text"]),
                "knowledge_sources": source_refs,
            },
            source_refs=source_refs,
            confidence=structured["confidence"],
        )
        return AgentResult(
            agent_id=agent_id,
            provider=self.provider_name,
            answer=str(structured["answer_text"]),
            structured_result=structured,
            artifacts=[artifact],
            citations=source_refs,
            confidence=structured["confidence"],
            metrics={
                "provider_latency_ms": int((perf_counter() - started) * 1000),
                "model_calls": 1,
            },
        )

    async def cancel(self, run_id: str) -> None:
        del run_id

    async def get_status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "unsupported", "provider": "xingchen"}
