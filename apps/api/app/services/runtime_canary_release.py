"""Load provider-free canary evidence for the Runtime launch policy."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from app.runtime import (
    RuntimeCanaryReport,
    RuntimeCanarySuite,
    evaluate_runtime_canary_suite,
)
from app.runtime.semantic_evidence import (
    RuntimeSemanticEvidence,
    payload_sha256,
    semantic_release_eligible,
)


class RuntimeCanaryReleaseRegistry:
    """Map Agent IDs to release-eligible, authorized canary reports."""

    def __init__(
        self,
        reports: Mapping[str, RuntimeCanaryReport] | None = None,
        semantic_evidence: (
            Mapping[
                str,
                RuntimeSemanticEvidence
                | Sequence[RuntimeSemanticEvidence],
            ]
            | None
        ) = None,
    ) -> None:
        self._reports = dict(reports or {})
        self._semantic_evidence = (
            None
            if semantic_evidence is None
            else {
                agent_id: (
                    (item,)
                    if isinstance(item, RuntimeSemanticEvidence)
                    else tuple(item)
                )
                for agent_id, item in semantic_evidence.items()
            }
        )

    @classmethod
    def from_paths(
        cls,
        value: str,
        *,
        semantic_paths: str | None = None,
    ) -> RuntimeCanaryReleaseRegistry:
        reports: dict[str, RuntimeCanaryReport] = {}
        suites: dict[str, RuntimeCanarySuite] = {}
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
            normalized_agent_id = agent_id.strip()
            if normalized_agent_id in reports:
                raise ValueError(
                    "duplicate Runtime canary artifact for "
                    f"{normalized_agent_id}"
                )
            reports[normalized_agent_id] = report
            suites[normalized_agent_id] = suite

        semantic_evidence = cls._load_semantic_evidence(
            semantic_paths,
            reports=reports,
            suites=suites,
        )
        return cls(reports, semantic_evidence=semantic_evidence)

    def release_eligible(
        self,
        agent_id: str,
        *,
        expected_agent_version: str | None = None,
        expected_runtime_plan_version: str | None = None,
    ) -> bool:
        if not self.structural_eligible(
            agent_id,
            expected_agent_version=expected_agent_version,
            expected_runtime_plan_version=expected_runtime_plan_version,
        ):
            return False
        report = self._reports[agent_id]
        evidence = self._semantic_evidence_for(agent_id)
        if evidence is None:
            return False
        return bool(evidence) and all(
            self._semantic_reason(agent_id, report, item) is None
            and semantic_release_eligible(report.release_eligible, item)
            for item in evidence
        )

    def structural_eligible(
        self,
        agent_id: str,
        *,
        expected_agent_version: str | None = None,
        expected_runtime_plan_version: str | None = None,
    ) -> bool:
        """Return structural/provenance eligibility without semantic promotion."""

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
        structural_reason = self.structural_reason(
            agent_id,
            expected_agent_version=expected_agent_version,
            expected_runtime_plan_version=expected_runtime_plan_version,
        )
        if structural_reason is not None:
            return structural_reason
        report = self._reports[agent_id]
        evidence = self._semantic_evidence_for(agent_id)
        if not evidence:
            return "semantic_evidence_missing"
        for item in evidence:
            semantic_reason = self._semantic_reason(agent_id, report, item)
            if semantic_reason is not None:
                return semantic_reason
        return "canary_release_evidence_approved"

    def structural_reason(
        self,
        agent_id: str,
        *,
        expected_agent_version: str | None = None,
        expected_runtime_plan_version: str | None = None,
    ) -> str | None:
        """Explain a structural eligibility failure without considering semantics."""

        report = self._reports.get(agent_id)
        if report is None:
            return "canary_release_evidence_missing"
        if not report.canary_eligible:
            return "canary_structural_gate_failed"
        if not report.evidence.release_ready:
            return "canary_authorized_evidence_missing"
        if expected_agent_version is not None and (
            report.evidence.agent_version != expected_agent_version
        ):
            return "canary_artifact_agent_version_mismatch"
        if expected_runtime_plan_version is not None and (
            report.evidence.runtime_plan_version
            != expected_runtime_plan_version
        ):
            return "canary_artifact_runtime_plan_version_mismatch"
        if report.release_failed_checks:
            return "canary_provenance_incomplete"
        return None

    @classmethod
    def _load_semantic_evidence(
        cls,
        value: str | None,
        *,
        reports: Mapping[str, RuntimeCanaryReport],
        suites: Mapping[str, RuntimeCanarySuite],
    ) -> dict[str, tuple[RuntimeSemanticEvidence, ...]] | None:
        """Load and bind semantic sidecars to structural suites when supplied.

        A caller may omit the sidecar for structural diagnostics, but the
        resulting registry is intentionally never release eligible.  This
        preserves a clear distinction between an operational canary report
        and a promotion decision.
        """

        if value is None or not value.strip():
            return None

        evidence_by_agent: dict[str, tuple[RuntimeSemanticEvidence, ...]] = {}
        for raw_item in value.split(","):
            item = raw_item.strip()
            if not item:
                continue
            agent_id, separator, raw_path = item.partition("=")
            normalized_agent_id = agent_id.strip()
            if (
                not separator
                or not normalized_agent_id
                or not raw_path.strip()
            ):
                raise ValueError(
                    "AGENT_RUNTIME_SEMANTIC_EVIDENCE entries must be "
                    "AGENT_ID=PATH"
                )
            if normalized_agent_id in evidence_by_agent:
                raise ValueError(
                    "duplicate Runtime semantic evidence for "
                    f"{normalized_agent_id}"
                )

            report = reports.get(normalized_agent_id)
            suite = suites.get(normalized_agent_id)
            if report is None or suite is None:
                raise ValueError(
                    "Runtime semantic evidence Agent mismatch for "
                    f"{normalized_agent_id}"
                )

            path = Path(raw_path.strip())
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                if payload.get("schema_version") == (
                    "learning_runtime_semantic_sidecar.v1"
                ):
                    raise ValueError(
                        "LearningLoop development semantic sidecar is not an "
                        "authorized Runtime semantic sidecar"
                    )
                evidence_fields = {
                    "schema_version",
                    "suite_id",
                    "case_id",
                    "agent_id",
                    "agent_version",
                    "runtime_plan_version",
                }
                if not evidence_fields.issubset(payload):
                    raise ValueError(
                        "Runtime semantic evidence sidecar must contain one "
                        "evidence object or an array of evidence objects; "
                        "received a case-keyed judgement template or other "
                        "non-sidecar mapping"
                    )
            raw_evidence = payload if isinstance(payload, list) else [payload]
            if not raw_evidence or not all(
                isinstance(item, dict) for item in raw_evidence
            ):
                raise ValueError(
                    "Runtime semantic evidence sidecar must be an object "
                    "or an array of objects"
                )
            evidence_items = tuple(
                RuntimeSemanticEvidence.model_validate(item)
                for item in raw_evidence
            )
            if not report.evidence.release_ready:
                raise ValueError(
                    "Runtime semantic evidence requires an authorized, "
                    "redacted structural suite for "
                    f"{normalized_agent_id}"
                )
            for evidence in evidence_items:
                cls._validate_semantic_binding(
                    normalized_agent_id,
                    evidence,
                    report=report,
                    suite=suite,
                )
                pair = next(
                    pair
                    for pair in suite.pairs
                    if pair.case_id == evidence.case_id
                )
                if pair.input_sha256 is None:
                    raise ValueError(
                        "Runtime semantic evidence input hash binding missing "
                        f"for {normalized_agent_id}/{evidence.case_id}"
                    )
                if evidence.input_sha256 != pair.input_sha256:
                    raise ValueError(
                        "Runtime semantic evidence input hash binding "
                        "mismatch for "
                        f"{normalized_agent_id}/{evidence.case_id}"
                    )
                expected_output_hashes = {
                    "legacy_output_sha256": payload_sha256(
                        pair.legacy_payload
                    ),
                    "runtime_output_sha256": payload_sha256(
                        pair.runtime_payload
                    ),
                }
                mismatched_hashes = [
                    field
                    for field, expected in expected_output_hashes.items()
                    if getattr(evidence, field) != expected
                ]
                if mismatched_hashes:
                    raise ValueError(
                        "Runtime semantic evidence output hash binding "
                        "mismatch for "
                        f"{normalized_agent_id}/{evidence.case_id}: "
                        + ", ".join(mismatched_hashes)
                    )
            expected_case_ids = {pair.case_id for pair in suite.pairs}
            actual_case_ids = [item.case_id for item in evidence_items]
            if set(actual_case_ids) != expected_case_ids or len(
                actual_case_ids
            ) != len(expected_case_ids):
                raise ValueError(
                    "Runtime semantic evidence case coverage incomplete for "
                    f"{normalized_agent_id}"
                )
            evidence_by_agent[normalized_agent_id] = evidence_items
        return evidence_by_agent

    @staticmethod
    def _validate_semantic_binding(
        agent_id: str,
        evidence: RuntimeSemanticEvidence,
        *,
        report: RuntimeCanaryReport,
        suite: RuntimeCanarySuite,
    ) -> None:
        """Reject sidecars that belong to another Agent or structural case."""

        if (
            evidence.agent_id != agent_id
            or evidence.agent_id != report.evidence.agent_id
        ):
            raise ValueError(
                "Runtime semantic evidence agent_id mismatch for "
                f"{agent_id}"
            )
        if evidence.agent_version != report.evidence.agent_version:
            raise ValueError(
                "Runtime semantic evidence agent_version mismatch for "
                f"{agent_id}"
            )
        if (
            evidence.runtime_plan_version
            != report.evidence.runtime_plan_version
        ):
            raise ValueError(
                "Runtime semantic evidence runtime_plan_version mismatch for "
                f"{agent_id}"
            )
        if (
            evidence.suite_id != suite.suite_id
            or evidence.suite_id != report.suite_id
        ):
            raise ValueError(
                "Runtime semantic evidence suite_id mismatch for "
                f"{agent_id}: expected={suite.suite_id}:actual={evidence.suite_id}"
            )
        if evidence.case_id not in {pair.case_id for pair in suite.pairs}:
            raise ValueError(
                "Runtime semantic evidence case_id mismatch for "
                f"{agent_id}"
            )
        if evidence.redaction_status != "redacted":
            raise ValueError(
                "Runtime semantic evidence redaction_status must be redacted "
                f"for {agent_id}"
            )
        if not evidence.authorization_ref.strip():
            raise ValueError(
                "Runtime semantic evidence authorization_ref is required "
                f"for {agent_id}"
            )

    def _semantic_evidence_for(
        self,
        agent_id: str,
    ) -> tuple[RuntimeSemanticEvidence, ...] | None:
        if self._semantic_evidence is None:
            return None
        return self._semantic_evidence.get(agent_id)

    @staticmethod
    def _semantic_reason(
        agent_id: str,
        report: RuntimeCanaryReport,
        evidence: RuntimeSemanticEvidence,
    ) -> str | None:
        if (
            evidence.agent_id != agent_id
            or evidence.agent_id != report.evidence.agent_id
        ):
            return "semantic_evidence_identity_mismatch"
        if evidence.suite_id != report.suite_id:
            return "semantic_evidence_suite_id_mismatch"
        case_ids = {result.case_id for result in report.results}
        if case_ids and evidence.case_id not in case_ids:
            return "semantic_evidence_case_id_mismatch"
        if evidence.agent_version != report.evidence.agent_version:
            return "semantic_evidence_agent_version_mismatch"
        if evidence.runtime_plan_version != report.evidence.runtime_plan_version:
            return "semantic_evidence_runtime_plan_version_mismatch"
        if evidence.redaction_status != "redacted":
            return "semantic_redaction_status_invalid"
        if not evidence.authorization_ref.strip():
            return "semantic_authorization_ref_missing"
        if evidence.judge_type == "model":
            return "semantic_judge_not_independent"
        if evidence.decision != "pass":
            return "semantic_decision_not_pass"
        return None

    @staticmethod
    def _matches_expected_versions(
        report: RuntimeCanaryReport,
        *,
        expected_agent_version: str | None,
        expected_runtime_plan_version: str | None,
    ) -> bool:
        if not report.release_eligible or not report.evidence.release_ready:
            return False
        if expected_agent_version is not None and (
            report.evidence.agent_version != expected_agent_version
        ):
            return False
        if expected_runtime_plan_version is not None and (
            report.evidence.runtime_plan_version
            != expected_runtime_plan_version
        ):
            return False
        return True
