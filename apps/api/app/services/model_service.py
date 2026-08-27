from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel

from app.contracts import (
    ImageInput,
    ModelResponse,
    ModelStreamEvent,
    ModelUsage,
    ResponseDepth,
)
from app.core.config import Settings
from app.core.errors import (
    AuthenticationError,
    InvalidModelRequestError,
    ModelProviderError,
    ModelTimeoutError,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    StructuredOutputError,
)
from app.observability import ModelCallRecord, ModelTracer
from app.providers.llm import BaseModelProvider
from app.services.agent_runtime import ProviderCircuitBreaker
from app.services.model_registry import ModelDefinition, ModelRegistry, ModelRoute
from app.services.response_depth import resolve_response_depth

T = TypeVar("T", bound=ModelResponse)


@dataclass(frozen=True, slots=True)
class ModelPreflight:
    """Provider-free availability result for one model task route."""

    task_type: str
    modality: str
    available: bool
    usable_aliases: tuple[str, ...]
    attempted_aliases: tuple[str, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "modality": self.modality,
            "available": self.available,
            "usable_aliases": list(self.usable_aliases),
            "attempted_aliases": list(self.attempted_aliases),
            "reason": self.reason,
        }


class ModelService:
    """Task-aware model gateway with bounded retries, fallback and safe tracing."""

    def __init__(
        self,
        settings: Settings,
        registry: ModelRegistry,
        providers: dict[str, BaseModelProvider],
        tracer: ModelTracer,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.providers = providers
        self.tracer = tracer
        self._global = asyncio.Semaphore(settings.model_global_max_concurrency)
        self._provider_limits = {
            "iflytek_spark": asyncio.Semaphore(settings.spark_max_concurrency),
            "dashscope": asyncio.Semaphore(settings.qwen_max_concurrency),
        }
        self._circuits: dict[str, ProviderCircuitBreaker] = {}
        self._vision = asyncio.Semaphore(settings.vision_max_concurrency)

    def preflight(
        self, task_type: str, *, modality: str = "text"
    ) -> ModelPreflight:
        """Check model route configuration without making a network call."""

        try:
            route = self.registry.get_route(task_type)
        except KeyError:
            return ModelPreflight(
                task_type=task_type,
                modality=modality,
                available=False,
                usable_aliases=(),
                attempted_aliases=(),
                reason="model_route_missing",
            )

        aliases = tuple(
            alias for alias in (route.primary, route.fallback) if alias is not None
        )
        usable: list[str] = []
        reasons: list[str] = []
        for alias in aliases:
            definition = self.registry.get_model(alias)
            if modality not in definition.modalities:
                reasons.append(f"model_modality_unsupported:{alias}")
                continue
            if not self.registry.enabled(definition):
                reasons.append(f"model_disabled:{alias}")
                continue
            provider = self.providers.get(definition.provider)
            if provider is None:
                reasons.append(f"model_provider_missing:{alias}")
                continue
            if not provider.configured:
                reasons.append(f"model_provider_unconfigured:{alias}")
                continue
            usable.append(alias)

        return ModelPreflight(
            task_type=task_type,
            modality=modality,
            available=bool(usable),
            usable_aliases=tuple(usable),
            attempted_aliases=aliases,
            reason=(
                "model_route_available"
                if usable
                else (reasons[0] if reasons else "model_unavailable")
            ),
        )

    def configuration_snapshot(self) -> dict[str, Any]:
        """Return a redacted, provider-free model readiness snapshot.

        Health and release checks must distinguish the Agent execution
        boundary from the actual text/image model providers. This snapshot
        performs no network call and never exposes credentials.
        """

        providers = {
            name: {
                "configured": bool(provider.configured),
                "default_model": provider.default_model,
            }
            for name, provider in self.providers.items()
        }
        routes: dict[str, dict[str, Any]] = {}
        unavailable_routes: list[str] = []
        for task_type, route in self.registry.routes.items():
            preflight = self.preflight(task_type)
            routes[task_type] = {
                "primary": route.primary,
                "fallback": route.fallback,
                "available": preflight.available,
                "usable_aliases": list(preflight.usable_aliases),
                "reason": preflight.reason,
            }
            if not preflight.available:
                unavailable_routes.append(task_type)
        configured_provider_names = sorted(
            name for name, item in providers.items() if item["configured"]
        )
        return {
            "status": (
                "ready"
                if not self.registry.errors and not unavailable_routes
                else "degraded"
            ),
            "configured_provider_names": configured_provider_names,
            "real_provider_configured": bool(configured_provider_names),
            "providers": providers,
            "route_count": len(routes),
            "unavailable_route_count": len(unavailable_routes),
            "unavailable_routes": unavailable_routes,
            "registry_errors": list(self.registry.errors),
        }

    async def generate_for_task(
        self,
        task_type: str,
        *,
        messages: list[dict[str, Any]],
        request_id: str | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ModelResponse:
        return await self._execute_route(
            task_type,
            request_id=request_id,
            input_hash=self._hash_messages(messages),
            image_count=0,
            high_resolution=False,
            operation=lambda provider, definition, options: provider.generate_text(
                messages=messages,
                model=definition.model,
                temperature=float(options.pop("temperature", 0.2)),
                max_tokens=self._optional_int(options.pop("max_tokens", None)),
                extra_options=options,
            ),
            extra_options=extra_options,
        )

    async def generate_json_for_task(
        self,
        task_type: str,
        *,
        messages: list[dict[str, Any]],
        schema: type[BaseModel] | None = None,
        request_id: str | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ModelResponse:
        return await self._execute_route(
            task_type,
            request_id=request_id,
            input_hash=self._hash_messages(messages),
            image_count=0,
            high_resolution=False,
            operation=lambda provider, definition, options: provider.generate_json(
                messages=messages,
                model=definition.model,
                schema=schema,
                extra_options=options,
            ),
            extra_options=extra_options,
        )

    async def analyze_images_for_task(
        self,
        task_type: str,
        *,
        prompt: str,
        images: list[ImageInput],
        request_id: str | None = None,
        json_mode: bool = False,
        high_resolution: bool | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ModelResponse:
        route = self.registry.get_route(task_type)
        effective_high_resolution = bool(
            route.options.get("high_resolution", False)
            if high_resolution is None
            else high_resolution
        )
        return await self._execute_route(
            task_type,
            request_id=request_id,
            input_hash=hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16],
            image_count=len(images),
            high_resolution=effective_high_resolution,
            operation=lambda provider, definition, options: (
                provider.generate_multimodal(
                    prompt=prompt,
                    images=images,
                    model=definition.model,
                    high_resolution=effective_high_resolution,
                    json_mode=json_mode,
                    extra_options=options,
                )
            ),
            extra_options=extra_options,
            vision=True,
        )

    async def stream_for_task(
        self,
        task_type: str,
        *,
        messages: list[dict[str, Any]],
        extra_options: dict[str, Any] | None = None,
    ) -> AsyncIterator[ModelStreamEvent]:
        route = self.registry.get_route(task_type)
        call_options = dict(extra_options or {})
        response_depth = call_options.pop("response_depth", None)
        alias = self._response_depth_alias(
            route, response_depth, vision=False
        ) or route.primary
        definition, provider = self._resolve(alias)
        options = self._options(definition, route.options, call_options)
        async with self._global, self._provider_limit(definition.provider):
            async for event in provider.stream_text(
                messages=messages,
                model=definition.model,
                extra_options=options,
            ):
                yield event

    async def verify_with_secondary_model(
        self,
        task_type: str,
        *,
        messages: list[dict[str, Any]],
        request_id: str | None = None,
    ) -> ModelResponse:
        route = self.registry.get_route(task_type)
        if not route.verifier:
            raise InvalidModelRequestError(
                f"任务 {task_type} 未配置校验模型",
                model=route.primary,
            )
        return await self._execute_alias(
            task_type,
            route.verifier,
            request_id=request_id,
            input_hash=self._hash_messages(messages),
            image_count=0,
            high_resolution=False,
            fallback_used=False,
            operation=lambda provider, definition, options: provider.generate_text(
                messages=messages,
                model=definition.model,
                temperature=float(options.pop("temperature", 0.1)),
                max_tokens=self._optional_int(options.pop("max_tokens", None)),
                extra_options=options,
            ),
            extra_options=None,
            vision=False,
            max_retries=self.settings.model_max_retries,
        )

    async def _execute_route(
        self,
        task_type: str,
        *,
        request_id: str | None,
        input_hash: str,
        image_count: int,
        high_resolution: bool,
        operation: Callable[
            [BaseModelProvider, ModelDefinition, dict[str, Any]],
            Awaitable[ModelResponse],
        ],
        extra_options: dict[str, Any] | None,
        vision: bool = False,
    ) -> ModelResponse:
        route = self.registry.get_route(task_type)
        call_options = dict(extra_options or {})
        response_depth = call_options.pop("response_depth", None)
        allow_route_fallback = bool(call_options.pop("_allow_route_fallback", True))
        allow_structured_fallback = bool(
            call_options.pop("_allow_structured_fallback", False)
        )
        prefer_route_fallback = bool(
            call_options.pop("_prefer_route_fallback", False)
        )
        preferred_alias = call_options.pop("_preferred_route_alias", None)
        max_retries = (
            self.settings.model_max_retries
            if route.max_retries is None
            else route.max_retries
        )
        route_aliases = {route.primary, route.fallback}
        if preferred_alias is not None and preferred_alias not in route_aliases:
            raise InvalidModelRequestError(
                f"模型别名 {preferred_alias} 不属于任务路由 {task_type}",
                details={
                    "task_type": task_type,
                    "preferred_alias": preferred_alias,
                },
            )
        if preferred_alias is not None:
            aliases = [preferred_alias]
        elif prefer_route_fallback and route.fallback:
            aliases = [
                route.fallback,
                route.primary if allow_route_fallback else None,
            ]
        else:
            depth_alias = self._response_depth_alias(
                route, response_depth, vision=vision
            )
            if depth_alias is None:
                aliases = [
                    route.primary,
                    route.fallback if allow_route_fallback else None,
                ]
            else:
                aliases = [depth_alias]
                if allow_route_fallback:
                    aliases.extend((route.primary, route.fallback))
        aliases = list(dict.fromkeys(item for item in aliases if item))
        last_error: ModelProviderError | None = None
        failed_usage: ModelUsage | None = None
        for index, alias in enumerate(item for item in aliases if item):
            if (
                index > 0
                and isinstance(last_error, ModelTimeoutError)
                and not route.fallback_on_timeout
            ):
                break
            circuit = self._circuit(alias)
            if not circuit.allow_request():
                definition = self.registry.get_model(alias)
                last_error = ProviderUnavailableError(
                    f"模型别名 {alias} 暂处于熔断冷却期",
                    provider=definition.provider,
                    model=definition.model,
                    details={
                        "circuit_open": True,
                        **circuit.snapshot(),
                    },
                )
                continue
            try:
                response = await self._execute_alias(
                    task_type,
                    alias,
                    request_id=request_id,
                    input_hash=input_hash,
                    image_count=image_count,
                    high_resolution=high_resolution,
                    fallback_used=index > 0,
                    operation=operation,
                    extra_options={**route.options, **call_options},
                    vision=vision,
                    max_retries=max_retries,
                )
                circuit.record_success()
                if index > 0:
                    response = response.model_copy(
                        update={
                            "raw_metadata": {
                                **response.raw_metadata,
                                "route_fallback_used": True,
                                "fallback_count": 1,
                                "fallback_reason": (
                                    last_error.code
                                    if last_error is not None
                                    else "primary_model_error"
                                ),
                                "source_model": route.primary,
                                "target_model": alias,
                            }
                        }
                    )
                if failed_usage is not None:
                    response = response.model_copy(
                        update={
                            "usage": self._merge_usage(failed_usage, response.usage),
                            "raw_metadata": {
                                **response.raw_metadata,
                                "failed_attempt_usage_included": True,
                            },
                        }
                    )
                return response
            except ModelProviderError as exc:
                last_error = exc
                if self._trips_circuit(exc):
                    circuit.record_failure()
                failed_usage = self._merge_usage(
                    failed_usage, self._usage_from_details(exc.details)
                )
                if isinstance(exc, InvalidModelRequestError) or (
                    isinstance(exc, StructuredOutputError)
                    and not allow_structured_fallback
                ):
                    raise
        if last_error is not None:
            attempted = [item for item in aliases if item]
            last_error.details.update(
                {
                    "attempted_models": attempted,
                    "fallback_attempted": len(attempted) > 1,
                }
            )
            if failed_usage is not None:
                last_error.details["usage"] = failed_usage.model_dump(exclude_none=True)
            raise last_error
        raise ProviderNotConfiguredError(f"任务 {task_type} 没有可用模型")

    async def _execute_alias(
        self,
        task_type: str,
        alias: str,
        *,
        request_id: str | None,
        input_hash: str,
        image_count: int,
        high_resolution: bool,
        fallback_used: bool,
        operation: Callable[
            [BaseModelProvider, ModelDefinition, dict[str, Any]],
            Awaitable[ModelResponse],
        ],
        extra_options: dict[str, Any] | None,
        vision: bool,
        max_retries: int,
    ) -> ModelResponse:
        definition, provider = self._resolve(alias)
        max_attempts = 1 + max(0, min(1, max_retries))
        last_error: ModelProviderError | None = None
        for attempt in range(max_attempts):
            started = self.tracer.now()
            try:
                options = self._options(definition, {}, extra_options)
                if definition.provider != "iflytek_spark":
                    options.pop("spark_response_transport", None)
                    options.pop("spark_stream_total_timeout_seconds", None)
                async with self._global, self._provider_limit(definition.provider):
                    if vision:
                        async with self._vision:
                            response = await operation(provider, definition, options)
                    else:
                        response = await operation(provider, definition, options)
            except ModelProviderError as exc:
                last_error = exc
                self._trace(
                    started=started,
                    task_type=task_type,
                    definition=definition,
                    request_id=request_id,
                    input_hash=input_hash,
                    image_count=image_count,
                    high_resolution=high_resolution,
                    retry_count=attempt,
                    fallback_used=fallback_used,
                    error=exc,
                )
                if not exc.retryable or attempt + 1 >= max_attempts:
                    raise
                continue
            self._trace(
                started=started,
                task_type=task_type,
                definition=definition,
                request_id=request_id,
                input_hash=input_hash,
                image_count=image_count,
                high_resolution=high_resolution,
                retry_count=attempt,
                fallback_used=fallback_used,
                response=response,
            )
            return response.model_copy(update={"request_id": request_id})
        if last_error is not None:
            raise last_error
        raise ProviderNotConfiguredError("模型不可用")

    def _resolve(self, alias: str) -> tuple[ModelDefinition, BaseModelProvider]:
        definition = self.registry.get_model(alias)
        if not self.registry.enabled(definition):
            raise ProviderNotConfiguredError(
                f"模型别名 {alias} 已禁用",
                provider=definition.provider,
                model=definition.model,
            )
        provider = self.providers.get(definition.provider)
        if provider is None:
            raise ProviderNotConfiguredError(
                f"Provider未注册: {definition.provider}",
                provider=definition.provider,
                model=definition.model,
            )
        if not provider.configured:
            key_name = (
                "IFLYTEK_SPARK_API_KEY"
                if definition.provider == "iflytek_spark"
                else "DASHSCOPE_API_KEY"
            )
            raise ProviderNotConfiguredError(
                f"{key_name}未配置",
                provider=definition.provider,
                model=definition.model,
            )
        return definition, provider

    def _response_depth_alias(
        self,
        route: ModelRoute,
        raw_depth: Any,
        *,
        vision: bool,
    ) -> str | None:
        """Map the user-facing depth to the configured Qwen model tier."""

        try:
            primary = self.registry.get_model(route.primary)
        except KeyError:
            return None
        if primary.provider != "dashscope":
            return None

        depth = resolve_response_depth({"response_depth": raw_depth})
        if (
            depth is ResponseDepth.STANDARD
            and not vision
            and route.task_type in {"general_question_answer", "knowledge_answer"}
        ):
            # Interactive answers are latency-sensitive. Prefer the brief
            # Qwen tier for the standard UI depth; the configured route
            # primary remains available as a fallback below.
            alias = "qwen_brief"
        else:
            alias = {
                ResponseDepth.BRIEF: "qwen_brief",
                ResponseDepth.STANDARD: (
                    "qwen_vision_fast" if vision else "qwen_text_fast"
                ),
                ResponseDepth.DEEP: "qwen_vision_primary",
            }[depth]
        try:
            self.registry.get_model(alias)
        except KeyError:
            return None
        return alias

    def _provider_limit(self, provider: str) -> asyncio.Semaphore:
        return self._provider_limits.setdefault(provider, asyncio.Semaphore(1))

    def _circuit(self, alias: str) -> ProviderCircuitBreaker:
        return self._circuits.setdefault(
            alias,
            ProviderCircuitBreaker(
                failure_threshold=self.settings.model_circuit_failure_threshold,
                reset_seconds=self.settings.model_circuit_reset_seconds,
            ),
        )

    @staticmethod
    def _trips_circuit(error: ModelProviderError) -> bool:
        streamed_total_timeout = isinstance(error, ModelTimeoutError) and (
            error.details.get("response_transport") == "stream"
        )
        return isinstance(
            error,
            (
                AuthenticationError,
                ProviderNotConfiguredError,
                ProviderUnavailableError,
            ),
        ) or streamed_total_timeout

    @staticmethod
    def _options(
        definition: ModelDefinition,
        route_options: dict[str, Any],
        call_options: dict[str, Any] | None,
    ) -> dict[str, Any]:
        options = {
            **definition.default_options,
            **route_options,
            **(call_options or {}),
        }
        options.pop("high_resolution", None)
        options.setdefault("timeout", definition.timeout_seconds)
        return options

    def _trace(
        self,
        *,
        started: Any,
        task_type: str,
        definition: ModelDefinition,
        request_id: str | None,
        input_hash: str,
        image_count: int,
        high_resolution: bool,
        retry_count: int,
        fallback_used: bool,
        response: ModelResponse | None = None,
        error: ModelProviderError | None = None,
    ) -> None:
        usage = response.usage if response else None
        self.tracer.record(
            ModelCallRecord(
                trace_id=request_id or f"model_{uuid4().hex}",
                request_id=request_id,
                provider=definition.provider,
                model=definition.model,
                task_type=task_type,
                start_time=started,
                elapsed_ms=(
                    response.elapsed_ms
                    if response
                    else max(
                        0,
                        int((self.tracer.now() - started).total_seconds() * 1000),
                    )
                ),
                status="completed" if response else "failed",
                retry_count=retry_count,
                fallback_used=fallback_used,
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                total_tokens=usage.total_tokens if usage else None,
                image_count=image_count,
                high_resolution=high_resolution,
                provider_request_id=(
                    response.provider_request_id if response else None
                ),
                error_type=error.code if error else None,
                input_hash=input_hash,
            )
        )

    async def aclose(self) -> None:
        await asyncio.gather(
            *(provider.aclose() for provider in self.providers.values()),
            return_exceptions=True,
        )

    @staticmethod
    def _hash_messages(messages: list[dict[str, Any]]) -> str:
        summary = "|".join(
            f"{item.get('role', '')}:{len(str(item.get('content', '')))}"
            for item in messages
        )
        return hashlib.sha256(summary.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        return int(value) if value is not None else None

    @staticmethod
    def _usage_from_details(details: dict[str, Any]) -> ModelUsage | None:
        value = details.get("usage")
        if not isinstance(value, dict):
            return None
        return ModelUsage(
            prompt_tokens=ModelService._optional_int(value.get("prompt_tokens")),
            completion_tokens=ModelService._optional_int(
                value.get("completion_tokens")
            ),
            total_tokens=ModelService._optional_int(value.get("total_tokens")),
        )

    @staticmethod
    def _merge_usage(
        left: ModelUsage | None, right: ModelUsage | None
    ) -> ModelUsage | None:
        if left is None:
            return right
        if right is None:
            return left
        return ModelUsage(
            prompt_tokens=ModelService._sum_token_field(
                left.prompt_tokens, right.prompt_tokens
            ),
            completion_tokens=ModelService._sum_token_field(
                left.completion_tokens, right.completion_tokens
            ),
            total_tokens=ModelService._sum_token_field(
                left.total_tokens, right.total_tokens
            ),
        )

    @staticmethod
    def _sum_token_field(left: int | None, right: int | None) -> int | None:
        if left is None and right is None:
            return None
        return (left or 0) + (right or 0)
