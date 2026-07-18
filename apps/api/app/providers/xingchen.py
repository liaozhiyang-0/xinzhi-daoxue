from __future__ import annotations

import asyncio
import json
import logging
from time import perf_counter
from typing import Any

import httpx

from app.agents.registry import AgentDefinition, AgentRegistry
from app.contracts import (
    AgentRequest,
    AgentResult,
    Artifact,
    AttachmentRef,
    RunMetrics,
    TaskRequestContext,
)
from app.core.config import Settings
from app.core.errors import (
    AgentConfigurationIncompleteError,
    AgentInputNotSupportedError,
    ProviderCircuitOpenError,
    ValidationAppError,
    XingchenConnectionError,
    XingchenHttpError,
    XingchenResponseParseError,
    XingchenTimeoutError,
)
from app.core.logging import mask_sensitive_text
from app.providers.base import AgentProvider
from app.services.agent_runtime import (
    AgentInputMapper,
    ProviderCircuitBreaker,
    WorkflowOutputParserRegistry,
)
from app.services.storage import StorageService

logger = logging.getLogger(__name__)
TEXT_FIELDS = ("text", "question", "problem", "query", "prompt")
IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg"}
DEFAULT_IMAGE_PROMPT = "请识别并解答图片中的电路题，说明关键步骤和最终答案。"
STRUCTURED_LIST_FIELDS = ("key_equations", "assumptions", "remaining_risks")
STRUCTURED_TEXT_FIELDS = (
    "answer_text",
    "problem_summary",
    "final_answer",
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
    image_url: str | None = None,
    definition: AgentDefinition | None = None,
    flow_id: str | None = None,
) -> dict[str, Any]:
    ext = {"caller": "workflow"}
    if settings.xingchen_bot_id.strip():
        ext["bot_id"] = settings.xingchen_bot_id.strip()
    mapping = definition.input_mapping if definition else {}
    text_parameter = mapping.get("text", "AGENT_USER_INPUT")
    image_parameter = mapping.get("image", "USER_INPUT_image")
    question = extract_input_text(request)
    packet = request.options.get("retrieval_context_packet", {})
    retrieved_context = request.options.get("retrieved_context", "")
    if not retrieved_context and isinstance(packet, dict):
        retrieved_context = str(packet.get("formatted_context", ""))
    logical_values = {
        "text": question,
        "question": question,
        "course_id": request.course_id or "UNKNOWN",
        "intent": request.intent.value,
        "retrieved_context": retrieved_context,
        "previous_answer_summary": request.options.get(
            "previous_answer_summary",
            request.canonical_input.get("previous_answer_summary", ""),
        ),
        "conversation_summary": request.options.get(
            "conversation_summary",
            request.canonical_input.get("conversation_summary", ""),
        ),
        "response_depth": request.options.get("response_depth", "standard"),
        "request_id": request.options.get("request_id", request.task_id),
    }
    parameters: dict[str, str] = {}
    if definition is not None and definition.input_rules:
        input_type = classify_input(request, definition)
        context = TaskRequestContext.from_agent_request(request, input_mode=input_type)
        parameters = (
            AgentInputMapper()
            .map(
                definition,
                context,
                retrieval_context=str(retrieved_context or ""),
                image_url=image_url,
            )
            .parameters
        )
    elif mapping:
        for logical_name, parameter_name in mapping.items():
            if logical_name == "image":
                continue
            value = logical_values.get(logical_name, "")
            if isinstance(value, str):
                parameters[parameter_name] = value
            elif value is None:
                parameters[parameter_name] = ""
            else:
                parameters[parameter_name] = json.dumps(value, ensure_ascii=False)
    else:
        parameters[text_parameter] = question
    if image_url and image_parameter not in parameters:
        parameters[image_parameter] = image_url
    return {
        "flow_id": flow_id or settings.xingchen_solver_ct_flow_id,
        "uid": settings.xingchen_uid,
        "parameters": parameters,
        "ext": ext,
        "stream": False,
    }


def get_single_image(request: AgentRequest) -> AttachmentRef | None:
    if not request.attachments:
        return None
    if len(request.attachments) != 1:
        raise AgentInputNotSupportedError("星辰工作流当前只支持单张图片")
    attachment = request.attachments[0]
    if attachment.content_type not in IMAGE_CONTENT_TYPES:
        raise AgentInputNotSupportedError("星辰工作流仅支持 PNG、JPG 或 JPEG")
    return attachment


