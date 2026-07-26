from __future__ import annotations

from typing import Literal

from app.contracts.solver import (
    QualityCheck,
    QualityGateResult,
    SolverFinalAnswer,
    SolverKnowledgeEvidence,
    SolverResult,
    SolverVerification,
)
from app.courses.base import BaseCoursePack


class SolverQualityGateService:
    """Deterministic, bounded acceptance gate for every academic result."""

    def evaluate(self, result: SolverResult, pack: BaseCoursePack) -> SolverResult:
        checks: list[QualityCheck] = []

        def add(check_id: str, passed: bool, message: str) -> None:
            checks.append(
                QualityCheck(
                    check_id=check_id,
                    status="pass" if passed else "fail",
                    message=message,
                )
            )

        add(
            "answer_present",
            bool(result.final_answer.strip()),
            "最终答案非空" if result.final_answer.strip() else "缺少最终答案",
        )
        add(
            "steps_present",
            bool(result.solution_steps) or result.status in {"unsupported", "failed"},
            "包含可审查步骤" if result.solution_steps else "缺少可审查步骤",
        )
        add(
            "confidence_bounded",
            0 <= result.confidence <= 1,
            "置信度位于 [0, 1]",
        )
        high_risk = result.execution_path == "HIGH_RISK"
        verified = result.verification_report is not None and (
            result.verification_report.verification_status == "pass"
        )
        checks.append(
            QualityCheck(
                check_id="high_risk_verification",
                status=("pass" if verified else "fail")
                if high_risk
                else "not_applicable",
                message=(
                    "HIGH_RISK 已完成确定性校验"
                    if verified
                    else "HIGH_RISK 未通过确定性校验"
                    if high_risk
                    else "当前路径无需强制 HIGH_RISK 校验"
                ),
            )
        )
        evidence = result.knowledge_evidence or SolverKnowledgeEvidence()
        if result.citations:
            citation_ok = evidence.citation_status in {"valid", "partially_supported"}
            checks.append(
                QualityCheck(
                    check_id="citation_traceability",
                    status="pass" if citation_ok else "warn",
                    message=f"引用状态：{evidence.citation_status}",
                )
            )
        else:
            checks.append(
                QualityCheck(
                    check_id="citation_traceability",
                    status="not_applicable",
                    message="本次结果未声明课程资料引用",
                )
            )
        for rule in pack.verification_rules:
            checks.append(
                QualityCheck(
                    check_id=f"course_rule:{rule}",
                    status="pass" if verified else "warn",
                    message=(
                        f"课程规则 {rule} 已由校验报告覆盖"
                        if verified
                        else f"课程规则 {rule} 尚无确定性覆盖证据"
                    ),
                )
            )

        failures = [item.message for item in checks if item.status == "fail"]
        warnings = [item.message for item in checks if item.status == "warn"]
        status: Literal["pass", "partial", "fail"] = (
            "fail" if failures else "partial" if warnings else "pass"
        )
        quality_gate = QualityGateResult(
            status=status,
            checks=checks,
            blocked_reasons=failures,
            applied_course_rules=list(pack.verification_rules),
        )
        verification = SolverVerification(
            status=(
                "pass"
                if result.consistency_status == "verified"
                else "partial"
                if result.consistency_status != "not_checked"
                else "not_checked"
            ),
            checks=[item.model_dump(mode="json") for item in checks],
            issues=[*result.remaining_issues, *failures],
        )
        detail = result.final_answer_detail or SolverFinalAnswer(
            value=result.final_answer,
            conclusion=result.final_answer,
            confidence=result.confidence,
        )
        update: dict[str, object] = {
            "final_answer_detail": detail,
            "verification": verification,
            "knowledge_evidence": evidence,
            "quality_gate": quality_gate,
        }
        if status == "fail" and result.status == "success":
            update["status"] = "partial"
            update["remaining_risks"] = [*result.remaining_risks, *failures]
        return result.model_copy(update=update)
