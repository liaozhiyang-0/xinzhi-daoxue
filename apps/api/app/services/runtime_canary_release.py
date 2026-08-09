"""Load provider-free canary evidence for the Runtime launch policy."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from app.runtime import (
    RuntimeCanaryReport,
    RuntimeCanarySuite,
    evaluate_runtime_canary_suite,
)


class RuntimeCanaryReleaseRegistry:
    """Map Agent IDs to release-eligible, authorized canary reports."""

    def __init__(
        self, reports: Mapping[str, RuntimeCanaryReport] | None = None
    ) -> None:
        self._reports = dict(reports or {})

    @classmethod
    def from_paths(cls, value: str) -> RuntimeCanaryReleaseRegistry:
        reports: dict[str, RuntimeCanaryReport] = {}
        for raw_item in value.split(","):
            item = raw_item.strip()
            if not item:
                continue
            agent_id, separator, raw_path = item.partition("=")
            if not separator or not agent_id.strip() or not raw_path.strip():
                raise ValueError(
                    "AGENT_RUNTIME_CANARY_ARTIFACTS entries must be AGENT_ID=PATH"
                )
            path = Path(raw_path.strip())
            payload = json.loads(path.read_text(encoding="utf-8"))
            suite = RuntimeCanarySuite.model_validate(payload)
            report = evaluate_runtime_canary_suite(suite)
            if suite.evidence.agent_id != agent_id.strip():
                raise ValueError(
                    f"Runtime canary artifact Agent mismatch for {agent_id.strip()}"
                )
            reports[agent_id.strip()] = report
        return cls(reports)

    def release_eligible(
        self,
        agent_id: str,
        *,
        expected_agent_version: str | None = None,
        expected_runtime_plan_version: str | None = None,
    ) -> bool:
        report = self._reports.get(agent_id)
        return report is not None and self._matches_expected_versions(
            report,
            expected_agent_version=expected_agent_version,
            expected_runtime_plan_version=expected_runtime_plan_version,
        )

    def report(self, agent_id: str) -> RuntimeCanaryReport | None:
        """Return the evaluated report without exposing mutable registry state."""

        return self._reports.get(agent_id)

    def reason(
        self,
        agent_id: str,
        *,
        expected_agent_version: str | None = None,
        expected_runtime_plan_version: str | None = None,
    ) -> str:
        report = self._reports.get(agent_id)
        if report is None:
            return "canary_release_evidence_missing"
        if not report.canary_eligible:
            return "canary_structural_gate_failed"
        if not report.evidence.release_ready:
            return "canary_authorized_evidence_missing"
        if expected_agent_version and (
            report.evidence.agent_version != expected_agent_version
        ):
            return "canary_artifact_agent_version_mismatch"
        if expected_runtime_plan_version and (
            report.evidence.runtime_plan_version
            != expected_runtime_plan_version
        ):
            return "canary_artifact_runtime_plan_version_mismatch"
        if report.release_failed_checks:
            return "canary_provenance_incomplete"
        return "canary_release_evidence_approved"

    @staticmethod
    def _matches_expected_versions(
        report: RuntimeCanaryReport,
        *,
        expected_agent_version: str | None,
        expected_runtime_plan_version: str | None,
    ) -> bool:
        if not report.release_eligible:
            return False
        if expected_agent_version and (
            report.evidence.agent_version != expected_agent_version
        ):
            return False
        if expected_runtime_plan_version and (
            report.evidence.runtime_plan_version
            != expected_runtime_plan_version
        ):
            return False
        return True