def classify_input(request: AgentRequest, definition: AgentDefinition) -> str:
    has_text = any(
        isinstance(request.canonical_input.get(field), str)
        and bool(request.canonical_input[field].strip())
        for field in TEXT_FIELDS
    )
    attachment = get_single_image(request)
    input_type = (
        "text_and_single_image"
        if has_text and attachment
        else "single_image"
        if attachment
        else "text"
        if has_text
        else "empty"
    )
    if input_type == "empty" or input_type not in definition.supports:
        raise AgentInputNotSupportedError(
            "Agent 不支持当前输入类型",
            details={
                "agent_id": definition.agent_id,
                "input_type": input_type,
                "supports": sorted(definition.supports),
            },
        )
    return input_type


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


def _json_object_from_answer(answer: str) -> dict[str, Any] | None:
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


def _line_protocol_object(answer: str) -> dict[str, Any] | None:
    """Parse the published LEARN end node's ordered, newline-delimited fields."""

    lines = [line.strip() for line in answer.splitlines()]
    if len(lines) < 10 or lines[0] not in {
        "success",
        "completed",
        "partial",
        "failed",
        "misrouted",
    }:
        return None
    return {
        "status": lines[0],
        "course_id": lines[1],
        "intent": lines[2],
        "answer": "\n".join(lines[3:-6]).strip(),
        "key_points_json": lines[-6],
        "source_references_json": lines[-5],
        "warnings_json": lines[-4],
        "confidence": lines[-3],
        "parse_status": lines[-2],
        "request_id": lines[-1],
    }


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [item.strip() for item in value.split(",") if item.strip()]
    return parsed if isinstance(parsed, list) else []


