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


class XingchenConfigurationError(ConfigurationError):
    code = "agent_unavailable"
    status_code = 503


class XingchenConnectionError(ProviderError):
    code = "xingchen_connection_error"


class XingchenTimeoutError(ProviderTimeoutError):
    code = "xingchen_timeout"


class XingchenHttpError(ProviderError):
    code = "xingchen_http_error"


class XingchenResponseParseError(ProviderError):
    code = "xingchen_response_parse_error"


class RouteUnresolvedError(AppError):
    code = "route_unresolved"
    status_code = 422


class NotConfiguredError(ConfigurationError):
    code = "not_configured"
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


class ValidationAppError(AppError):
    code = "validation_error"
    status_code = 422
