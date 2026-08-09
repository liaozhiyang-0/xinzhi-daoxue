from __future__ import annotations

from collections import Counter
from typing import Literal

from app.contracts.research_analysis import (
    ResearchAnalysisRequest,
    ResearchDataQualityCheck,
    ResearchDataQualityReport,
    ResearchQualityGateDecision,
)

DESIGN_REQUIRED_ROLES: dict[str, frozenset[str]] = {
    "experimental_comparison": frozenset({"outcome", "treatment"}),
    "multigroup_comparison": frozenset({"outcome", "treatment"}),
    "repeated_measures": frozenset({"outcome", "treatment", "identifier"}),
    "observational_regression": frozenset({"outcome", "exposure"}),
    "time_series": frozenset({"time", "outcome"}),
    "small_sample": frozenset({"outcome"}),
    "prediction": frozenset({"outcome", "feature"}),
}


class ResearchDataQualityService:
    """Deterministic pre-execution quality gate; it never reads raw data."""

    def evaluate(self, request: ResearchAnalysisRequest) -> ResearchQualityGateDecision:
        if request.data_manifest is None:
            report = ResearchDataQualityReport(
                status="blocked",
                checks=[
                    ResearchDataQualityCheck(
                        check_id="dataset_manifest",
                        status="failed",
                        summary="尚未提供数据清单，当前只能制定分析计划",
                        blocking=True,
                    )
                ],
                limitations=["缺少授权数据集、版本和 checksum"],
            )
            return ResearchQualityGateDecision(
                analysis_status="insufficient_data",
                report=report,
                reasons=["missing_dataset_manifest"],
            )

        checks: list[ResearchDataQualityCheck] = []
        reasons: list[str] = []
        manifest = request.data_manifest
        self._append_authorization_check(checks, manifest.authorized)
        if not manifest.authorized:
            reasons.append("dataset_not_authorized")
        self._append_manifest_metadata_checks(checks, manifest)
        if not manifest.checksum_sha256:
            reasons.append("missing_dataset_checksum")
        if manifest.contains_sensitive_data:
            reasons.append("sensitive_data_requires_review")

        names = [item.name for item in request.variables]
        duplicate_names = sorted(
            name for name, count in Counter(names).items() if count > 1
        )
        checks.append(
            ResearchDataQualityCheck(
                check_id="variable_names",
                status="failed" if duplicate_names else "passed",
                summary=(
                    f"变量名重复：{', '.join(duplicate_names)}"
                    if duplicate_names
                    else "变量名唯一"
                ),
                affected_columns=duplicate_names,
                blocking=bool(duplicate_names),
            )
        )
        if duplicate_names:
            reasons.append("duplicate_variable_names")

        required_roles = DESIGN_REQUIRED_ROLES.get(request.design)
        actual_roles = {item.role for item in request.variables}
        if required_roles is None:
            checks.append(
                ResearchDataQualityCheck(
                    check_id="design_roles",
                    status="failed",
                    summary="研究设计尚未确定，无法选择可执行分析方法",
                    blocking=True,
                )
            )
            reasons.append("unknown_research_design")
        else:
            missing_roles = sorted(required_roles - actual_roles)
            checks.append(
                ResearchDataQualityCheck(
                    check_id="design_roles",
                    status="failed" if missing_roles else "passed",
                    summary=(
                        f"缺少变量角色：{', '.join(missing_roles)}"
                        if missing_roles
                        else "研究设计所需变量角色齐全"
                    ),
                    affected_columns=missing_roles,
                    blocking=bool(missing_roles),
                )
            )
            if missing_roles:
                reasons.append("missing_required_variable_roles")

        if not request.data_dictionary.strip():
            checks.append(
                ResearchDataQualityCheck(
                    check_id="data_dictionary",
                    status="warning",
                    summary="缺少数据字典，变量含义和单位需要人工确认",
                )
            )
            reasons.append("missing_data_dictionary")
        else:
            checks.append(
                ResearchDataQualityCheck(
                    check_id="data_dictionary",
                    status="passed",
                    summary="已提供数据字典文本，仍需与实际 schema 对照",
                )
            )

        if any(
            item.role in {"outcome", "exposure", "treatment", "feature"}
            and not item.unit
            for item in request.variables
        ):
            checks.append(
                ResearchDataQualityCheck(
                    check_id="variable_units",
                    status="warning",
                    summary="关键变量存在缺失单位，结果解释需要人工复核",
                )
            )
            reasons.append("missing_variable_units")
        else:
            checks.append(
                ResearchDataQualityCheck(
                    check_id="variable_units",
                    status="passed",
                    summary="关键变量均声明单位或不适用",
                )
            )

        blocking = any(check.blocking or check.status == "failed" for check in checks)
        report_status: Literal["passed", "needs_review", "blocked"]
        analysis_status: Literal[
            "planning", "quality_blocked", "ready_for_execution"
        ]
        if blocking:
            report_status = "blocked"
            analysis_status = "quality_blocked"
        elif manifest.contains_sensitive_data or not manifest.checksum_sha256:
            report_status = "needs_review"
            analysis_status = "planning"
        else:
            report_status = "passed"
            analysis_status = "ready_for_execution"
        return ResearchQualityGateDecision(
            analysis_status=analysis_status,
            report=ResearchDataQualityReport(
                status=report_status,
                checks=checks,
                limitations=(
                    ["质量门禁只检查元数据，尚未读取原始数据行"]
                    if report_status != "blocked"
                    else ["质量门禁未通过，禁止执行统计或模型"]
                ),
            ),
            reasons=reasons,
        )

    @staticmethod
    def _append_authorization_check(
        checks: list[ResearchDataQualityCheck], authorized: bool
    ) -> None:
        checks.append(
            ResearchDataQualityCheck(
                check_id="dataset_authorization",
                status="passed" if authorized else "failed",
                summary=("数据集已授权" if authorized else "数据集未标记为授权"),
                blocking=not authorized,
            )
        )

    @staticmethod
    def _append_manifest_metadata_checks(
        checks: list[ResearchDataQualityCheck], manifest: object
    ) -> None:
        row_count = getattr(manifest, "row_count", None)
        column_count = getattr(manifest, "column_count", None)
        empty = row_count == 0 or column_count == 0
        checks.append(
            ResearchDataQualityCheck(
                check_id="dataset_shape",
                status=(
                    "failed"
                    if empty
                    else "warning"
                    if row_count is None
                    else "passed"
                ),
                summary=(
                    "数据集行数或列数为0"
                    if empty
                    else "数据集规模尚未写入清单"
                    if row_count is None
                    else f"数据集规模：{row_count}行、{column_count or '未知'}列"
                ),
                blocking=empty,
            )
        )
