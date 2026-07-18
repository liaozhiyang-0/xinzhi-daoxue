from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic, perf_counter
from typing import Any

from app.agents.registry import AgentDefinition, AgentRegistry, InputMappingRule
from app.contracts import (
    AgentExecutionPlan,
    AgentRequest,
    ExecutionTimeBudget,
    RouteDecision,
    TaskRequestContext,
)
from app.core.config import Settings
from app.core.errors import AgentInputNotSupportedError, ValidationAppError

IMAGE_PROMPT = "请识别并解答图片中的电路题，说明关键步骤和最终答案。"
SAFE_TRANSFORMS = {
    "string",
    "json_string",
    "bool_string",
    "number_string",
    "truncate",
    "default",
    "join_lines",
    "retrieval_context",
}
VALID_OUTPUT_STATUSES = {"success", "completed", "partial", "failed", "misrouted"}


@dataclass(frozen=True, slots=True)
class MappedAgentInput:
    parameters: dict[str, str]
    field_lengths: dict[str, int]
    redacted_preview: dict[str, str]


@dataclass(frozen=True, slots=True)
class ParsedWorkflowOutput:
    structured: dict[str, Any]
    answer_text: str
    warnings: list[str]
    confidence: float | None
    parse_status: str
    redacted_summary: dict[str, Any]


