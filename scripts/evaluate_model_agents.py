from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.agents.internal import InternalAgentHub  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.errors import ModelProviderError  # noqa: E402
from app.core.redaction import redact_sensitive_text  # noqa: E402
from app.observability import ModelTracer  # noqa: E402
from app.providers.llm import (  # noqa: E402
    DashScopeQwenProvider,
    IflytekSparkProvider,
)
from app.services.model_registry import ModelRegistry  # noqa: E402
from app.services.model_service import ModelService  # noqa: E402

DEFAULT_CASES = ROOT / "evaluation" / "model_agents" / "cases.yaml"
REPORT_ROOT = ROOT / "local_storage" / "evaluations"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="内部模型Agent批量真实评测")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--agent", action="append", default=[])
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-total-tokens", type=int, default=5000)
    parser.add_argument("--max-output-tokens", type=int, default=512)
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("评测文件必须包含cases列表")
    cases = payload["cases"]
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in cases:
        if not isinstance(item, dict):
            raise ValueError("每个评测案例必须是对象")
        case_id = str(item.get("case_id", ""))
        if not case_id or case_id in seen:
            raise ValueError(f"评测case_id为空或重复: {case_id}")
        seen.add(case_id)
        result.append(item)
    return result


async def run(args: argparse.Namespace) -> int:
    settings = Settings(model_max_retries=0)
    registry = ModelRegistry(settings)
    spark = IflytekSparkProvider(settings)
    qwen = DashScopeQwenProvider(settings)
    service = ModelService(
        settings,
        registry,
        {"iflytek_spark": spark, "dashscope": qwen},
        ModelTracer(max_records=1000),
    )
    hub = InternalAgentHub(service)
    cases = load_cases(args.cases)
    selected = set(args.agent)
    if selected:
        cases = [item for item in cases if item["agent_id"] in selected]
    selected_cases = set(args.case)
    if selected_cases:
        cases = [item for item in cases if item["case_id"] in selected_cases]
    if args.dry_run:
        print(
            json.dumps(
                {
                    "valid": not registry.errors,
                    "cases": len(cases),
                    "agents": sorted({item["agent_id"] for item in cases}),
                    "registry_errors": registry.errors,
                    "sends_api_requests": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        await service.aclose()
        return 0 if not registry.errors and cases else 1
    required_providers = {
        registry.get_model(registry.get_route(item.task_type).primary).provider
        for item in hub.definitions
        if any(case["agent_id"] == item.agent_id for case in cases)
    }
    missing = [
        name
        for name in sorted(required_providers)
        if not service.providers[name].configured
    ]
    if missing:
        print(f"配置不完整: {', '.join(missing)}；请检查.env中的API Key")
        await service.aclose()
        return 2

    report: dict[str, Any] = {
        "started_at": datetime.now(UTC).isoformat(),
        "case_file": str(args.cases.resolve()),
        "token_budget": args.max_total_tokens,
        "results": [],
    }
    total_tokens = 0
    try:
        for case in cases:
            if total_tokens >= args.max_total_tokens:
                report["results"].append(
                    {
                        "case_id": case["case_id"],
                        "agent_id": case["agent_id"],
                        "status": "skipped_budget",
                    }
                )
                continue
            max_tokens = min(
                int(case.get("max_tokens", args.max_output_tokens)),
                args.max_output_tokens,
                max(16, args.max_total_tokens - total_tokens),
            )
            try:
                result = await hub.run_text(
                    str(case["agent_id"]),
                    input_text=str(case["input"]),
                    request_id=f"eval_{case['case_id']}",
                    max_tokens=max_tokens,
                )
                passed, failures = validate_result(result.structured_result, case)
                used = result.total_tokens or (
                    (result.prompt_tokens or 0) + (result.completion_tokens or 0)
                )
                total_tokens += used
                report["results"].append(
                    {
                        "case_id": case["case_id"],
                        "agent_id": case["agent_id"],
                        "status": "passed" if passed else "quality_failed",
                        "failures": failures,
                        "provider": result.provider,
                        "model": result.model,
                        "elapsed_ms": result.elapsed_ms,
                        "prompt_tokens": result.prompt_tokens,
                        "completion_tokens": result.completion_tokens,
                        "total_tokens": used,
                        "provider_request_id": result.provider_request_id,
                        "output_fields": sorted(result.structured_result),
                    }
                )
            except Exception as exc:
                details = exc.details if isinstance(exc, ModelProviderError) else {}
                usage = details.get("usage", {})
                if not isinstance(usage, dict):
                    usage = {}
                used = int(
                    usage.get("total_tokens")
                    or (
                        int(usage.get("prompt_tokens") or 0)
                        + int(usage.get("completion_tokens") or 0)
                    )
                )
                total_tokens += used
                report["results"].append(
                    {
                        "case_id": case["case_id"],
                        "agent_id": case["agent_id"],
                        "status": "error",
                        "error_type": type(exc).__name__,
                        "error_message": redact_sensitive_text(exc, max_length=160),
                        "provider": details.get("provider"),
                        "model": details.get("model"),
                        "elapsed_ms": details.get("elapsed_ms"),
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "total_tokens": used or None,
                        "provider_request_id": details.get("provider_request_id"),
                        "validation_fields": details.get("validation_fields", []),
                    }
                )
    finally:
        await service.aclose()

    results = report["results"]
    report["completed_at"] = datetime.now(UTC).isoformat()
    report["summary"] = {
        "cases": len(results),
        "passed": sum(item["status"] == "passed" for item in results),
        "quality_failed": sum(item["status"] == "quality_failed" for item in results),
        "errors": sum(item["status"] == "error" for item in results),
        "skipped_budget": sum(item["status"] == "skipped_budget" for item in results),
        "total_tokens": total_tokens,
    }
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORT_ROOT / f"model_agents_{stamp}.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print_summary(report, report_path)
    return 0 if report["summary"]["passed"] == len(results) else 1


def validate_result(
    value: dict[str, Any], case: dict[str, Any]
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    expected = case.get("expect", {})
    if isinstance(expected, dict):
        for path, expected_value in expected.items():
            actual = get_path(value, str(path))
            if actual != expected_value:
                failures.append(
                    f"{path}: expected={expected_value!r}, actual={actual!r}"
                )
    expected_one_of = case.get("expect_one_of", {})
    if isinstance(expected_one_of, dict):
        for path, choices in expected_one_of.items():
            actual = get_path(value, str(path))
            if not isinstance(choices, list) or actual not in choices:
                failures.append(f"{path}: actual={actual!r} not in {choices!r}")
    non_empty = case.get("expect_non_empty", [])
    if isinstance(non_empty, list):
        for path in non_empty:
            if get_path(value, str(path)) in (None, "", [], {}):
                failures.append(f"{path}: empty")
    return not failures, failures


def get_path(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def print_summary(report: dict[str, Any], report_path: Path) -> None:
    print("Case | Agent | Status | Model | Tokens | Elapsed")
    print("-----+-------+--------+-------+--------+--------")
    for item in report["results"]:
        print(
            f"{item['case_id']} | {item['agent_id']} | {item['status']} | "
            f"{item.get('model', '-')} | {item.get('total_tokens', '-')} | "
            f"{item.get('elapsed_ms', '-')}ms"
        )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report={report_path}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
