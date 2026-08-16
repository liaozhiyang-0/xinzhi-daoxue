from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.agents import AgentRegistry  # noqa: E402
from app.contracts import (  # noqa: E402
    AgentRequest,
    Intent,
    RouteDecision,
    RouteStatus,
    TaskRequestContext,
)
from app.core.config import Settings  # noqa: E402
from app.services.agent_runtime import (  # noqa: E402
    AgentExecutionPlanner,
    AgentInputMapper,
)
from app.services.agent_scaffold import (  # noqa: E402
    AgentScaffoldService,
    AgentScaffoldSpec,
)


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _summary(
    registry: AgentRegistry, settings: Settings, agent_id: str
) -> dict[str, Any]:
    definition = registry.get(agent_id)
    return {
        "agent_id": definition.agent_id,
        "display_name": definition.display_name,
        "enabled": definition.enabled,
        "publication_status": definition.publication_status,
        "provider": definition.provider,
        "local_handler": definition.local_handler,
        "configured": registry.is_configured(agent_id, settings),
        "runtime_available": registry.is_runtime_available(agent_id, settings),
        "parser_type": definition.provider_config.parser_type,
        "retrieval_policy": definition.retrieval_policy.policy_name,
        "retrieval_mode": definition.retrieval_policy.mode,
        "fallback_handler": definition.fallback.handler,
        "courses": sorted(definition.course_ids),
        "intents": sorted(definition.capabilities.intents),
        "input_modes": sorted(definition.supports),
    }


def _dry_run(
    registry: AgentRegistry,
    settings: Settings,
    agent_id: str,
    *,
    question: str,
    course_id: str,
    intent: Intent,
) -> dict[str, Any]:
    definition = registry.get(agent_id)
    request = AgentRequest(
        task_id="dry_run_task",
        session_id="dry_run_session",
        user_id="dry_run_user",
        course_id=course_id.upper(),
        intent=intent,
        canonical_input={"text": question},
        options={
            "request_id": "dry_run_request",
            "retrieved_context": "[dry-run retrieval context]",
        },
    )
    decision = RouteDecision(
        agent_id=agent_id,
        scene=definition.scene,
        course_id=course_id.upper(),
        intent=intent.value,
        route_status=RouteStatus.SELECTED,
        reason="CLI dry-run",
        retrieval_required=definition.retrieval_policy.enabled,
        provider_required=False,
    )
    plan = AgentExecutionPlanner(registry, settings).build(decision, request)
    context = TaskRequestContext.from_agent_request(request, input_mode="text")
    mapped = AgentInputMapper().map(
        definition,
        context,
        retrieval_context="[dry-run retrieval context]",
    )
    return {
        **_summary(registry, settings, agent_id),
        "dry_run": True,
        "remote_provider_called": False,
        "required_inputs": sorted(definition.input_contract.required),
        "field_lengths": mapped.field_lengths,
        "mapping_preview": mapped.redacted_preview,
        "execution_plan": plan.model_dump(mode="json"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="芯智导学 Agent 契约与接入工具")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="列出 Agent 的脱敏状态")
    sub.add_parser("validate", help="加载并校验全部 AgentDefinition")
    for name in ("show", "check-runtime", "test-contract"):
        command = sub.add_parser(name)
        command.add_argument("agent_id")
    dry = sub.add_parser("dry-run")
    dry.add_argument("agent_id")
    dry.add_argument("--question", default="什么是节点电压法？")
    dry.add_argument("--course", default="CT", choices=("CT", "AE", "DE"))
    dry.add_argument(
        "--intent", default="explain_concept", choices=[item.value for item in Intent]
    )
    scaffold = sub.add_parser("scaffold", help="生成新Agent接入脚手架")
    scaffold.add_argument("agent_id")
    scaffold.add_argument("--display-name", default="新工作流")
    scaffold.add_argument("--version", default="1.0")
    scaffold.add_argument("--user-roles", default="student")
    scaffold.add_argument("--courses", default="CT,AE,DE")
    scaffold.add_argument("--intents", default="general_qa")
    scaffold.add_argument("--input-modes", default="text")
    scaffold.add_argument("--required-inputs", default="question,course_id")
    scaffold.add_argument("--optional-inputs", default="request_id")
    scaffold.add_argument("--output-fields", default="result")
    scaffold.add_argument("--parser-type", default="json")
    scaffold.add_argument("--retrieval-policy", default="no_rag")
    scaffold.add_argument("--fallback-type", default="planned_response")
    scaffold.add_argument("--mock-profile", default="generic_planned_v1")
    scaffold.add_argument(
        "--output-dir", default=str(PROJECT_ROOT / "agent_configs" / "scaffolds")
    )
    scaffold.add_argument("--dry-run", action="store_true")
    scaffold.add_argument("--force", action="store_true")
    return parser


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return ["list"]
    if value is None:
        return "null"
    return type(value).__name__


def main() -> int:
    args = build_parser().parse_args()
    try:
        registry = AgentRegistry()
        settings = Settings()
        if args.command == "scaffold":
            spec = AgentScaffoldSpec(
                agent_id=args.agent_id,
                display_name=args.display_name,
                version=args.version,
                user_roles=_csv(args.user_roles),
                courses=_csv(args.courses),
                intents=_csv(args.intents),
                input_modes=_csv(args.input_modes),
                required_inputs=_csv(args.required_inputs),
                optional_inputs=_csv(args.optional_inputs),
                output_fields=_csv(args.output_fields),
                parser_type=args.parser_type,
                retrieval_policy=args.retrieval_policy,
                fallback_type=args.fallback_type,
                mock_profile=args.mock_profile,
            )
            service = AgentScaffoldService()
            if args.dry_run:
                files = service.build(spec)
                _print(
                    {
                        "dry_run": True,
                        "agent_id": args.agent_id,
                        "files": sorted(files),
                        "schema_valid": True,
                        "remote_provider_called": False,
                    }
                )
            else:
                written = service.write(
                    spec, Path(args.output_dir), force=bool(args.force)
                )
                _print(
                    {
                        "agent_id": args.agent_id,
                        "written": [str(path) for path in written],
                        "force_used": bool(args.force),
                        "warning": (
                            "--force已明确覆盖现有脚手架文件" if args.force else ""
                        ),
                    }
                )
        elif args.command == "validate":
            _print({"valid": True, "agent_count": len(registry.list_agents())})
        elif args.command == "show":
            _print(_summary(registry, settings, args.agent_id))
        elif args.command == "check-runtime":
            item = _summary(registry, settings, args.agent_id)
            _print(
                {
                    "agent_id": args.agent_id,
                    "local_handler": item["local_handler"],
                    "configured": item["configured"],
                    "runtime_available": item["runtime_available"],
                }
            )
        elif args.command == "test-contract":
            _print(
                {
                    "valid": True,
                    "contract": _dry_run(
                        registry,
                        settings,
                        args.agent_id,
                        question="契约测试输入",
                        course_id="CT",
                        intent=Intent.EXPLAIN_CONCEPT,
                    ),
                }
            )
        else:
            _print(
                _dry_run(
                    registry,
                    settings,
                    args.agent_id,
                    question=args.question,
                    course_id=args.course,
                    intent=Intent(args.intent),
                )
            )
        return 0
    except (
        FileExistsError,
        KeyError,
        OSError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        _print({"valid": False, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
