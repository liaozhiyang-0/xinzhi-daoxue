from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.config import PROJECT_ROOT, Settings

ProviderName = Literal["iflytek_spark", "dashscope"]
Modality = Literal["text", "image", "video"]


class ModelDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str
    provider: ProviderName
    model: str
    enabled_env: str
    modalities: list[Modality]
    supports_streaming: bool = False
    supports_tools: bool = False
    supports_json: bool = False
    default_options: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = Field(gt=0, le=600)

    @field_validator("modalities")
    @classmethod
    def modalities_must_be_unique(cls, value: list[Modality]) -> list[Modality]:
        if not value or len(value) != len(set(value)):
            raise ValueError("modalities必须非空且不能重复")
        return value

    @field_validator("default_options")
    @classmethod
    def validate_default_options(cls, value: dict[str, Any]) -> dict[str, Any]:
        max_tokens = value.get("max_tokens")
        if max_tokens is not None and (
            not isinstance(max_tokens, int) or max_tokens < 1
        ):
            raise ValueError("default_options.max_tokens必须为正整数")
        return value


class ModelRoute(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: str
    primary: str
    fallback: str | None = None
    verifier: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ModelRegistry:
    """Validated model catalog; invalid entries are isolated and reported."""

    def __init__(
        self,
        settings: Settings,
        *,
        models_path: Path | None = None,
        routes_path: Path | None = None,
    ) -> None:
        self.settings = settings
        self.models_path = models_path or PROJECT_ROOT / "config" / "models.yaml"
        self.routes_path = routes_path or PROJECT_ROOT / "config" / "model_routes.yaml"
        self.errors: list[str] = []
        self._models = self._load_models()
        self._routes = self._load_routes()

    @property
    def models(self) -> dict[str, ModelDefinition]:
        return dict(self._models)

    @property
    def routes(self) -> dict[str, ModelRoute]:
        return dict(self._routes)

    def get_model(self, alias: str) -> ModelDefinition:
        try:
            return self._models[alias]
        except KeyError as exc:
            raise KeyError(f"模型别名未注册: {alias}") from exc

    def get_route(self, task_type: str) -> ModelRoute:
        try:
            return self._routes[task_type]
        except KeyError as exc:
            raise KeyError(f"模型任务路由未注册: {task_type}") from exc

    def enabled(self, definition: ModelDefinition) -> bool:
        value = getattr(self.settings, definition.enabled_env.lower(), None)
        return bool(value)

    def _read_yaml(self, path: Path, root_key: str) -> dict[str, Any]:
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            self.errors.append(f"{path.name}: {type(exc).__name__}")
            return {}
        if not isinstance(payload, dict):
            self.errors.append(f"{path.name}: 顶层必须是对象")
            return {}
        value = payload.get(root_key)
        if not isinstance(value, dict):
            self.errors.append(f"{path.name}: 缺少对象字段 {root_key}")
            return {}
        return value

    def _load_models(self) -> dict[str, ModelDefinition]:
        result: dict[str, ModelDefinition] = {}
        for alias, value in self._read_yaml(self.models_path, "models").items():
            if not isinstance(alias, str) or not isinstance(value, dict):
                self.errors.append(f"models.yaml: 无效模型条目 {alias!r}")
                continue
            try:
                result[alias] = ModelDefinition(alias=alias, **value)
            except (TypeError, ValidationError) as exc:
                self.errors.append(f"models.yaml:{alias}: {exc}")
        return result

    def _load_routes(self) -> dict[str, ModelRoute]:
        result: dict[str, ModelRoute] = {}
        for task_type, value in self._read_yaml(self.routes_path, "routes").items():
            if not isinstance(task_type, str) or not isinstance(value, dict):
                self.errors.append(f"model_routes.yaml: 无效路由条目 {task_type!r}")
                continue
            try:
                route = ModelRoute(task_type=task_type, **value)
            except (TypeError, ValidationError) as exc:
                self.errors.append(f"model_routes.yaml:{task_type}: {exc}")
                continue
            aliases = [route.primary, route.fallback, route.verifier]
            missing = [item for item in aliases if item and item not in self._models]
            if missing:
                self.errors.append(
                    f"model_routes.yaml:{task_type}: 未注册模型 {', '.join(missing)}"
                )
                continue
            result[task_type] = route
        return result
