from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.contracts.external_retrieval import ExternalRetrievalPolicy
from app.core.config import PROJECT_ROOT, Settings
from app.core.internal_workflows import internal_workflow_models_configured

VALID_PARSERS = {
    "json",
    "fixed_line_fields",
    "plain_text",
    "json_or_fixed_line",
    "custom_registered_parser",
}
VALID_RETRIEVAL_MODES = {
    "no_rag",
    "text_rag",
    "multimodal_rag",
    "method_only_rag",
    "data_context_only",
    "external_source_context",
}
VALID_FALLBACK_HANDLERS = {
    "local_retrieval_answer",
    "static_template",
    "planned_response",
    "manual_review",
    "no_fallback",
}
VALID_INPUT_TRANSFORMS = {
    "string",
    "json_string",
    "bool_string",
    "number_string",
    "truncate",
    "default",
    "join_lines",
    "retrieval_context",
}
VALID_OUTPUT_FIELD_PARSERS = {
    "identity",
    "json_string",
    "list_json",
    "float",
    "float_string",
}
VALID_INPUT_MODES = {
    "text",
    "single_image",
    "text_and_single_image",
    "multi_image",
    "text_and_multi_image",
}
VALID_EXECUTION_MODES = {"local", "xingchen", "hybrid", "disabled"}
VALID_VALIDATORS = {
    "generic",
    "learn_qa",
    "solver_ct",
    "lesson_prep",
    "assignment_review",
    "academic_writing",
    "data_analysis",
    "router_only",
}
VALID_RENDERERS = {
    "generic",
    "learn_qa",
    "solver_ct",
    "lesson_prep",
    "assignment_review",
    "academic_writing",
    "data_analysis",
    "router_only",
}
VALID_OUTPUT_ROOTS = {
    "status",
    "answer",
    "answer_text",
    "business_data",
    "confidence",
    "warnings",
    "assumptions",
    "remaining_risks",
    "source_references",
    "key_points",
    "key_equations",
    "course_id",
    "intent",
    "parse_status",
    "request_id",
}
FLOW_ENV_RE = re.compile(r"^XINGCHEN_[A-Z0-9_]+_FLOW_ID$")
_DEPRECATION_WARNED = False


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate mapping keys before data is lost."""


def _construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate Agent registry key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    type: str
    flow_env_key: str | None
    timeout_seconds: float
    max_retries: int
    parser_type: str
    parser_options: dict[str, Any]
    output_schema: str


@dataclass(frozen=True, slots=True)
class AgentCapabilities:
    user_roles: frozenset[str]
    courses: frozenset[str]
    intents: frozenset[str]
    input_modes: frozenset[str]
    supports_session_context: bool
    supports_images: bool


@dataclass(frozen=True, slots=True)
class InputContract:
    required: frozenset[str]
    optional: frozenset[str]


@dataclass(frozen=True, slots=True)
class InputMappingRule:
    parameter_name: str
    source: str
    transform: str
    max_length: int | None
    default: Any = ""


@dataclass(frozen=True, slots=True)
class OutputMappingRule:
    source: str
    target: str
    parser: str


@dataclass(frozen=True, slots=True)
class RetrievalPolicyDefinition:
    enabled: bool
    policy_name: str
    mode: str
    course_required: bool
    text_top_k: int
    image_top_k: int
    reranker_mode: str
    allowed_content_types: frozenset[str]
    context_max_chars: int
    generation_injection: bool

    @property
    def interaction_mode(self) -> str:
        if not self.enabled or self.mode == "no_rag":
            return "no_rag"
        if self.mode == "method_only_rag":
            return "method_reference"
        if self.mode == "data_context_only":
            return "data_context_only"
        if self.mode == "external_source_context":
            return "user_sources_only"
        if self.generation_injection:
            return "grounded_generation"
        return "reference_only"


@dataclass(frozen=True, slots=True)
class FallbackDefinition:
    type: str
    handler: str
    trigger_on: frozenset[str]
    target_agent_id: str | None
    instruction_prefix: str


@dataclass(frozen=True, slots=True)
class DevelopmentDefinition:
    mock_enabled: bool
    mock_profile: str
    mock_latency_ms: int


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    agent_id: str
    scene: str
    provider: str
    enabled: bool
    publication_status: str
    mode: str
    flow_env: str | None
    course_ids: frozenset[str]
    supports: frozenset[str]
    fallback_agent_id: str | None
    input_mapping: dict[str, str]
    output_mapping: dict[str, str]
    knowledge_top_k: int
    knowledge_context_mode: str
    knowledge_content_types: frozenset[str]
    display_name: str
    version: str
    schema_version: str
    provider_config: ProviderDefinition
    capabilities: AgentCapabilities
    input_contract: InputContract
    input_rules: tuple[InputMappingRule, ...]
    output_rules: tuple[OutputMappingRule, ...]
    retrieval_policy: RetrievalPolicyDefinition
    external_retrieval: ExternalRetrievalPolicy
    fallback: FallbackDefinition
    development: DevelopmentDefinition
    route_when_unconfigured: bool
    validator_type: str
    renderer_type: str
    execution_mode: str
    local_handler: str
    priority: int
    task_families: frozenset[str]
    graph_name: str
    required_capabilities: frozenset[str]

    @property
    def timeout_seconds(self) -> float:
        return self.provider_config.timeout_seconds


@dataclass(frozen=True, slots=True)
class RoutingRule:
    course_ids: frozenset[str]
    intents: frozenset[str]
    agent_id: str
    scene: str
    retrieval_required: bool
    provider_required: bool


class AgentRegistry:
    """Validated, read-only view of all local and cloud workflow definitions."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PROJECT_ROOT / "agent_configs" / "registry.yaml"
        payload = self._load_payload(self.path)
        self._scenes = self._load_scenes(payload.get("scenes"))
        self._agents = self._load_agents(payload.get("agents"))
        self._validate_fallbacks()
        self._routing_rules = self._load_rules(payload.get("routing"))

    @staticmethod
    def _load_payload(path: Path) -> dict[str, Any]:
        try:
            payload = yaml.load(
                path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader
            )
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            raise ValueError(f"无法读取 Agent 注册表: {path}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Agent 注册表顶层必须是映射")
        return payload

    @staticmethod
    def _load_scenes(value: Any) -> dict[str, dict[str, Any]]:
        if not isinstance(value, dict) or not value:
            raise ValueError("Agent 注册表必须包含非空 scenes")
        return {
            str(scene): dict(raw)
            for scene, raw in value.items()
            if isinstance(raw, dict)
        }

    @staticmethod
    def _load_agents(value: Any) -> dict[str, AgentDefinition]:
        global _DEPRECATION_WARNED
        if not isinstance(value, dict) or not value:
            raise ValueError("Agent 注册表必须包含非空 agents")
        agents: dict[str, AgentDefinition] = {}
        deprecated_agents: list[str] = []
        for agent_id, raw in value.items():
            if not isinstance(agent_id, str) or not isinstance(raw, dict):
                raise ValueError("agents 条目格式无效")
            mapping = raw.get("input_mapping", {})
            output_mapping = raw.get("output_mapping", {})
            if not isinstance(mapping, dict):
                raise ValueError(f"Agent input_mapping 必须是映射: {agent_id}")
            if not isinstance(output_mapping, dict):
                raise ValueError(f"Agent output_mapping 必须是映射: {agent_id}")
            provider_raw = raw.get("provider", "local")
            if isinstance(provider_raw, str) and any(
                key in raw
                for key in (
                    "flow_env",
                    "knowledge_top_k",
                    "knowledge_context_mode",
                )
            ):
                deprecated_agents.append(agent_id)
            provider_payload = provider_raw if isinstance(provider_raw, dict) else {}
            provider_type = str(
                provider_payload.get(
                    "type", provider_raw if isinstance(provider_raw, str) else "local"
                )
            )
            flow_env = (
                str(provider_payload.get("flow_env_key", raw.get("flow_env", "")))
                or None
            )
            parser_type = str(provider_payload.get("parser_type", "plain_text"))
            parser_options = provider_payload.get("parser_options", {})
            if not isinstance(parser_options, dict):
                raise ValueError(f"Agent parser_options 必须是映射: {agent_id}")
            input_rules, legacy_input_mapping = AgentRegistry._input_rules(
                agent_id, mapping
            )
            output_rules, legacy_output_mapping = AgentRegistry._output_rules(
                agent_id, output_mapping
            )
            capabilities_raw = raw.get("capabilities", {})
            if not isinstance(capabilities_raw, dict):
                raise ValueError(f"Agent capabilities 必须是映射: {agent_id}")
            courses = frozenset(
                str(item).upper()
                for item in (
                    capabilities_raw.get("courses", raw.get("course_ids", [])) or []
                )
            )
            input_modes = frozenset(
                str(item)
                for item in (
                    capabilities_raw.get("input_modes", raw.get("supports", ["text"]))
                    or []
                )
            )
            contract_raw = raw.get("input_contract", {})
            if not isinstance(contract_raw, dict):
                raise ValueError(f"Agent input_contract 必须是映射: {agent_id}")
            retrieval_raw = raw.get("retrieval_policy", {})
            if not isinstance(retrieval_raw, dict):
                raise ValueError(f"Agent retrieval_policy 必须是映射: {agent_id}")
            external_raw = retrieval_raw.get("external", {})
            if not isinstance(external_raw, dict):
                raise ValueError(
                    f"Agent retrieval_policy.external 必须是映射: {agent_id}"
                )
            legacy_top_k = max(0, int(raw.get("knowledge_top_k", 0)))
            legacy_mode = str(raw.get("knowledge_context_mode", "none"))
            retrieval_enabled = bool(retrieval_raw.get("enabled", legacy_top_k > 0))
            retrieval_mode = str(
                retrieval_raw.get(
                    "mode",
                    "method_only_rag"
                    if legacy_mode == "solver_methods"
                    else "text_rag"
                    if retrieval_enabled
                    else "no_rag",
                )
            )
            reranker_raw = retrieval_raw.get("reranker", "off")
            if isinstance(reranker_raw, bool):
                reranker_mode = "on" if reranker_raw else "off"
            else:
                reranker_mode = str(reranker_raw).lower()
            fallback_raw = raw.get("fallback", {})
            if not isinstance(fallback_raw, dict):
                raise ValueError(f"Agent fallback 必须是映射: {agent_id}")
            development_raw = raw.get("development", {})
            if not isinstance(development_raw, dict):
                raise ValueError(f"Agent development 必须是映射: {agent_id}")
            fallback_agent_id = (
                str(
                    fallback_raw.get(
                        "target_agent_id", raw.get("fallback_agent_id", "")
                    )
                )
                or None
            )
            fallback_handler = str(
                fallback_raw.get(
                    "handler",
                    "local_retrieval_answer" if fallback_agent_id else "no_fallback",
                )
            )
            definition = AgentDefinition(
                agent_id=agent_id,
                scene=str(raw.get("scene", "learning")),
                provider=provider_type,
                enabled=bool(raw.get("enabled", True)),
                publication_status=str(raw.get("publication_status", "local")),
                mode=str(raw.get("mode", "provider")),
                flow_env=flow_env,
                course_ids=courses,
                supports=input_modes,
                fallback_agent_id=fallback_agent_id,
                input_mapping=legacy_input_mapping,
                output_mapping=legacy_output_mapping,
                knowledge_top_k=int(retrieval_raw.get("text_top_k", legacy_top_k)),
                knowledge_context_mode=legacy_mode,
                knowledge_content_types=frozenset(
                    str(item)
                    for item in (
                        retrieval_raw.get(
                            "allowed_content_types",
                            raw.get("knowledge_content_types", []),
                        )
                        or []
                    )
                ),
                display_name=str(raw.get("display_name", agent_id)),
                version=str(raw.get("version", "1.0")),
                schema_version=str(raw.get("schema_version", "1")),
                provider_config=ProviderDefinition(
                    type=provider_type,
                    flow_env_key=flow_env,
                    timeout_seconds=float(provider_payload.get("timeout_seconds", 45)),
                    max_retries=max(
                        0, min(1, int(provider_payload.get("max_retries", 0)))
                    ),
                    parser_type=parser_type,
                    parser_options={str(k): v for k, v in parser_options.items()},
                    output_schema=str(
                        provider_payload.get("output_schema", "generic_v1")
                    ),
                ),
                capabilities=AgentCapabilities(
                    user_roles=frozenset(
                        str(item) for item in capabilities_raw.get("user_roles", [])
                    ),
                    courses=courses,
                    intents=frozenset(
                        str(item) for item in capabilities_raw.get("intents", [])
                    ),
                    input_modes=input_modes,
                    supports_session_context=bool(
                        capabilities_raw.get("supports_session_context", False)
                    ),
                    supports_images=bool(
                        capabilities_raw.get(
                            "supports_images",
                            any("image" in item for item in input_modes),
                        )
                    ),
                ),
                input_contract=InputContract(
                    required=frozenset(
                        str(item) for item in contract_raw.get("required", [])
                    ),
                    optional=frozenset(
                        str(item) for item in contract_raw.get("optional", [])
                    ),
                ),
                input_rules=input_rules,
                output_rules=output_rules,
                retrieval_policy=RetrievalPolicyDefinition(
                    enabled=retrieval_enabled,
                    policy_name=str(retrieval_raw.get("policy_name", legacy_mode)),
                    mode=retrieval_mode,
                    course_required=bool(
                        retrieval_raw.get("course_required", retrieval_enabled)
                    ),
                    text_top_k=max(
                        0, int(retrieval_raw.get("text_top_k", legacy_top_k))
                    ),
                    image_top_k=max(0, int(retrieval_raw.get("image_top_k", 0))),
                    reranker_mode=reranker_mode,
                    allowed_content_types=frozenset(
                        str(item)
                        for item in (
                            retrieval_raw.get(
                                "allowed_content_types",
                                raw.get("knowledge_content_types", []),
                            )
                            or []
                        )
                    ),
                    context_max_chars=max(
                        0, int(retrieval_raw.get("context_max_chars", 6000))
                    ),
                    generation_injection=bool(
                        retrieval_raw.get(
                            "generation_injection", legacy_mode == "learning_qa"
                        )
                    ),
                ),
                external_retrieval=ExternalRetrievalPolicy(
                    enabled=bool(external_raw.get("enabled", False)),
                    source_scopes=list(external_raw.get("source_scopes", [])),
                    providers=list(external_raw.get("providers", [])),
                    max_results=int(external_raw.get("max_results", 8)),
                    max_fetches=int(external_raw.get("max_fetches", 4)),
                    max_iterations=int(external_raw.get("max_iterations", 2)),
                    freshness_days=external_raw.get("freshness_days"),
                    allow_full_text=bool(external_raw.get("allow_full_text", False)),
                    require_citations=bool(external_raw.get("require_citations", True)),
                    generation_injection=bool(
                        external_raw.get("generation_injection", False)
                    ),
                    timeout_seconds=float(external_raw.get("timeout_seconds", 20)),
                ),
                fallback=FallbackDefinition(
                    type=str(
                        fallback_raw.get(
                            "type", "agent" if fallback_agent_id else "none"
                        )
                    ),
                    handler=fallback_handler,
                    trigger_on=frozenset(
                        str(item)
                        for item in fallback_raw.get(
                            "trigger_on",
                            ["cloud_timeout", "cloud_http_error", "cloud_parse_error"],
                        )
                    ),
                    target_agent_id=fallback_agent_id,
                    instruction_prefix=str(fallback_raw.get("instruction_prefix", "")),
                ),
                development=DevelopmentDefinition(
                    mock_enabled=bool(development_raw.get("mock_enabled", False)),
                    mock_profile=str(development_raw.get("mock_profile", "")),
                    mock_latency_ms=max(
                        0, min(2000, int(development_raw.get("mock_latency_ms", 25)))
                    ),
                ),
                route_when_unconfigured=bool(raw.get("route_when_unconfigured", False)),
                validator_type=str(raw.get("validator_type", "generic")),
                renderer_type=str(raw.get("renderer_type", "generic")),
                execution_mode=str(
                    raw.get(
                        "execution_mode",
                        "local"
                        if provider_type == "local"
                        else "disabled"
                        if not bool(raw.get("enabled", True))
                        else "xingchen",
                    )
                ),
                local_handler=str(raw.get("local_handler", "")),
                priority=max(0, int(raw.get("priority", 100))),
                task_families=frozenset(
                    str(item).upper() for item in raw.get("task_families", [])
                ),
                graph_name=str(raw.get("graph_name", "")),
                required_capabilities=frozenset(
                    str(item) for item in raw.get("required_capabilities", [])
                ),
            )
            AgentRegistry._validate_definition(definition)
            agents[agent_id] = definition
        if deprecated_agents and not _DEPRECATION_WARNED:
            warnings.warn(
                "deprecated Agent registry v1 fields remain in: "
                f"{', '.join(deprecated_agents)}; migrate before schema v2 removal",
                DeprecationWarning,
                stacklevel=2,
            )
            _DEPRECATION_WARNED = True
        return agents

    @staticmethod
    def _input_rules(
        agent_id: str, mapping: dict[Any, Any]
    ) -> tuple[tuple[InputMappingRule, ...], dict[str, str]]:
        rules: list[InputMappingRule] = []
        legacy: dict[str, str] = {}
        for key, value in mapping.items():
            if isinstance(value, str):
                source, parameter = str(key), value
                rule = InputMappingRule(parameter, source, "string", None, "")
            elif isinstance(value, dict):
                parameter = str(key)
                source = str(value.get("source", ""))
                if not source:
                    raise ValueError(
                        f"Agent input_mapping 缺少 source: {agent_id}.{parameter}"
                    )
                maximum = value.get("max_length")
                rule = InputMappingRule(
                    parameter,
                    source,
                    str(value.get("transform", "string")),
                    int(maximum) if maximum is not None else None,
                    value.get("default", ""),
                )
            else:
                raise ValueError(f"Agent input_mapping 条目无效: {agent_id}.{key}")
            rules.append(rule)
            legacy[rule.source] = rule.parameter_name
        return tuple(rules), legacy

    @staticmethod
    def _output_rules(
        agent_id: str, mapping: dict[Any, Any]
    ) -> tuple[tuple[OutputMappingRule, ...], dict[str, str]]:
        rules: list[OutputMappingRule] = []
        legacy: dict[str, str] = {}
        for key, value in mapping.items():
            if isinstance(value, str):
                logical, source = str(key), value
                rule = OutputMappingRule(source, logical, "identity")
                legacy[logical] = source
            elif isinstance(value, dict):
                source = str(key)
                target = str(value.get("target", source))
                rule = OutputMappingRule(
                    source, target, str(value.get("parser", "identity"))
                )
                legacy[target.rsplit(".", 1)[-1]] = source
            else:
                raise ValueError(f"Agent output_mapping 条目无效: {agent_id}.{key}")
            rules.append(rule)
        return tuple(rules), legacy

    @staticmethod
    def _validate_definition(definition: AgentDefinition) -> None:
        if definition.execution_mode not in VALID_EXECUTION_MODES:
            raise ValueError(
                f"Agent execution_mode 无效: {definition.agent_id}: "
                f"{definition.execution_mode}"
            )
        if definition.provider_config.parser_type not in VALID_PARSERS:
            raise ValueError(f"Agent parser_type 未注册: {definition.agent_id}")
        if definition.validator_type not in VALID_VALIDATORS:
            raise ValueError(f"Agent validator_type 未注册: {definition.agent_id}")
        if definition.renderer_type not in VALID_RENDERERS:
            raise ValueError(f"Agent renderer_type 未注册: {definition.agent_id}")
        if definition.retrieval_policy.mode not in VALID_RETRIEVAL_MODES:
            raise ValueError(f"Agent retrieval mode 无效: {definition.agent_id}")
        if definition.retrieval_policy.reranker_mode not in {
            "off",
            "on",
            "conditional",
        }:
            raise ValueError(f"Agent reranker 模式无效: {definition.agent_id}")
        if definition.fallback.handler not in VALID_FALLBACK_HANDLERS:
            raise ValueError(f"Agent fallback handler 未注册: {definition.agent_id}")
        unsupported_modes = definition.supports - VALID_INPUT_MODES
        if unsupported_modes:
            raise ValueError(
                f"Agent input_mode 无效: {definition.agent_id}: "
                f"{sorted(unsupported_modes)}"
            )
        for rule in definition.input_rules:
            if rule.transform not in VALID_INPUT_TRANSFORMS:
                raise ValueError(
                    f"Agent input transform 未注册: {definition.agent_id}: "
                    f"{rule.transform}"
                )
            if rule.max_length is not None and rule.max_length <= 0:
                raise ValueError(
                    f"Agent input max_length 必须为正数: {definition.agent_id}"
                )
        for output_rule in definition.output_rules:
            if output_rule.parser not in VALID_OUTPUT_FIELD_PARSERS:
                raise ValueError(
                    f"Agent output parser 未注册: {definition.agent_id}: "
                    f"{output_rule.parser}"
                )
            if output_rule.target.split(".", 1)[0] not in VALID_OUTPUT_ROOTS:
                raise ValueError(
                    f"Agent output target 无效: {definition.agent_id}: "
                    f"{output_rule.target}"
                )
        if definition.provider == "xingchen" and definition.flow_env:
            if not FLOW_ENV_RE.fullmatch(definition.flow_env):
                raise ValueError(f"Agent Flow 环境变量名称无效: {definition.agent_id}")
        if (
            definition.enabled
            and definition.provider == "xingchen"
            and definition.publication_status != "published"
        ):
            raise ValueError(
                f"启用的星辰 Agent 必须为 published: {definition.agent_id}"
            )
        mapped_sources = {item.source for item in definition.input_rules}
        missing = definition.input_contract.required - mapped_sources
        if missing:
            raise ValueError(
                f"Agent required 输入缺少映射: {definition.agent_id}: {sorted(missing)}"
            )
        if (
            definition.development.mock_enabled
            and not definition.development.mock_profile
        ):
            raise ValueError(f"Agent Mock已启用但缺少profile: {definition.agent_id}")

    def _validate_fallbacks(self) -> None:
        for agent in self._agents.values():
            if agent.scene not in self._scenes:
                raise ValueError(f"Agent 引用了未注册 scene: {agent.agent_id}")
            if agent.fallback_agent_id and agent.fallback_agent_id not in self._agents:
                raise ValueError(f"Agent fallback 未注册: {agent.agent_id}")

    def _load_rules(self, value: Any) -> tuple[RoutingRule, ...]:
        if not isinstance(value, list) or not value:
            raise ValueError("Agent 注册表必须包含非空 routing")
        rules: list[RoutingRule] = []
        for raw in value:
            if not isinstance(raw, dict):
                raise ValueError("routing 条目必须是映射")
            agent_id = str(raw.get("agent_id", ""))
            if agent_id not in self._agents:
                raise ValueError(f"routing 引用了未注册 Agent: {agent_id}")
            course_ids = frozenset(
                str(item).upper() for item in raw.get("course_ids", [])
            )
            intents = frozenset(str(item) for item in raw.get("intents", []))
            if not course_ids or not intents:
                raise ValueError("routing 条目必须包含 course_ids 和 intents")
            rules.append(
                RoutingRule(
                    course_ids=course_ids,
                    intents=intents,
                    agent_id=agent_id,
                    scene=str(raw.get("scene", "learning")),
                    retrieval_required=bool(raw.get("retrieval_required", False)),
                    provider_required=bool(raw.get("provider_required", False)),
                )
            )
        return tuple(rules)

    @property
    def routing_rules(self) -> tuple[RoutingRule, ...]:
        return self._routing_rules

    def get(self, agent_id: str) -> AgentDefinition:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise KeyError(f"未注册 Agent: {agent_id}") from exc

    def list_agents(self) -> tuple[AgentDefinition, ...]:
        return tuple(self._agents.values())

    def resolve_flow_id(self, agent_id: str, settings: Settings) -> str | None:
        return settings.resolve_flow_env(self.get(agent_id).flow_env)

    def is_runtime_available(self, agent_id: str, settings: Settings) -> bool:
        agent = self.get(agent_id)
        if not agent.enabled:
            return False
        if internal_workflow_models_configured(settings, agent_id):
            return True
        if agent.provider == "local":
            return True
        return bool(
            agent.provider == "xingchen"
            and agent.publication_status == "published"
            and settings.xingchen_enabled
            and settings.xingchen_api_key.get_secret_value()
            and settings.xingchen_api_secret.get_secret_value()
            and self.resolve_flow_id(agent_id, settings)
        )

    def is_configured(self, agent_id: str, settings: Settings) -> bool:
        agent = self.get(agent_id)
        if internal_workflow_models_configured(settings, agent_id):
            return True
        if agent.provider == "local":
            return True
        return bool(
            agent.provider == "xingchen"
            and settings.xingchen_api_key.get_secret_value()
            and settings.xingchen_api_secret.get_secret_value()
            and self.resolve_flow_id(agent_id, settings)
        )

    def resolve_fallback(self, agent_id: str) -> AgentDefinition | None:
        fallback_id = self.get(agent_id).fallback_agent_id
        return self.get(fallback_id) if fallback_id else None
