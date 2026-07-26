from __future__ import annotations

from hashlib import sha256
from typing import Any, Literal

from app.contracts.solver import (
    AcademicProblem,
    AcademicSolutionResult,
    SolutionPatch,
    ToolResult,
    VerificationIssue,
    VerificationReport,
)


class HighRiskVerificationService:
    """Build deterministic-first review reports and apply bounded local patches."""

    def verify(
        self,
        problem: AcademicProblem,
        result: AcademicSolutionResult,
        tool_results: list[ToolResult],
    ) -> VerificationReport:
        issues: list[VerificationIssue] = []
        for index, conflict in enumerate(problem.source_conflicts):
            description = str(conflict.get("description", conflict))
            issue_type = self._classify_conflict(description)
            issues.append(
                self._issue(
                    f"source_conflicts[{index}]",
                    issue_type,
                    description,
                    severity="high",
                    instruction="保留冲突标记；仅在原始题目或确定性证据确认后修正。",
                )
            )
        for index, missing in enumerate(problem.critical_missing_info):
            description = str(missing.get("field", missing))
            issues.append(
                self._issue(
                    f"critical_missing_info[{index}]",
                    "condition",
                    description,
                    severity="high",
                    instruction="将相关结论改为条件化表达，不补造缺失参数。",
                )
            )
        for index, tool in enumerate(tool_results):
            if tool.status == "success":
                continue
            issues.append(
                self._issue(
                    f"tool_verification[{index}]",
                    "tool_conflict",
                    "; ".join(tool.warnings) or f"{tool.tool_id}:{tool.status}",
                    severity="critical" if tool.status == "failed" else "high",
                    instruction="保留主答案，仅局部标记该计算未通过确定性工具校验。",
                    deterministic=True,
                )
            )
        successful_tools = [item for item in tool_results if item.status == "success"]
        if not successful_tools and not issues:
            issues.append(
                self._issue(
                    "verification",
                    "evidence",
                    "HIGH_RISK答案缺少可用的确定性工具证据",
                    severity="medium",
                    instruction="将未经工具确认的关键结论标记为不确定。",
                )
            )
        status = self._status(issues)
        confidence = (
            0.9
            if status == "pass"
            else max(0.2, min(0.75, result.confidence - len(issues) * 0.08))
        )
        return VerificationReport(
            verification_status=status,
            issues=issues,
            requires_patch=bool(issues),
            requires_fallback=any(
                item.severity in {"high", "critical"} for item in issues
            ),
            confidence=confidence if issues else max(0.9, result.confidence),
        )

    def patches_for(self, report: VerificationReport) -> list[SolutionPatch]:
        if not report.requires_patch:
            return []
        severe = [
            item for item in report.issues if item.severity in {"high", "critical"}
        ]
        issue_ids = [item.issue_id for item in (severe or report.issues)]
        summary = "；".join(
            item.correction_instruction or item.issue_type
            for item in (severe or report.issues)
        )
        return [
            SolutionPatch(
                target_section="final_answer",
                operation="mark_uncertain",
                old_content_summary="保留现有答案主体",
                new_content=f"校验提示：{summary}",
                reason=f"HIGH_RISK校验状态为{report.verification_status}",
                verification_issue_ids=issue_ids,
            )
        ]

    def apply_patches(
        self,
        result: AcademicSolutionResult,
        patches: list[SolutionPatch],
        report: VerificationReport,
    ) -> AcademicSolutionResult:
        answer = result.final_answer
        risks = list(result.remaining_risks)
        sections: list[str] = []
        applied: list[SolutionPatch] = []
        for patch in patches:
            if patch.target_section != "final_answer":
                risks.append(f"未应用不支持的补丁区域: {patch.target_section}")
                continue
            if patch.operation == "mark_uncertain":
                marker = f"\n\n【不确定性标记】{patch.new_content}"
                if marker not in answer:
                    answer += marker
            elif patch.operation == "append":
                answer += f"\n\n{patch.new_content}"
            else:
                risks.append("拒绝使用replace/remove覆盖完整final_answer")
                continue
            sections.append(patch.target_section)
            applied.append(patch)
        remaining = [item.issue_id for item in report.issues]
        issue_summaries = [
            item.evidence[0] if item.evidence else item.issue_type
            for item in report.issues
        ]
        return result.model_copy(
            update={
                "final_answer": answer,
                "verification_report": report,
                "patches": applied,
                "patch_count": len(applied),
                "patched_sections": list(dict.fromkeys(sections)),
                "remaining_issues": remaining,
                "remaining_risks": list(dict.fromkeys([*risks, *issue_summaries])),
                "consistency_status": report.verification_status,
                "confidence": min(result.confidence, report.confidence),
            }
        )

    def merge_secondary_review(
        self, report: VerificationReport, review: str
    ) -> VerificationReport:
        summary = review.strip()[:1000]
        if not summary:
            return report
        issue = self._issue(
            "secondary_model_review",
            "evidence",
            summary,
            severity="medium",
            instruction="次模型意见仅作为待核对线索，不作为确定性事实。",
        )
        return report.model_copy(
            update={
                "issues": [*report.issues, issue],
                "requires_patch": True,
                "confidence": min(report.confidence, 0.65),
            }
        )

    @staticmethod
    def _classify_conflict(description: str) -> str:
        lowered = description.casefold()
        if any(item in lowered for item in ("方向", "极性", "参考")):
            return "direction"
        if any(item in lowered for item in ("单位", "量纲")):
            return "unit"
        if any(item in lowered for item in ("方程", "等式")):
            return "equation"
        return "evidence"

    @staticmethod
    def _status(
        issues: list[VerificationIssue],
    ) -> Literal["pass", "conflict", "uncertain", "failed"]:
        if not issues:
            return "pass"
        if any(item.issue_type == "tool_conflict" for item in issues):
            return "failed"
        if any(item.severity in {"high", "critical"} for item in issues):
            return "conflict"
        return "uncertain"

    @staticmethod
    def _issue(
        location: str,
        issue_type: Any,
        evidence: str,
        *,
        severity: Any,
        instruction: str,
        deterministic: bool = False,
    ) -> VerificationIssue:
        digest = sha256(f"{location}|{issue_type}|{evidence}".encode()).hexdigest()[:12]
        return VerificationIssue(
            issue_id=f"verify_{digest}",
            issue_type=issue_type,
            location=location,
            severity=severity,
            evidence=[evidence],
            correction_instruction=instruction,
            deterministic=deterministic,
        )
