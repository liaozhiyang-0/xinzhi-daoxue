from __future__ import annotations

import re
from collections.abc import Callable
from time import perf_counter
from typing import Any

from app.agents.registry import AgentDefinition
from app.contracts import (
    AgentRequest,
    AgentResult,
    AgentValidationResult,
    WorkflowContextBundle,
)

Validator = Callable[
    [AgentResult, AgentRequest, WorkflowContextBundle | None],
    tuple[list[str], list[str], bool],
]


class AgentResultValidatorRegistry:
    """Agent-specific deterministic safety and contract checks."""

    def __init__(self) -> None:
        self._validators: dict[str, Validator] = {
            "generic": self._generic,
            "learn_qa": self._learn,
            "solver_ct": self._solver,
            "lesson_prep": self._lesson,
            "assignment_review": self._assignment,
            "academic_writing": self._writing,
            "data_analysis": self._analysis,
            "router_only": self._generic,
        }

    def validate(
        self,
        definition: AgentDefinition,
        result: AgentResult,
        request: AgentRequest,
        bundle: WorkflowContextBundle | None,
    ) -> AgentValidationResult:
        started = perf_counter()
        upstream = str(result.structured_result.get("status", "completed")).casefold()
        if upstream == "misrouted":
            return AgentValidationResult(
                validation_status="misrouted",
                validation_issues=["目标工作流明确拒绝当前任务"],
                response_usable=False,
                result_status="misrouted",
                latency_ms=(perf_counter() - started) * 1000,
            )
        issues, corrected, usable = self._validators[definition.validator_type](
            result, request, bundle
        )
        if result.fallback_used:
            status = "fallback"
        elif not usable:
            status = "insufficient" if upstream != "failed" else "failed"
        elif issues or result.warnings or result.assumptions:
            status = "accepted_with_warnings"
        else:
            status = "accepted"
        validation_status = (
            "passed" if not issues else "warning" if usable else "failed"
        )
        return AgentValidationResult(
            validation_status=validation_status,
            validation_issues=issues,
            corrected_fields=corrected,
            response_usable=usable,
            result_status=status,
            latency_ms=(perf_counter() - started) * 1000,
        )

    @staticmethod
    def _generic(
        result: AgentResult,
        request: AgentRequest,
        bundle: WorkflowContextBundle | None,
    ) -> tuple[list[str], list[str], bool]:
        del request, bundle
        return (
            ["回答为空"] if not result.answer.strip() else [],
            [],
            bool(result.answer.strip()),
        )

    @staticmethod
    def _learn(
        result: AgentResult,
        request: AgentRequest,
        bundle: WorkflowContextBundle | None,
    ) -> tuple[list[str], list[str], bool]:
        issues: list[str] = []
        if not result.answer.strip():
            issues.append("知识问答正文为空")
        returned_course = str(
            result.structured_result.get("course_id", request.course_id)
        )
        if returned_course and returned_course not in {request.course_id, "UNKNOWN"}:
            issues.append("工作流返回课程与路由课程不一致")
        declared = result.structured_result.get("source_references", [])
        valid_ids = set(bundle.workflow_evidence_ids if bundle else [])
        if isinstance(declared, list) and any(
            str(item) not in valid_ids for item in declared
        ):
            issues.append("存在不属于当前证据包的引用")
        return issues, [], bool(result.answer.strip())

    @staticmethod
    def _solver(
        result: AgentResult,
        request: AgentRequest,
        bundle: WorkflowContextBundle | None,
    ) -> tuple[list[str], list[str], bool]:
        issues: list[str] = []
        data = result.business_data or result.structured_result
        if not result.answer.strip():
            issues.append("求解回答为空")
        if not data.get("final_answer") and not result.structured_result.get(
            "final_answer"
        ):
            issues.append("未提供独立的最终答案字段")
        if request.attachments and any(
            token in result.answer for token in ("无法识别", "图片不清晰", "未识别")
        ):
            issues.append("图片题识别未成功")
        if bundle and bundle.rag_mode.value == "method_reference" and result.citations:
            issues.append("方法参考不得标记为云端生成依据")
            result.citations = []
        return (
            issues,
            ["citations"] if issues and result.citations else [],
            bool(result.answer.strip()),
        )

    @staticmethod
    def _lesson(
        result: AgentResult,
        request: AgentRequest,
        bundle: WorkflowContextBundle | None,
    ) -> tuple[list[str], list[str], bool]:
        del request, bundle
        data = result.business_data or result.structured_result.get("business_data", {})
        issues = []
        for field, label in (
            ("learning_objectives", "教学目标"),
            ("lesson_flow", "课堂流程"),
            ("activities", "课堂活动"),
            ("formative_assessment", "形成性评价"),
        ):
            if not data.get(field):
                issues.append(f"缺少{label}结构")
        return issues, [], bool(result.answer.strip())

    @staticmethod
    def _assignment(
        result: AgentResult,
        request: AgentRequest,
        bundle: WorkflowContextBundle | None,
    ) -> tuple[list[str], list[str], bool]:
        del bundle
        data = result.business_data or result.structured_result.get("business_data", {})
        issues: list[str] = []
        corrected: list[str] = []
        materials = request.options.get("_material_extraction", {}).get("materials", {})
        rubric = materials.get("rubric") if isinstance(materials, dict) else None
        maximum = (
            materials.get("maximum_score") if isinstance(materials, dict) else None
        )
        score = data.get("score_suggestion")
        if not rubric and score not in {None, ""}:
            data.pop("score_suggestion", None)
            issues.append("未提供rubric，已移除确定性正式分数")
            corrected.append("business_data.score_suggestion")
        try:
            if (
                maximum not in {None, ""}
                and score not in {None, ""}
                and float(str(score)) > float(str(maximum))
            ):
                data["score_suggestion"] = float(str(maximum))
                issues.append("建议得分超过满分，已限制到满分")
                corrected.append("business_data.score_suggestion")
        except (TypeError, ValueError):
            issues.append("满分或建议得分不是有效数字")
        if re.search(r"(?:确定|认定).{0,4}作弊", result.answer):
            issues.append("回答包含无依据的作弊定性")
        return issues, corrected, bool(result.answer.strip())

    @staticmethod
    def _writing(
        result: AgentResult,
        request: AgentRequest,
        bundle: WorkflowContextBundle | None,
    ) -> tuple[list[str], list[str], bool]:
        del bundle
        issues: list[str] = []
        source_text = "\n".join(
            str(request.canonical_input.get(key, ""))
            for key in ("source_text", "trusted_sources", "text", "question")
        )
        for doi in re.findall(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", result.answer, re.I):
            if doi not in source_text:
                issues.append("输出新增了用户未提供的DOI")
        if re.search(
            r"(?:实验|研究)(?:已经|已)(?:证明|证实|完成)", result.answer
        ) and not any(
            token in source_text
            for token in ("实验结果", "研究结果", "provided_results")
        ):
            issues.append("可能把计划表述为已完成实验")
        return (
            issues,
            [],
            bool(result.answer.strip()) and not any("DOI" in item for item in issues),
        )

    @staticmethod
    def _analysis(
        result: AgentResult,
        request: AgentRequest,
        bundle: WorkflowContextBundle | None,
    ) -> tuple[list[str], list[str], bool]:
        del bundle
        issues: list[str] = []
        corrected: list[str] = []
        data = result.business_data or result.structured_result.get("business_data", {})
        if result.structured_result.get("analysis_v2") is True:
            if not result.answer.strip():
                issues.append("科研数据分析 V2 未生成可展示结果")
            if data.get("human_review_required") is not True:
                issues.append("科研数据分析 V2 缺少人工复核标记")
            return (
                issues,
                corrected,
                bool(result.answer.strip()) and not issues,
            )
        materials = request.options.get("_material_extraction", {}).get("materials", {})
        provided = (
            materials.get("provided_results") if isinstance(materials, dict) else None
        )
        if not provided and data.get("analysis_status") != "plan":
            data["analysis_status"] = "plan"
            issues.append("无真实结果，已将analysis_status校正为plan")
            corrected.append("business_data.analysis_status")
        source = str(provided or "")
        for label, pattern in (
            ("p值", r"\bp\s*[=<]\s*0?\.\d+"),
            ("AUC", r"\bAUC\s*[=:]?\s*0?\.\d+"),
            ("样本量", r"\bn\s*=\s*\d+"),
        ):
            generated = re.findall(pattern, result.answer, re.I)
            if any(item not in source for item in generated):
                issues.append(f"输出包含用户未提供的{label}数值")
        return (
            issues,
            corrected,
            bool(result.answer.strip())
            and not any("未提供的" in item for item in issues),
        )


class BusinessResultRendererRegistry:
    """Convert normalized business data to front-end sections without raw JSON."""

    FIELD_LABELS: dict[str, tuple[tuple[str, str], ...]] = {
        "learn_qa": (
            ("key_points", "关键点"),
            ("learning_advice", "学习建议"),
            ("evidence_summary", "证据摘要"),
            ("weak_knowledge_points", "薄弱知识点"),
            ("prerequisite_path", "前置知识路径"),
            ("staged_plan", "阶段学习计划"),
            ("verification_tasks", "验证任务"),
            ("asset_inventory", "课程资产清单"),
            ("version_conflicts", "版本冲突"),
            ("source_audit", "来源审计"),
            ("approval_status", "审批状态"),
            ("publication_blockers", "发布阻塞项"),
            ("traceability_links", "可追溯链接"),
            ("publication_checklist_before", "发布前检查清单"),
            ("publication_checklist_after", "发布后检查清单"),
            ("rollback_checklist", "回滚后检查清单"),
            ("research_scope", "检索范围"),
            ("evidence_table", "证据表"),
            ("doi_or_arxiv", "DOI 或 arXiv"),
            ("open_questions", "开放问题"),
            ("limitations", "限制"),
            ("first_error", "首个错误"),
            ("error_cause", "错误原因"),
            ("preserved_correct_steps", "保留的正确步骤"),
            ("tiered_hints", "分层提示"),
            ("verification_problem", "验证题"),
            ("common_misconceptions", "常见误区"),
            ("differentiated_practice", "分层练习"),
            ("evidence", "资料依据"),
            ("review_boundary", "人工复核边界"),
        ),
        "solver_ct": (
            ("problem_summary", "题目摘要"),
            ("key_equations", "关键方程"),
            ("steps", "分步解答"),
            ("final_answer", "最终答案"),
            ("assumptions", "假设"),
            ("remaining_risks", "风险"),
        ),
        "lesson_prep": (
            ("learning_objectives", "教学目标"),
            ("prerequisites", "先修知识"),
            ("lesson_flow", "课堂流程"),
            ("worked_examples", "例题"),
            ("worked_example", "带解例题"),
            ("common_confusions", "常见混淆"),
            ("tiered_practice", "分层练习"),
            ("activities", "课堂活动"),
            ("formative_assessment", "形成性评价"),
            ("evidence_notes", "资料依据与缺口"),
            ("missing_information", "缺失信息"),
            ("homework", "课后作业"),
            ("teacher_notes", "教师备注"),
            ("teacher_review", "教师复核"),
        ),
        "assignment_review": (
            ("score_suggestion", "建议得分"),
            ("rubric_breakdown", "评分点拆解"),
            ("correct_parts", "正确部分"),
            ("errors", "需要改进"),
            ("first_error", "首个关键错误"),
            ("error_propagation", "错误传播"),
            ("basic_hint", "基础提示"),
            ("advanced_hint", "进阶提示"),
            ("verification_task", "验证任务"),
            ("evidence_notes", "资料依据与缺口"),
            ("missing_information", "缺失信息"),
            ("teacher_feedback", "教师反馈"),
            ("teacher_review", "教师复核"),
            ("review_required", "人工复核"),
        ),
        "academic_writing": (
            ("outline", "提纲"),
            ("revised_text", "修改稿"),
            ("revision_notes", "修改说明"),
            ("citation_check", "引用检查"),
            ("unsupported_claims", "无依据声明"),
        ),
        "data_analysis": (
            ("status", "分析状态"),
            ("design_assessment", "设计评估"),
            ("plan", "冻结分析计划"),
            ("data_quality", "数据质量"),
            ("method_selection", "方法选择"),
            ("metrics", "指标"),
            ("result_interpretation", "结果解释"),
            ("primary_result", "主要结果"),
            ("effect_estimates", "效应量与指标"),
            ("uncertainty_summary", "不确定性"),
            ("diagnostics", "诊断"),
            ("robustness_findings", "稳健性与敏感性"),
            ("interpretation", "科学解释边界"),
            ("evidence_ids", "方法证据 ID"),
            ("evidence_references", "方法证据来源"),
            ("provenance", "数据版本与复现元数据"),
            ("artifacts", "可复现 Artifact"),
            ("review_checklist", "人工复核清单"),
            ("limitations", "限制"),
        ),
    }

    def render(
        self,
        definition: AgentDefinition,
        result: AgentResult,
        validation: AgentValidationResult,
    ) -> dict[str, Any]:
        data = dict(result.business_data)
        nested = result.structured_result.get("business_data", {})
        if isinstance(nested, dict):
            data.update(nested)
        for key in (
            "problem_summary",
            "key_equations",
            "final_answer",
            "assumptions",
            "remaining_risks",
            "key_points",
        ):
            if key in result.structured_result:
                data.setdefault(key, result.structured_result[key])
        sections = [
            {"key": key, "label": label, "content": data[key]}
            for key, label in self.FIELD_LABELS.get(definition.renderer_type, ())
            if data.get(key) is not None
            and data.get(key) != ""
            and data.get(key) != []
            and data.get(key) != {}
        ]
        banner = ""
        if definition.renderer_type == "assignment_review":
            banner = "建议分仅供教师复核，不是正式成绩"
        elif (
            definition.renderer_type == "data_analysis"
            and data.get("analysis_status") == "plan"
        ):
            banner = "当前为分析方案，未实际运行计算"
        elif (
            definition.renderer_type == "data_analysis"
            and result.structured_result.get("analysis_v2") is True
        ):
            model_assistance = result.structured_result.get("model_assistance", {})
            if (
                result.structured_result.get("analysis_execution_source")
                == "model_direct"
            ):
                banner = (
                    "科研数据分析 V2 已由 Qwen/Spark 直接分析；"
                    "模型生成的统计结果必须独立复核"
                )
            elif model_assistance.get("status") == "used":
                banner = (
                    "科研数据分析 V2 已完成本地计算，并由模型辅助解释；"
                    "数值与结论边界仍需人工复核"
                )
            else:
                banner = "科研数据分析 V2 已按本地确定性流程生成，结论必须人工复核"
        return {
            "renderer_type": definition.renderer_type,
            "banner": banner,
            "sections": sections,
            "copy_field": (
                "revised_text" if definition.renderer_type == "academic_writing" else ""
            ),
            "validation_status": validation.validation_status,
            "result_status": validation.result_status,
        }
