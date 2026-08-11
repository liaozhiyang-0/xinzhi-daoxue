"""Run a provider-free, fail-closed Runtime release preflight.

The command only reads serialized structural and semantic evidence.  It
delegates structural evaluation and semantic binding to
``RuntimeCanaryReleaseRegistry`` and never constructs a Provider, tool, or
model client.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402
from app.services.runtime_canary_release import (  # noqa: E402
    RuntimeCanaryReleaseRegistry,
)


def _configured_or_explicit(explicit: str | None, configured: str) -> str:
    """Prefer an explicit path, while retaining the Settings contract."""

    return explicit.strip() if explicit and explicit.strip() else configured.strip()


def _normalized_expected_version(value: str | None) -> str | None:
    """Normalize an operator-supplied version without trusting blank input."""

    normalized = value.strip() if value else ""
    return normalized or None


def _artifact_spec(agent_id: str, path_or_spec: str) -> str:
    """Convert a single CLI path into the Registry's ``AGENT_ID=PATH`` form."""

    value = path_or_spec.strip()
    if not value:
        return ""
    if "=" in value:
        configured_agent, _, configured_path = value.partition("=")
        if configured_agent.strip() and configured_path.strip():
            return value
    return f"{agent_id}={value}"


def _error_code(exc: BaseException, *, semantic: bool) -> str:
    if isinstance(exc, FileNotFoundError):
        return (
            "semantic_sidecar_file_missing"
            if semantic
            else "structural_suite_file_missing"
        )
    if isinstance(exc, IsADirectoryError):
        return (
            "semantic_sidecar_path_invalid"
            if semantic
            else "structural_suite_path_invalid"
        )
    if isinstance(exc, json.JSONDecodeError):
        return (
            "semantic_sidecar_invalid_json"
            if semantic
            else "structural_suite_invalid_json"
        )
    if isinstance(exc, ValueError):
        detail = str(exc).lower()
        if "development semantic sidecar" in detail:
            return "semantic_development_evidence_not_authorized"
        if "input hash binding mismatch" in detail:
            return "semantic_input_hash_mismatch"
        if "input hash binding missing" in detail:
            return "semantic_input_hash_missing"
        if "output hash binding mismatch" in detail:
            return "semantic_output_hash_mismatch"
        if "agent mismatch" in detail:
            return "artifact_agent_id_mismatch"
        if "version mismatch" in detail:
            return "semantic_version_mismatch"
        if "case coverage" in detail or "case_id mismatch" in detail:
            return "semantic_case_coverage_mismatch"
        if "authorized_paired" in detail or "authorized" in detail:
            return "structural_authorization_missing"
        return (
            "semantic_sidecar_binding_invalid"
            if semantic
            else "structural_suite_invalid"
        )
    return (
        "semantic_sidecar_load_failed" if semantic else "structural_suite_load_failed"
    )


def _next_steps(blocking_reasons: list[str]) -> list[str]:
    if not blocking_reasons:
        return [
            "retain the structural suite and semantic sidecar as the release record",
            "obtain the separate human release approval before changing launch mode",
        ]
    steps: list[str] = []
    if any(
        reason.startswith("structural_") or "artifact_" in reason
        for reason in blocking_reasons
    ):
        steps.append(
            "provide a complete redacted authorized_paired structural suite "
            "with matching Agent/version/plan"
        )
    if any(reason.startswith("semantic_") for reason in blocking_reasons):
        steps.append(
            "provide a redacted semantic sidecar covering every structural "
            "case_id with matching identity and versions"
        )
    if any(
        reason in {
            "release_expected_agent_version_missing",
            "release_expected_runtime_plan_version_missing",
        }
        for reason in blocking_reasons
    ):
        steps.append(
            "rerun preflight with explicit expected Agent and Runtime plan "
            "versions from the release record"
        )
    if not steps:
        steps.append(
            "inspect the blocking reason and rerun this provider-free preflight"
        )
    return steps


def _base_result(
    agent_id: str,
    *,
    suite: str,
    semantic_sidecar: str,
    expected_agent_version: str | None,
    expected_runtime_plan_version: str | None,
) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "suite": suite,
        "semantic_sidecar": semantic_sidecar or None,
        "expected_agent_version": expected_agent_version,
        "expected_runtime_plan_version": expected_runtime_plan_version,
        "provider_free": True,
        "structural_eligible": False,
        "semantic_eligible": False,
        "release_eligible": False,
        "blocking_reasons": [],
        "next_steps": [],
    }