def standardize_answer(
    answer: str,
    *,
    input_type: str,
    output_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Best-effort mapping that always preserves the upstream student answer."""

    structured: dict[str, Any] = {
        "status": "completed",
        "input_type": input_type,
        "answer_text": answer,
        "problem_summary": "",
        "key_equations": [],
        "final_answer": "",
        "assumptions": [],
        "remaining_risks": [],
        "confidence": None,
    }
    payload = _json_object_from_answer(answer)
    if payload is None and output_mapping:
        payload = _line_protocol_object(answer)
    if payload is None:
        return structured

    if output_mapping:

        def output_value(logical_name: str, default: Any = None) -> Any:
            return payload.get(output_mapping.get(logical_name, logical_name), default)

        mapped_answer = output_value("answer", "")
        if isinstance(mapped_answer, str) and mapped_answer.strip():
            structured["answer_text"] = mapped_answer.strip()
        structured.update(
            {
                "status": str(output_value("status", "completed") or "completed"),
                "course_id": str(output_value("course_id", "") or ""),
                "intent": str(output_value("intent", "") or ""),
                "key_points": [
                    str(item) for item in _json_list(output_value("key_points", []))
                ],
                "source_references": [
                    str(item)
                    for item in _json_list(output_value("source_references", []))
                    if str(item).strip()
                ],
                "warnings": [
                    str(item) for item in _json_list(output_value("warnings", []))
                ],
                "parse_status": str(output_value("parse_status", "") or ""),
                "request_id": str(output_value("request_id", "") or ""),
            }
        )
        confidence = output_value("confidence")
        if isinstance(confidence, str):
            try:
                confidence = float(confidence)
            except ValueError:
                confidence = None
        if (
            isinstance(confidence, (int, float))
            and not isinstance(confidence, bool)
            and 0 <= confidence <= 1
        ):
            structured["confidence"] = float(confidence)
        return structured

    for field in STRUCTURED_TEXT_FIELDS:
        value = payload.get(field)
        if isinstance(value, str):
            structured[field] = value.strip()
    if not structured["answer_text"]:
        structured["answer_text"] = answer

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
        self._owns_client = client is None
        self.client = client
        self.input_mapper = AgentInputMapper()
        self.output_parsers = WorkflowOutputParserRegistry()
        self._semaphore = asyncio.Semaphore(settings.cloud_concurrency_limit)
        self._active_requests = 0
        self.circuit_breaker = ProviderCircuitBreaker(
            failure_threshold=settings.cloud_circuit_failure_threshold,
            reset_seconds=settings.cloud_circuit_reset_seconds,
        )

    def _client(self) -> httpx.AsyncClient:
        """Return the provider-scoped connection pool, creating it lazily."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=self.settings.xingchen_connect_timeout_seconds,
                    read=self.settings.xingchen_read_timeout_seconds,
                    write=self.settings.xingchen_write_timeout_seconds,
                    pool=self.settings.xingchen_pool_timeout_seconds,
                ),
                limits=httpx.Limits(
                    max_connections=self.settings.xingchen_max_connections,
                    max_keepalive_connections=(
                        self.settings.xingchen_max_keepalive_connections
                    ),
                ),
            )
        return self.client

    @property
    def is_available(self) -> bool:
        return any(
            self.registry.is_runtime_available(agent.agent_id, self.settings)
            for agent in self.registry.list_agents()
            if agent.provider == "xingchen"
        )

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
        definition: AgentDefinition,
        flow_id: str,
        request: AgentRequest,
    ) -> tuple[httpx.Response, bool]:
        attachment = get_single_image(request)
        image_url = await self._upload_image(client, attachment) if attachment else None
        payload = build_workflow_payload(
            self.settings,
            request,
            image_url=image_url,
            definition=definition,
            flow_id=flow_id,
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
        if stream:
            raise ValidationAppError("本阶段仅支持星辰 stream=false")
        try:
            definition = self.registry.get(agent_id)
        except KeyError as exc:
            raise ValidationAppError("Xingchen Provider 收到未注册 Agent") from exc
        if definition.provider != "xingchen" or not definition.enabled:
            raise ValidationAppError("Agent 未启用星辰 Provider")
        flow_id = self.registry.resolve_flow_id(agent_id, self.settings)
        if (
            not self.registry.is_runtime_available(agent_id, self.settings)
            or not flow_id
        ):
            raise AgentConfigurationIncompleteError(
                "Agent 的星辰凭据、发布状态或 Flow ID 配置不完整",
                details={"agent_id": agent_id, "flow_configured": bool(flow_id)},
            )
        input_type = classify_input(request, definition)
        if not self.circuit_breaker.allow_request():
            raise ProviderCircuitOpenError(
                "星辰 Provider 熔断中，已阻止必然失败的云端请求",
                details={"state": self.circuit_breaker.state},
            )

        started = perf_counter()
        try:
            async with self._semaphore:
                self._active_requests += 1
                try:
                    response, image_used = await self._request_workflow(
                        self._client(), definition, flow_id, request
                    )
                finally:
                    self._active_requests -= 1
            if response.status_code >= 500:
                self.circuit_breaker.record_failure()
            else:
                self.circuit_breaker.record_success()
        except httpx.TimeoutException as exc:
            self.circuit_breaker.record_failure()
            raise XingchenTimeoutError("星辰工作流请求超时") from exc
        except httpx.RequestError as exc:
            self.circuit_breaker.record_failure()
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

        del image_used
        parsed_output = self.output_parsers.parse(
            answer,
            definition,
            input_type=input_type,
        )
        structured = parsed_output.structured
        declared_refs = [str(item) for item in structured.get("source_references", [])]
        packet = request.options.get("retrieval_context_packet", {})
        evidence_by_id: dict[str, str] = {}
        if isinstance(packet, dict):
            for item in packet.get("evidence", []):
                if isinstance(item, dict):
                    evidence_id = str(item.get("evidence_id", ""))
                    source_ref = str(item.get("source_ref", ""))
                    if evidence_id and source_ref:
                        evidence_by_id[evidence_id] = source_ref
        source_refs = [
            evidence_by_id[item] for item in declared_refs if item in evidence_by_id
        ]
        warnings = [str(item) for item in structured.get("warnings", [])]
        expected_request_id = str(request.options.get("request_id", request.task_id))
        returned_request_id = str(structured.get("request_id", ""))
        if definition.output_mapping and returned_request_id != expected_request_id:
            warnings.append("云端 request_id 未按输入值返回")
        artifact = Artifact(
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content={
                **structured,
                "mode": "xingchen_workflow",
                "knowledge_sources": source_refs,
            },
            source_refs=source_refs,
            confidence=structured["confidence"],
        )
        latency_ms = int((perf_counter() - started) * 1000)
        return AgentResult(
            agent_id=agent_id,
            provider=self.provider_name,
            answer=str(structured["answer_text"]),
            structured_result=structured,
            artifacts=[artifact],
            citations=source_refs,
            warnings=warnings,
            confidence=structured["confidence"],
            metrics=RunMetrics(provider_latency_ms=latency_ms),
            agent_version=definition.version,
            course_id=request.course_id,
            intent=request.intent.value,
            business_data=dict(structured.get("business_data", {})),
            assumptions=[str(item) for item in structured.get("assumptions", [])],
            remaining_risks=[
                str(item) for item in structured.get("remaining_risks", [])
            ],
            request_id=expected_request_id,
            task_id=request.task_id,
            cloud_status=f"cloud_{structured.get('status', 'completed')}",
            timings={"provider_ms": latency_ms},
        )

    def runtime_status(self) -> dict[str, Any]:
        return {
            **self.circuit_breaker.snapshot(),
            "active_requests": self._active_requests,
            "concurrency_limit": self.settings.cloud_concurrency_limit,
        }

    async def aclose(self) -> None:
        if self._owns_client and self.client is not None:
            await self.client.aclose()
            self.client = None

    async def cancel(self, run_id: str) -> None:
        del run_id

    async def get_status(self, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "unsupported", "provider": "xingchen"}