class AgentInputMapper:
    """Safe, finite transform mapper for Xingchen string start-node inputs."""

    def map(
        self,
        definition: AgentDefinition,
        context: TaskRequestContext,
        *,
        retrieval_context: str = "",
        image_url: str | None = None,
    ) -> MappedAgentInput:
        parameters: dict[str, str] = {}
        lengths: dict[str, int] = {}
        previews: dict[str, str] = {}
        missing: list[str] = []
        required = definition.input_contract.required
        for rule in definition.input_rules:
            if rule.source == "image":
                value: Any = image_url or ""
            else:
                value = self._source_value(
                    context, rule.source, retrieval_context=retrieval_context
                )
            if rule.source in required and self._is_empty(value):
                missing.append(rule.source)
            rendered = self._transform(value, rule)
            parameters[rule.parameter_name] = rendered
            lengths[rule.parameter_name] = len(rendered)
            previews[rule.parameter_name] = self._preview(rule.parameter_name, rendered)
        if missing:
            raise ValidationAppError(
                "Agent 必需输入缺失",
                details={
                    "agent_id": definition.agent_id,
                    "missing": sorted(set(missing)),
                },
            )
        return MappedAgentInput(parameters, lengths, previews)

    @staticmethod
    def _source_value(
        context: TaskRequestContext, source: str, *, retrieval_context: str
    ) -> Any:
        if source in {"text", "question"}:
            return context.question or (IMAGE_PROMPT if context.attachments else "")
        if source in {"retrieval_context", "retrieved_context"}:
            return retrieval_context or context.options.get("retrieved_context", "")
        if hasattr(context, source):
            return getattr(context, source)
        if source in context.canonical_input:
            return context.canonical_input[source]
        return context.options.get(source, "")

    @staticmethod
    def _is_empty(value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    @staticmethod
    def _transform(value: Any, rule: InputMappingRule) -> str:
        if rule.transform not in SAFE_TRANSFORMS:
            raise ValidationAppError(
                "Agent input transform 未注册",
                details={"transform": rule.transform, "field": rule.parameter_name},
            )
        if AgentInputMapper._is_empty(value):
            value = rule.default
        if rule.transform == "json_string" or isinstance(value, (dict, list, tuple)):
            rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        elif rule.transform == "bool_string":
            rendered = "true" if bool(value) else "false"
        elif rule.transform == "number_string":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ValidationAppError("number_string 输入必须是数字")
            rendered = str(value)
        elif rule.transform == "join_lines":
            rendered = (
                "\n".join(str(item) for item in value)
                if isinstance(value, (list, tuple))
                else str(value or "")
            )
        else:
            rendered = str(value or "")
        return rendered[: rule.max_length] if rule.max_length is not None else rendered

    @staticmethod
    def _preview(name: str, value: str) -> str:
        if any(
            token in name.casefold()
            for token in ("key", "secret", "authorization", "flow")
        ):
            return "***"
        if len(value) > 120:
            return f"{value[:80]}…[len={len(value)}]"
        return value


class WorkflowOutputParserRegistry:
    """Provider-independent workflow output parser and mapping registry."""

    def __init__(self) -> None:
        self._custom: dict[str, Callable[[str, AgentDefinition], dict[str, Any]]] = {}

    def register(
        self, name: str, parser: Callable[[str, AgentDefinition], dict[str, Any]]
    ) -> None:
        if not name or name in self._custom:
            raise ValueError(f"重复或无效 parser: {name}")
        self._custom[name] = parser

    def parse(
        self,
        answer: str,
        definition: AgentDefinition,
        *,
        input_type: str,
    ) -> ParsedWorkflowOutput:
        parser_type = definition.provider_config.parser_type
        payload: dict[str, Any] | None = None
        parse_status = "plain_text"
        if parser_type in {"json", "json_or_fixed_line"}:
            payload = self._json_object(answer)
            parse_status = "json" if payload is not None else parse_status
        if payload is None and parser_type in {
            "fixed_line_fields",
            "json_or_fixed_line",
        }:
            payload = self._fixed_lines(answer, definition)
            parse_status = "fixed_line_fields" if payload is not None else parse_status
        if parser_type == "custom_registered_parser":
            name = str(definition.provider_config.parser_options.get("name", ""))
            if name not in self._custom:
                raise ValidationAppError("配置的自定义输出 Parser 未注册")
            payload = self._custom[name](answer, definition)
            parse_status = f"custom:{name}"
        if parser_type == "plain_text":
            payload = None
        if payload is None and parser_type not in {
            "plain_text",
            "json_or_fixed_line",
            "json",
        }:
            raise ValidationAppError("工作流输出无法按契约解析")
        structured = self._standardize(
            answer,
            payload,
            definition,
            input_type=input_type,
            parse_status=parse_status,
        )
        return ParsedWorkflowOutput(
            structured=structured,
            answer_text=str(structured["answer_text"]),
            warnings=[str(item) for item in structured.get("warnings", [])],
            confidence=structured.get("confidence"),
            parse_status=str(structured.get("parse_status", parse_status)),
            redacted_summary={
                "parser_type": parser_type,
                "parse_status": parse_status,
                "answer_length": len(answer),
                "fields": sorted(structured),
            },
        )

    @staticmethod
    def _json_object(answer: str) -> dict[str, Any] | None:
        candidate = answer.strip()
        fenced = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.DOTALL | re.IGNORECASE
        )
        if fenced:
            candidate = fenced.group(1)
        else:
            start, end = candidate.find("{"), candidate.rfind("}")
            if start >= 0 and end > start:
                candidate = candidate[start : end + 1]
        try:
            payload = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _fixed_lines(answer: str, definition: AgentDefinition) -> dict[str, Any] | None:
        fields = definition.provider_config.parser_options.get("ordered_fields", [])
        if not isinstance(fields, list) or not fields:
            return None
        lines = [line.strip() for line in answer.splitlines()]
        if len(lines) < len(fields):
            return None
        if len(fields) == 10 and fields[3] == "answer":
            return {
                str(fields[0]): lines[0],
                str(fields[1]): lines[1],
                str(fields[2]): lines[2],
                str(fields[3]): "\n".join(lines[3:-6]).strip(),
                **{
                    str(field): lines[-6 + index]
                    for index, field in enumerate(fields[4:])
                },
            }
        return {str(field): lines[index] for index, field in enumerate(fields)}

    @classmethod
    def _standardize(
        cls,
        answer: str,
        payload: dict[str, Any] | None,
        definition: AgentDefinition,
        *,
        input_type: str,
        parse_status: str,
    ) -> dict[str, Any]:
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
            "warnings": [],
            "parse_status": parse_status,
            "business_data": {},
        }
        if payload is None:
            return structured
        for rule in definition.output_rules:
            value = payload.get(rule.source)
            value = cls._parse_value(value, rule.parser)
            cls._set_target(structured, rule.target, value)
        if not definition.output_rules:
            for key, value in payload.items():
                if key in structured:
                    structured[key] = value
                else:
                    structured["business_data"][str(key)] = value
        mapped_answer = structured.get("answer")
        if isinstance(mapped_answer, str) and mapped_answer.strip():
            structured["answer_text"] = mapped_answer.strip()
        if isinstance(payload.get("answer_text"), str):
            structured["answer_text"] = payload["answer_text"].strip() or answer
        status = str(structured.get("status", "completed")).casefold()
        structured["status"] = status if status in VALID_OUTPUT_STATUSES else "failed"
        if status not in VALID_OUTPUT_STATUSES:
            structured["warnings"].append("云端 status 非法，已校正为 failed")
        for key in (
            "key_points",
            "source_references",
            "warnings",
            "key_equations",
            "assumptions",
            "remaining_risks",
        ):
            structured[key] = cls._list_value(structured.get(key, []))
        confidence = cls._float_value(structured.get("confidence"))
        structured["confidence"] = (
            confidence if confidence is not None and 0 <= confidence <= 1 else None
        )
        return structured

    @staticmethod
    def _parse_value(value: Any, parser: str) -> Any:
        if parser in {"json_string", "list_json"} and isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [] if parser == "list_json" else value
        if parser in {"float", "float_string"}:
            return WorkflowOutputParserRegistry._float_value(value)
        return value

    @staticmethod
    def _set_target(target: dict[str, Any], path: str, value: Any) -> None:
        parts = path.split(".")
        cursor = target
        for part in parts[:-1]:
            nested = cursor.setdefault(part, {})
            if not isinstance(nested, dict):
                return
            cursor = nested
        cursor[parts[-1]] = value

    @staticmethod
    def _list_value(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if not isinstance(value, str) or not value.strip():
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [item.strip() for item in value.split(",") if item.strip()]
        return parsed if isinstance(parsed, list) else []

    @staticmethod
    def _float_value(value: Any) -> float | None:
        try:
            return (
                float(value)
                if value is not None and not isinstance(value, bool)
                else None
            )
        except (TypeError, ValueError):
            return None


class AgentExecutionPlanner:
    def __init__(self, registry: AgentRegistry, settings: Settings) -> None:
        self.registry = registry
        self.settings = settings

    def build(
        self, decision: RouteDecision, request: AgentRequest
    ) -> AgentExecutionPlan:
        definition = self.registry.get(decision.agent_id)
        input_mode = self._input_mode(request)
        if input_mode not in definition.supports:
            raise AgentInputNotSupportedError(
                "目标 Agent 不支持当前输入类型",
                details={"agent_id": definition.agent_id, "input_mode": input_mode},
            )
        policy = definition.retrieval_policy
        explicit_images = request.options.get("include_images")
        use_images = bool(
            policy.image_top_k > 0
            and (
                explicit_images is True
                or "image" in input_mode
                or request.intent.value in {"explain_concept", "summarize_knowledge"}
            )
        )
        reranker_mode = policy.reranker_mode
        if request.options.get("use_reranker") is True:
            reranker_mode = "on"
        budget = ExecutionTimeBudget.create(
            cloud_timeout_seconds=definition.provider_config.timeout_seconds,
            route_budget_ms=self.settings.route_budget_ms,
            normalization_budget_ms=self.settings.normalization_budget_ms,
            retrieval_p95_target_ms=self.settings.retrieval_p95_target_ms,
            context_format_budget_ms=self.settings.context_format_budget_ms,
            local_total_p95_target_ms=self.settings.local_total_p95_target_ms,
        )
        return AgentExecutionPlan(
            agent_id=definition.agent_id,
            provider_type=definition.provider,
            route_status=decision.route_status.value,
            use_rag=policy.enabled
            and policy.mode not in {"no_rag", "external_source_context"},
            retrieval_policy_name=policy.policy_name,
            retrieval_mode=policy.mode,
            use_images=use_images,
            reranker_mode=reranker_mode,
            context_budget=policy.context_max_chars,
            cloud_timeout_seconds=definition.provider_config.timeout_seconds,
            max_retries=definition.provider_config.max_retries,
            fallback_type=definition.fallback.type,
            fallback_handler=definition.fallback.handler,
            input_mode=input_mode,
            configured=self.registry.is_configured(definition.agent_id, self.settings),
            published=definition.publication_status in {"published", "local"},
            debug_enabled=self.settings.rag_debug_enabled,
            budget=budget,
            skipped_optional_stages=[
                stage
                for stage, skipped in (
                    ("image", not use_images),
                    ("reranker", reranker_mode == "off"),
                )
                if skipped
            ],
        )

    @staticmethod
    def _input_mode(request: AgentRequest) -> str:
        has_text = any(
            isinstance(request.canonical_input.get(key), str)
            and request.canonical_input[key].strip()
            for key in ("text", "question", "problem", "query", "prompt")
        )
        if len(request.attachments) > 1:
            raise AgentInputNotSupportedError("任务输入仅支持单张图片")
        if request.attachments and has_text:
            return "text_and_single_image"
        if request.attachments:
            return "single_image"
        if has_text:
            return "text"
        raise AgentInputNotSupportedError("任务输入不能为空")


class ProviderCircuitBreaker:
    def __init__(self, *, failure_threshold: int, reset_seconds: float) -> None:
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self.failures = 0
        self.opened_at: float | None = None
        self.probe_in_flight = False

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "available" if self.failures == 0 else "degraded"
        if monotonic() - self.opened_at >= self.reset_seconds:
            return "recovering"
        return "open_circuit"

    def allow_request(self) -> bool:
        state = self.state
        if state in {"available", "degraded"}:
            return True
        if state == "recovering" and not self.probe_in_flight:
            self.probe_in_flight = True
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None
        self.probe_in_flight = False

    def record_failure(self) -> None:
        self.failures += 1
        self.probe_in_flight = False
        if self.failures >= self.failure_threshold:
            self.opened_at = monotonic()

    def snapshot(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "consecutive_failures": self.failures,
            "reset_seconds": self.reset_seconds,
        }


def timed_call(call: Callable[[], Any]) -> tuple[Any, int]:
    started = perf_counter()
    return call(), int((perf_counter() - started) * 1000)