def run_preflight(
    *,
    agent_id: str,
    suite: str | None,
    semantic_sidecar: str | None,
    expected_agent_version: str | None = None,
    expected_runtime_plan_version: str | None = None,
    settings: Settings | None = None,
) -> tuple[dict[str, Any], int]:
    """Evaluate a release candidate without any online execution."""

    effective_settings = settings or Settings()
    expected_agent_version = _normalized_expected_version(expected_agent_version)
    expected_runtime_plan_version = _normalized_expected_version(
        expected_runtime_plan_version
    )
    suite_value = _configured_or_explicit(
        suite,
        effective_settings.agent_runtime_canary_artifacts,
    )
    semantic_value = _configured_or_explicit(
        semantic_sidecar,
        effective_settings.agent_runtime_semantic_evidence,
    )
    result = _base_result(
        agent_id,
        suite=suite_value,
        semantic_sidecar=semantic_value,
        expected_agent_version=expected_agent_version,
        expected_runtime_plan_version=expected_runtime_plan_version,
    )
    blockers: list[str] = []

    # The artifact carries its own identity, but that is not enough to bind a
    # release decision to the operator's intended Agent/plan.  Keep the
    # lower-level registry backward compatible, while making this release
    # preflight fail closed unless both expected versions are explicit.
    if expected_agent_version is None:
        blockers.append("release_expected_agent_version_missing")
    if expected_runtime_plan_version is None:
        blockers.append("release_expected_runtime_plan_version_missing")

    if not agent_id.strip():
        blockers.append("agent_id_missing")
    if not suite_value:
        blockers.append("structural_suite_path_missing")
    else:
        structural_spec = _artifact_spec(agent_id, suite_value)
        try:
            structural_registry = RuntimeCanaryReleaseRegistry.from_paths(
                structural_spec
            )
            report = structural_registry.report(agent_id)
            if report is None:
                blockers.append("structural_evidence_missing")
            else:
                result["suite_id"] = report.suite_id
                result["suite_version"] = report.suite_version
                result["pair_count"] = report.pair_count
                result["agent_version"] = report.evidence.agent_version
                result["runtime_plan_version"] = report.evidence.runtime_plan_version
                structural_eligible = structural_registry.structural_eligible(
                    agent_id,
                    expected_agent_version=expected_agent_version,
                    expected_runtime_plan_version=expected_runtime_plan_version,
                )
                result["structural_eligible"] = structural_eligible
                if not structural_eligible:
                    structural_reason = structural_registry.structural_reason(
                        agent_id,
                        expected_agent_version=expected_agent_version,
                        expected_runtime_plan_version=expected_runtime_plan_version,
                    )
                    blockers.append(
                        structural_reason or "canary_provenance_incomplete"
                    )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            blockers.append(_error_code(exc, semantic=False))
            result["error_detail"] = str(exc)

    if not semantic_value:
        blockers.append("semantic_evidence_missing")
    elif suite_value:
        semantic_spec = _artifact_spec(agent_id, semantic_value)
        try:
            registry = RuntimeCanaryReleaseRegistry.from_paths(
                _artifact_spec(agent_id, suite_value),
                semantic_paths=semantic_spec,
            )
            release_eligible = registry.release_eligible(
                agent_id,
                expected_agent_version=expected_agent_version,
                expected_runtime_plan_version=expected_runtime_plan_version,
            )
            result["semantic_eligible"] = bool(
                release_eligible and result["structural_eligible"]
            )
            if not result["semantic_eligible"]:
                blockers.append(
                    registry.reason(
                        agent_id,
                        expected_agent_version=expected_agent_version,
                        expected_runtime_plan_version=expected_runtime_plan_version,
                    )
                )
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            blockers.append(_error_code(exc, semantic=True))
            result["semantic_error_detail"] = str(exc)

    result["blocking_reasons"] = list(dict.fromkeys(blockers))
    result["release_eligible"] = bool(
        result["structural_eligible"]
        and result["semantic_eligible"]
        and expected_agent_version is not None
        and expected_runtime_plan_version is not None
    )
    result["next_steps"] = _next_steps(result["blocking_reasons"])
    return result, 0 if result["release_eligible"] else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check Runtime release evidence without a Provider, tool, or model."
    )
    parser.add_argument("--agent-id", required=True)
    parser.add_argument(
        "--suite",
        help="structural suite JSON path; defaults to Settings when omitted",
    )
    parser.add_argument(
        "--semantic-sidecar",
        "--semantic",
        dest="semantic_sidecar",
        help="optional semantic evidence sidecar JSON path",
    )
    parser.add_argument(
        "--expected-agent-version",
        "--agent-version",
        dest="expected_agent_version",
        help="optional expected Agent version",
    )
    parser.add_argument(
        "--expected-runtime-plan-version",
        "--runtime-plan-version",
        dest="expected_runtime_plan_version",
        help="optional expected Runtime plan version",
    )
    return parser


def main(args: argparse.Namespace) -> int:
    result, exit_code = run_preflight(
        agent_id=args.agent_id,
        suite=args.suite,
        semantic_sidecar=args.semantic_sidecar,
        expected_agent_version=args.expected_agent_version,
        expected_runtime_plan_version=args.expected_runtime_plan_version,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main(_parser().parse_args()))
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "provider_free": True,
                    "structural_eligible": False,
                    "semantic_eligible": False,
                    "release_eligible": False,
                    "blocking_reasons": ["preflight_input_invalid"],
                    "next_steps": ["inspect the input error and rerun the preflight"],
                    "error_detail": str(exc),
                },
                ensure_ascii=False,
            )
        )
        raise SystemExit(1) from exc
