from __future__ import annotations

from typing import Any


class AppError(Exception):
    code = "app_error"
    status_code = 500

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(AppError):
    code = "configuration_error"


class ProviderError(AppError):
    code = "provider_error"
    status_code = 502


class ProviderTimeoutError(ProviderError):
    code = "provider_timeout"
    status_code = 504


class ProviderCancelledError(ProviderError):
    code = "provider_cancelled"
    status_code = 409


class XingchenConfigurationError(ConfigurationError):
    code = "xingchen_configuration_error"
    status_code = 503


class XingchenConnectionError(ProviderError):
    code = "xingchen_connection_error"


class XingchenTimeoutError(ProviderTimeoutError):
    code = "xingchen_timeout"


class XingchenHttpError(ProviderError):
    code = "xingchen_http_error"


class XingchenResponseParseError(ProviderError):
    code = "xingchen_response_parse_error"


class ProviderCircuitOpenError(ProviderError):
    code = "provider_circuit_open"
    status_code = 503


class NotConfiguredError(ConfigurationError):
    code = "not_configured"
    status_code = 503


class NotPublishedError(ConfigurationError):
    code = "not_published"
    status_code = 503


class StorageError(AppError):
    code = "storage_error"
    status_code = 503


class DatabaseError(AppError):
    code = "database_error"
    status_code = 503


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class ConflictError(AppError):
    code = "conflict"
    status_code = 409


class ValidationAppError(AppError):
    code = "validation_error"
    status_code = 422


class AgentConfigurationIncompleteError(ConfigurationError):
    code = "agent_configuration_incomplete"
    status_code = 503


class AgentInputNotSupportedError(ValidationAppError):
    code = "agent_input_not_supported"


class RouteInvalidTargetError(ValidationAppError):
    code = "route_invalid_target"


class ModelProviderError(ProviderError):
    code = "model_provider_error"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        provider: str = "",
        model: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        safe_details = {"provider": provider, "model": model, **(details or {})}
        super().__init__(message, details=safe_details)
        self.provider = provider
        self.model = model


class ProviderNotConfiguredError(ModelProviderError):
    code = "model_provider_not_configured"
    status_code = 503


class AuthenticationError(ModelProviderError):
    code = "model_authentication_error"


class RateLimitError(ModelProviderError):
    code = "model_rate_limit"
    retryable = True


class ModelTimeoutError(ModelProviderError):
    code = "model_timeout"
    status_code = 504
    retryable = True


class InvalidModelRequestError(ModelProviderError):
    code = "invalid_model_request"
    status_code = 422


class UnsupportedModalityError(InvalidModelRequestError):
    code = "unsupported_modality"


class ContextLengthExceededError(InvalidModelRequestError):
    code = "context_length_exceeded"


class StructuredOutputError(ModelProviderError):
    code = "structured_output_error"
    status_code = 422


class ImageProcessingError(InvalidModelRequestError):
    code = "image_processing_error"


class ProviderUnavailableError(ModelProviderError):
    code = "model_provider_unavailable"
    status_code = 503
    retryable = True
