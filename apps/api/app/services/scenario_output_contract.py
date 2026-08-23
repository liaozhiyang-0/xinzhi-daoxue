from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.contracts import AgentRequest, AgentResult


def _requested_research_count(query: str) -> int | None:
    match = re.search(
        r"(?:至少|不少于|不低于|at\s+least)\s*(\d+)\s*"
        r"(?:篇|条|项|papers?|sources?)?",
        query,
        flags=re.IGNORECASE,
    )
    return int(match.group(1)) if match else None


class ScenarioOutputContractService:
    """Materialize the configured demo-case contract in a task result.

    Scenario binding happens at task creation.  This service deliberately does
    not call a model: it normalizes fields already produced by the selected
    Agent, adds deterministic case-specific scaffolding where the local
    runtime is retrieval-only, and marks evidence gaps explicitly.
    """

    _LABELS = {
        "faculty_course_copilot_v1": "教师智能备课",
        "assessment_diagnosis_v1": "作业批改与首错诊断",
        "student_learning_path_v1": "学生个性化学习路径",
        "research_frontier_radar_v1": "科研前沿检索与证据简报",
        "department_knowledge_governance_v1": "学院知识库治理与课程资产发布",
        "academic_visual_problem_solver_v1": "学术题图视觉求解",
        "academic_visual_spectrum_solver_v1": "学术题图频谱视觉求解",
        "academic_text_diagnostic_solver_v1": "学术纯文本电路诊断",
        "rubric_generation_v1": "教师评分量规生成",
    }

    def enrich(self, result: AgentResult, request: AgentRequest) -> AgentResult:
        raw_contract = request.options.get("scenario_contract")
        if not isinstance(raw_contract, Mapping):
            return result

        contract = dict(raw_contract)
        expected_agent = str(contract.get("expected_agent", ""))
        scenario_id = str(
            request.options.get("scenario_id") or request.scenario_id or ""
        )
        governance = scenario_id == "department_knowledge_governance_v1"
        if (
            (result.fallback_used and not governance)
            or expected_agent != result.agent_id
        ):
            result.structured_result["scenario_contract"] = {
                **contract,
                "status": "not_applied",
                "reason": (
                    "generic_fallback_used"
                    if result.fallback_used
                    else "selected_agent_mismatch"
                ),
                "present_fields": [],
                "missing_fields": list(contract.get("expected_output", [])),
                "presentation_label": self._label(request),
            }
            return result

        data = dict(result.business_data)
        nested_data = result.structured_result.get("business_data")
        if isinstance(nested_data, Mapping):
            data = {**dict(nested_data), **data}
        data.setdefault("final_answer", result.answer)
        if "external_retrieval" in result.structured_result:
            data.setdefault(
                "external_retrieval",
                result.structured_result.get("external_retrieval"),
            )
        data.setdefault("scenario_id", scenario_id)
        data.setdefault("scenario_case_id", contract.get("demo_case_id", ""))
        evidence = self._evidence(result)
        fields = self._build_fields(scenario_id, data, evidence, contract, request)
        data.update(fields)
        result.business_data = data
        result.structured_result["business_data"] = data

        expected_output = [
            str(item) for item in contract.get("expected_output", []) if str(item)
        ]
        present_fields = [
            key
            for key in expected_output
            if self._field_is_present(data.get(key))
        ]
        missing_fields = [key for key in expected_output if key not in present_fields]
        has_unavailable = any(
            isinstance(data.get(key), Mapping)
            and data[key].get("status")
            in {
                "not_available",
                "unknown",
                "not_determinable",
                "possible_conflict_needs_review",
            }
            for key in expected_output
        )
        evidence_status = str(
            result.evidence_status or evidence.get("status", "insufficient")
        )
        duration_check = data.get("duration_check")
        has_duration_gap = isinstance(duration_check, Mapping) and str(
            duration_check.get("status", "")
        ) in {"missing", "mismatch"}
        plan_horizon_check = data.get("plan_horizon_check")
        has_plan_horizon_gap = isinstance(plan_horizon_check, Mapping) and str(
            plan_horizon_check.get("status", "")
        ) in {"missing", "mismatch"}
        external_retrieval = data.get("external_retrieval")
        external_review_status = (
            self._external_review_status(external_retrieval)
            if isinstance(external_retrieval, Mapping)
            else "not_applicable"
        )
        has_evidence_review_gap = (
            scenario_id == "research_frontier_radar_v1"
            and external_review_status not in {"approved", "not_applicable"}
        )
        research_quality = data.get("research_evidence_quality")
        has_research_quality_gap = (
            scenario_id == "research_frontier_radar_v1"
            and isinstance(research_quality, Mapping)
            and str(research_quality.get("status", ""))
            in {"insufficient", "partial"}
        )
        raw_visual_acceptance = data.get("visual_acceptance")
        if not isinstance(raw_visual_acceptance, Mapping):
            raw_vision = data.get("vision_execution")
            raw_visual_acceptance = (
                raw_vision.get("visual_acceptance")
                if isinstance(raw_vision, Mapping)
                else None
            )
        has_visual_acceptance_gap = (
            scenario_id.startswith("academic_visual_")
            and isinstance(raw_visual_acceptance, Mapping)
            and str(raw_visual_acceptance.get("status", "")) != "passed"
        )
        has_manual_review_gap = scenario_id == "academic_text_diagnostic_solver_v1"
        evidence_policy = request.options.get("scenario_evidence_policy")
        manual_review_required = isinstance(evidence_policy, Mapping) and bool(
            evidence_policy.get("manual_review_required", False)
        )
        has_policy_review_gap = manual_review_required
        course_confirmation_required = bool(
            contract.get("course_confirmation_required", False)
        )
        model_synthesis_required = governance and (
            result.structured_result.get("mode") != "governance_model_generation"
        )
        contract_status = (
            "model_synthesis_required"
            if model_synthesis_required
            else (
                "completed_with_gaps"
                if (
                    has_unavailable
                    or evidence_status != "sufficient"
                    or has_duration_gap
                    or has_plan_horizon_gap
                    or has_evidence_review_gap
                    or has_research_quality_gap
                    or has_visual_acceptance_gap
                    or has_manual_review_gap
                    or has_policy_review_gap
                    or course_confirmation_required
                )
                else "completed"
            )
        )
        result.structured_result["scenario_contract"] = {
            **contract,
            "status": contract_status,
            "scenario_id": scenario_id,
            "presentation_label": self._label(request),
            "present_fields": present_fields,
            "missing_fields": missing_fields,
            "evidence_status": evidence_status,
            "evidence_review_status": external_review_status,
            "quality_gaps": (
                [
                    *(["duration_constraint"] if has_duration_gap else []),
                    *(["plan_horizon"] if has_plan_horizon_gap else []),
                    *(["evidence_review"] if has_evidence_review_gap else []),
                    *(
                        ["research_evidence_quality"]
                        if has_research_quality_gap
                        else []
                    ),
                    *(["visual_acceptance"] if has_visual_acceptance_gap else []),
                    *(["manual_review"] if has_manual_review_gap else []),
                    *(
                        ["manual_review_required"]
                        if has_policy_review_gap
                        else []
                    ),
                    *(
                        ["course_confirmation"]
                        if course_confirmation_required
                        else []
                    ),
                ]
            ),
            "evidence_source_refs": evidence.get("source_refs", []),
            "model_synthesis": {
                "status": "required" if model_synthesis_required else "completed",
                "publishable": contract_status == "completed",
            },
        }
        result.structured_result["scenario_id"] = scenario_id
        result.answer = self._append_contract_answer(
            result.answer,
            self._label(request),
            fields,
            str(contract.get("review_boundary", "")),
        )
        return result

    @staticmethod
    def _field_is_present(value: Any) -> bool:
        """Count only usable values as present in the scenario contract.

        Availability envelopes are intentionally kept in ``business_data`` so
        the UI can explain why a field is missing.  They must not, however,
        satisfy an acceptance contract merely because the mapping is non-empty.
        """

        if value in (None, "", [], {}):
            return False
        if isinstance(value, Mapping) and str(value.get("status", "")) in {
            "not_available",
            "unknown",
            "not_determinable",
            "possible_conflict_needs_review",
        }:
            return False
        return True

    def _build_fields(
        self,
        scenario_id: str,
        data: dict[str, Any],
        evidence: dict[str, Any],
        contract: Mapping[str, Any],
        request: AgentRequest,
    ) -> dict[str, Any]:
        review = str(contract.get("review_boundary", ""))
        if scenario_id == "student_learning_path_v1":
            return self._student_fields(data, evidence, review)
        if scenario_id == "department_knowledge_governance_v1":
            return self._governance_fields(data, evidence, review, request)
        if scenario_id == "research_frontier_radar_v1":
            return self._research_fields(data, evidence, review, request.input_text())
        if scenario_id == "faculty_course_copilot_v1":
            return self._lesson_fields(data, evidence, review)
        if scenario_id == "assessment_diagnosis_v1":
            return self._assignment_fields(data, evidence, review)
        if scenario_id == "rubric_generation_v1":
            return self._rubric_fields(data, review)
        if scenario_id == "academic_text_diagnostic_solver_v1":
            return self._academic_text_diagnostic_fields(data, review)
        if scenario_id.startswith("academic_visual_"):
            return self._academic_visual_fields(data, review)
        return {"evidence": evidence, "review_boundary": review}

    @staticmethod
    def _rubric_fields(
        data: Mapping[str, Any], review: str
    ) -> dict[str, Any]:
        answer = str(data.get("final_answer") or data.get("answer_text") or "")
        dimensions = ("代码规范性", "资源占用率", "功能完整性", "防抖动处理")
        levels = ("优秀", "良好", "及格", "不及格")
        has_student_score = bool(
            re.search(
                r"(?:学生|该生).{0,16}(?:得分|总分|成绩)\s*[:：=]?\s*\d",
                answer,
            )
        )
        return {
            "rubric_dimensions": {
                "status": "available"
                if all(item in answer for item in dimensions)
                else "not_available",
                "source": "final_answer",
            },
            "rubric_levels": {
                "status": "available"
                if all(item in answer for item in levels)
                else "not_available",
                "source": "final_answer",
            },
            "student_score_excluded": {
                "status": "not_available" if has_student_score else "available",
                "source": "answer_policy",
            },
            "review_boundary": review,
        }

    @staticmethod
    def _academic_text_diagnostic_fields(
        data: Mapping[str, Any], review: str
    ) -> dict[str, Any]:
        """Expose only semantic markers actually present in the model answer.

        The text-diagnostic scenario is intentionally conservative: these
        fields are availability envelopes, not generated facts.  Missing
        headings or safety boundaries remain visible as contract gaps.
        """

        answer = str(data.get("final_answer") or data.get("answer_text") or "")

        def availability(markers: tuple[str, ...]) -> dict[str, str]:
            return {
                "status": "available"
                if any(marker.casefold() in answer.casefold() for marker in markers)
                else "not_available",
                "source": "final_answer",
            }

        return {
            "observation_summary": availability(
                (
                    "VCC",
                    "集电极直流电位",
                    "顶部削峰",
                    "输出漂移",
                    "输出电压",
                    "随时间线性漂移",
                    "最终饱和",
                )
            ),
            "operating_region": availability(("截止区", "饱和区", "放大区")),
            "candidate_causes": availability(("可能原因", "原因一", "原因1")),
            "diagnostic_steps": availability(
                ("验证步骤", "验证：", "验证实验", "实验验证", "验证方案")
            ),
            "safety_boundary": availability(
                ("安全边界", "断电", "电源范围", "数据手册")
            ),
            "nonideality_diagnosis": availability(
                ("非理想", "输入失调", "偏置电流", "漏电", "漂移")
            ),
            "compensation_component": availability(
                (
                    "泄放电阻",
                    "并联电阻",
                    "补偿元件",
                    "增加电阻",
                    "并联一个",
                    "反馈电容两端",
                    "R_f",
                    "Rf",
                )
            ),
            "review_boundary": review,
        }

    @staticmethod
    def _academic_visual_fields(
        data: Mapping[str, Any], review: str
    ) -> dict[str, Any]:
        vision = data.get("vision_execution")
        vision = dict(vision) if isinstance(vision, Mapping) else {}
        acceptance = vision.get("visual_acceptance")
        acceptance = (
            dict(acceptance) if isinstance(acceptance, Mapping) else None
        )
        answer = str(data.get("final_answer") or data.get("answer_text") or "")
        answer_available = not any(
            marker in answer for marker in ("当前题目信息缺失", "无法唯一求解")
        )

        def availability(status: str, *, source: str) -> dict[str, Any]:
            return {"status": status, "source": source}

        has_piecewise = answer_available and bool(
            re.search(r"分段表达式|begin\s*\{cases\}|y\s*\(\s*t\s*\)", answer)
        )
        has_waveform = answer_available and "波形" in answer
        has_breakpoints = answer_available and all(
            re.search(rf"t\s*=\s*{value}\b", answer) for value in (0, 1, 4, 5)
        )
        if str(data.get("scenario_id", "")) == "academic_visual_spectrum_solver_v1":
            return {
                "visual_structure": (
                    vision
                    if vision
                    else ScenarioOutputContractService._not_available(
                        "未获得结构化视觉输出"
                    )
                ),
                "visual_acceptance": (
                    acceptance
                    if acceptance is not None
                    else ScenarioOutputContractService._not_available(
                        "未执行题图视觉验收"
                    )
                ),
                "spectrum_expression": availability(
                    "available"
                    if answer_available and re.search(r"Y\s*\(|频谱|傅里叶", answer)
                    else "not_available",
                    source="final_answer",
                ),
                "frequency_bands": availability(
                    "available"
                    if answer_available and re.search(r"频带|支撑区间|[-−]π", answer)
                    else "not_available",
                    source="final_answer",
                ),
                "center_peak_sign": availability(
                    "available"
                    if answer_available
                    and all(marker in answer for marker in ("中心", "峰值"))
                    else "not_available",
                    source="final_answer",
                ),
                "review_boundary": review,
            }
        if str(data.get("scenario_case_id", "")) != "signal-convolution":
            return {
                "visual_structure": (
                    vision
                    if vision
                    else ScenarioOutputContractService._not_available(
                        "未获得结构化视觉输出"
                    )
                ),
                "visual_acceptance": (
                    acceptance
                    if acceptance is not None
                    else ScenarioOutputContractService._not_available(
                        "未执行题图视觉验收"
                    )
                ),
                "solution": availability(
                    "available" if answer_available else "not_available",
                    source="final_answer",
                ),
                "review_boundary": review,
            }
        return {
            "visual_structure": (
                vision
                if vision
                else ScenarioOutputContractService._not_available(
                    "未获得结构化视觉输出"
                )
            ),
            "visual_acceptance": (
                acceptance
                if acceptance is not None
                else ScenarioOutputContractService._not_available(
                    "未执行题图视觉验收"
                )
            ),
            "piecewise_expression": availability(
                "available" if has_piecewise else "not_available",
                source="final_answer",
            ),
            "waveform": availability(
                "available" if has_waveform else "not_available",
                source="final_answer",
            ),
            "breakpoint_explanation": availability(
                "available" if has_breakpoints else "not_available",
                source="final_answer",
            ),
            "review_boundary": review,
        }

    @staticmethod
    def _not_available(reason: str) -> dict[str, str]:
        return {"status": "not_available", "reason": reason}

    @staticmethod
    def _student_fields(
        data: Mapping[str, Any], evidence: dict[str, Any], review: str
    ) -> dict[str, Any]:
        return {
            "evidence_summary": data.get(
                "evidence_summary",
                ScenarioOutputContractService._not_available(
                    "真实模型未提供证据摘要"
                ),
            ),
            "weak_knowledge_points": data.get(
                "weak_knowledge_points",
                ScenarioOutputContractService._not_available(
                    "真实模型未提供薄弱知识点"
                ),
            ),
            "prerequisite_path": data.get(
                "prerequisite_path",
                ScenarioOutputContractService._not_available(
                    "真实模型未提供前置知识路径"
                ),
            ),
            "staged_plan": data.get(
                "staged_plan",
                ScenarioOutputContractService._not_available(
                    "真实模型未提供阶段学习计划"
                ),
            ),
            "verification_tasks": data.get(
                "verification_tasks",
                ScenarioOutputContractService._not_available(
                    "真实模型未提供验证任务"
                ),
            ),
            "evidence": evidence,
            "review_boundary": review,
        }

    @classmethod
    def _governance_fields(
        cls,
        data: Mapping[str, Any],
        evidence: dict[str, Any],
        review: str,
        request: AgentRequest,
    ) -> dict[str, Any]:
        """Build governance fields strictly from the asset records in input."""

        # Governance is an input-audit contract. Never let a model response or
        # retrieval evidence invent assets that were not present in the request.
        inventory = cls._assets_from_request(request)
        if not inventory:
            return {
                "asset_inventory": cls._not_available("输入中未提供资产记录"),
                "version_conflicts": cls._not_available("未提供可核验的资产版本清单"),
                "source_audit": cls._not_available("输入中未提供资产来源"),
                "approval_status": cls._not_available(
                    "未提供审批记录，不能标记为已批准"
                ),
                "publication_blockers": [
                    "缺少可核验的版本清单",
                    "缺少来源所有者和审批记录",
                    "发布前必须由授权教师或管理员复核",
                ],
                "traceability_links": [],
                "publication_checklist_before": [
                    "补齐资产清单、来源、审批状态和可追溯链接"
                ],
                "publication_checklist_after": ["核对已发布版本与访问权限"],
                "rollback_checklist": ["恢复到已批准且可追溯的上一版本"],
                "review_boundary": review,
            }
        names = [
            str(item.get("title", "未知资产"))
            for item in inventory
            if isinstance(item, Mapping)
        ]
        missing = (
            [f"{name}：来源" for name in names]
            + [f"{name}：最近审批状态" for name in names]
            + [f"{name}：可追溯链接" for name in names]
        )
        return {
            "asset_inventory": inventory or cls._not_available("输入中未提供资产记录"),
            "version_conflicts": cls._version_audit(inventory),
            "source_audit": {
                "status": "unknown",
                "sources": [{"asset": name, "source": "未知"} for name in names],
                "missing": missing,
            },
            "approval_status": {
                "status": "unknown",
                "by_asset": [
                    {"asset": name, "last_approval_status": "未知"} for name in names
                ],
                "missing": "输入中未提供审批记录、审批人或权限信息",
            },
            "publication_blockers": [
                "来源、最近审批状态和可追溯链接未知",
                "讲义与练习题包的版本配套关系尚未核对",
                "发布权限、审批人和审批记录未提供",
                "未经授权教师或管理员复核不得发布",
            ],
            "traceability_links": [
                {"asset": name, "link": "未知"} for name in names
            ],
            "publication_checklist_before": [
                "核对每项资产标题、版本号与配套关系",
                "补齐来源、审批状态、审批人/权限和可追溯链接",
                "教师复核讲义与练习题包内容一致后再提交发布",
            ],
            "publication_checklist_after": [
                "核对发布版本、可见范围和访问权限",
                "记录发布人、时间、版本与追溯链接",
                "抽查讲义与练习题包可访问且版本一致",
            ],
            "rollback_checklist": [
                "冻结当前发布并记录触发原因",
                "恢复到已批准且可追溯的上一版本",
                "复核回滚后的权限、链接和课程引用",
            ],
            "review_boundary": review,
        }

    @staticmethod
    def _assets_from_request(request: AgentRequest) -> list[dict[str, str]]:
        pattern = re.compile(
            r"(讲义|练习题包|教师修订说明)\s*(?:《([^》]+)》\s*)?v\s*(\d+(?:\.\d+)?)",
            re.IGNORECASE,
        )
        assets: list[dict[str, str]] = []
        for kind, title, version in pattern.findall(request.input_text()):
            assets.append(
                {
                    "asset_type": kind,
                    "title": title.strip() or kind,
                    "version": f"v{version}",
                    "source": "未知",
                    "last_approval_status": "未知",
                    "traceability_link": "未知",
                }
            )
        return assets

    @staticmethod
    def _version_audit(inventory: list[Any]) -> dict[str, Any]:
        if len(inventory) < 2:
            return {"status": "not_determinable", "items": []}
        pairs: list[dict[str, Any]] = []
        for index, left in enumerate(inventory[:-1]):
            for right in inventory[index + 1 :]:
                if not isinstance(left, Mapping) or not isinstance(right, Mapping):
                    continue
                pairs.append(
                    {
                        "assets": [
                            {
                                "title": str(left.get("title", "未知")),
                                "version": str(left.get("version", "未知")),
                            },
                            {
                                "title": str(right.get("title", "未知")),
                                "version": str(right.get("version", "未知")),
                            },
                        ],
                        "finding": (
                            "版本号不同不能单独证明内容冲突，需核对发布时间、配套关系和引用范围"
                        ),
                    }
                )
        return {
            "status": "possible_conflict_needs_review",
            "items": pairs,
            "missing": ["发布时间", "配套关系", "内容引用范围"],
        }

    @staticmethod
    def _research_fields(
        data: Mapping[str, Any],
        evidence: dict[str, Any],
        review: str,
        query: str,
    ) -> dict[str, Any]:
        external = data.get("external_retrieval")
        if not isinstance(external, Mapping):
            external = {}
        items = external.get("items", [])
        if not isinstance(items, list):
            items = []
        external_review_status = ScenarioOutputContractService._external_review_status(
            external
        )
        table = [
            {
                "title": item.get("title", ""),
                "published_at": item.get("published_at", ""),
                "doi": item.get("doi", ""),
                "arxiv_id": item.get("arxiv_id", ""),
                "url": item.get("canonical_url", ""),
                "source_ref": item.get("source_ref", ""),
                # Item-level status is not an authoritative review decision.
                # Only a consistent aggregate review envelope can promote all
                # displayed items to approved evidence.
                "evidence_status": (
                    "approved"
                    if external_review_status == "approved"
                    else "candidate"
                ),
            }
            for item in items
            if isinstance(item, Mapping)
        ]
        identifiers = [
            value
            for item in table
            for value in (item.get("doi"), item.get("arxiv_id"))
            if value
        ]
        displayed_items = table or evidence.get("items", [])
        item_count = len(displayed_items) if isinstance(displayed_items, list) else 0
        evidence_status = str(evidence.get("status", "insufficient"))
        if item_count == 0:
            evidence_status = "insufficient"
        raw_summary = data.get("evidence_summary")
        evidence_summary = (
            dict(raw_summary) if isinstance(raw_summary, Mapping) else {}
        )
        # The result-level evidence status is authoritative. Do not let a
        # model-provided summary claim sufficient evidence after filtering has
        # removed every candidate.
        evidence_summary.update(
            {"status": evidence_status, "item_count": item_count}
        )
        research_quality = ScenarioOutputContractService._research_quality(
            query, items
        )
        raw_limitations = data.get("limitations")
        limitations = (
            [str(item) for item in raw_limitations if str(item).strip()]
            if isinstance(raw_limitations, list)
            else []
        )
        for limitation in research_quality["limitations"]:
            if limitation not in limitations:
                limitations.append(limitation)
        return {
            "research_scope": data.get(
                "research_scope",
                {
                    "status": "bounded_by_user_prompt",
                    "time_range": "按示例问题指定时间窗筛选；未扩大时间范围。",
                },
            ),
            "evidence_table": displayed_items,
            "doi_or_arxiv": identifiers,
            "evidence_summary": evidence_summary,
            "open_questions": data.get(
                "open_questions", ["未通过相关性和原文核验的候选结果不能作为最终证据。"]
            ),
            "limitations": limitations
            or ["摘要、标识和链接必须由研究人员打开原文复核。"],
            "research_evidence_quality": research_quality,
            "review_boundary": review,
        }

    @staticmethod
    def _research_quality(query: str, items: list[Any]) -> dict[str, Any]:
        """Check evidence completeness without inferring paper facts."""

        requested_minimum = _requested_research_count(query)
        if not items:
            return {
                "status": "insufficient",
                "item_count": 0,
                "identifier_count": 0,
                "dated_count": 0,
                "source_count": 0,
                "requested_minimum": requested_minimum,
                "missing": ["至少一条可核验外部证据"],
                "limitations": ["当前没有可核验外部证据，不能形成研究结论。"],
            }

        identifier_count = sum(
            int(
                isinstance(item, Mapping)
                and bool(str(item.get("doi") or item.get("arxiv_id") or "").strip())
            )
            for item in items
        )
        dated_count = sum(
            int(
                isinstance(item, Mapping)
                and bool(
                    str(
                        item.get("published_at")
                        or item.get("updated_at")
                        or ""
                    ).strip()
                )
            )
            for item in items
        )
        source_count = sum(
            int(
                isinstance(item, Mapping)
                and bool(
                    str(
                        item.get("source_ref")
                        or item.get("canonical_url")
                        or item.get("url")
                        or ""
                    ).strip()
                )
            )
            for item in items
        )
        normalized_query = query.casefold()
        requires_identifier = any(
            marker in normalized_query
            for marker in (
                "doi",
                "arxiv",
                "唯一标识",
                "可核验一手论文",
                "论文",
                "文献",
                "paper",
                "publication",
            )
        )
        missing: list[str] = []
        if requested_minimum is not None and len(items) < requested_minimum:
            missing.append(f"至少 {requested_minimum} 条证据（当前 {len(items)} 条）")
        if requires_identifier and identifier_count < len(items):
            missing.append("每条论文证据的 DOI 或 arXiv 标识")
        if dated_count < len(items):
            missing.append("每条证据的可核验发布日期")
        if source_count < len(items):
            missing.append("每条证据的来源链接或来源引用")
        limitations = ["摘要级证据不能替代原文、实验条件和定量结果核验。"]
        if missing:
            limitations.append("证据完整性缺口：" + "；".join(missing) + "。")
        return {
            "status": "sufficient" if not missing else "partial",
            "item_count": len(items),
            "identifier_count": identifier_count,
            "dated_count": dated_count,
            "source_count": source_count,
            "requested_minimum": requested_minimum,
            "missing": missing,
            "limitations": limitations,
        }

    @staticmethod
    def _external_review_status(external: Mapping[str, Any]) -> str:
        """Derive review status from an internally consistent evidence envelope.

        ``review_status`` is metadata that can be copied into an Agent result;
        it is not sufficient by itself to authorize publication.  The approved
        count must cover every displayed item.  This mirrors the Runtime
        external-research gate and prevents a result from claiming approval
        while omitting or falsifying its accounting metadata.
        """

        status = str(external.get("review_status", "not_run")).strip().casefold()
        raw_items = external.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            if status in {"not_run", "rejected", "failed"}:
                # An empty list can mean that candidates were deliberately
                # withheld pending review. Preserve that state instead of
                # presenting it as if external evidence was never attempted.
                return status
            return "not_applicable"
        items = [item for item in raw_items if isinstance(item, Mapping)]
        if len(items) != len(raw_items):
            return "incomplete"
        if status in {"not_run", "rejected", "failed"}:
            return status
        approved_count = external.get("approved_count")
        if isinstance(approved_count, bool) or not isinstance(approved_count, int):
            return "incomplete"
        if status == "approved" and approved_count == len(items):
            return "approved"
        return "incomplete"

    @staticmethod
    def _lesson_fields(
        data: Mapping[str, Any], evidence: dict[str, Any], review: str
    ) -> dict[str, Any]:
        return {
            "learning_objectives": data.get(
                "learning_objectives",
                ScenarioOutputContractService._not_available(
                    "内部备课结果未提供学习目标"
                ),
            ),
            "lesson_flow": data.get(
                "lesson_flow",
                ScenarioOutputContractService._not_available(
                    "内部备课结果未提供课堂流程"
                ),
            ),
            "common_misconceptions": data.get(
                "common_misconceptions",
                ScenarioOutputContractService._not_available(
                    "需要教师结合学情补充常见误区"
                ),
            ),
            "differentiated_practice": data.get(
                "differentiated_practice",
                ScenarioOutputContractService._not_available(
                    "需要教师确认分层练习难度"
                ),
            ),
            "evidence": evidence,
            "review_boundary": review,
        }

    @staticmethod
    def _assignment_fields(
        data: Mapping[str, Any], evidence: dict[str, Any], review: str
    ) -> dict[str, Any]:
        concept_correction = data.get("concept_correction")
        if concept_correction in (None, "", [], {}):
            correction_text = str(
                data.get("correction") or data.get("teacher_feedback") or ""
            ).strip()
            if correction_text:
                concept_correction = {
                    "status": "available",
                    "content": correction_text,
                    "source": "teacher_feedback",
                }
            else:
                concept_correction = ScenarioOutputContractService._not_available(
                    "未提供概念纠正"
                )
        return {
            "first_error": data.get(
                "first_error",
                data.get(
                    "errors",
                    ScenarioOutputContractService._not_available(
                        "未提供可定位的首个错误"
                    ),
                ),
            ),
            "error_cause": data.get(
                "error_cause",
                ScenarioOutputContractService._not_available("未提供错误原因分析"),
            ),
            "preserved_correct_steps": data.get(
                "preserved_correct_steps",
                data.get(
                    "correct_parts",
                    ScenarioOutputContractService._not_available(
                        "未提供已确认的正确步骤"
                    ),
                ),
            ),
            "tiered_hints": data.get(
                "tiered_hints",
                data.get(
                    "hints",
                    ScenarioOutputContractService._not_available("未提供分层提示"),
                ),
            ),
            "verification_problem": data.get(
                "verification_problem",
                data.get(
                    "next_check",
                    ScenarioOutputContractService._not_available("未生成验证题"),
                ),
            ),
            "concept_correction": concept_correction,
            "verification_task": data.get(
                "verification_task",
                data.get(
                    "verification_problem",
                    data.get(
                        "next_check",
                        ScenarioOutputContractService._not_available(
                            "未生成验证任务"
                        ),
                    ),
                ),
            ),
            "evidence": evidence,
            "review_boundary": review,
        }

    @staticmethod
    def _evidence(result: AgentResult) -> dict[str, Any]:
        packet = result.structured_result.get("evidence_packet", {})
        raw_items: Any = (
            packet.get("sources", []) if isinstance(packet, Mapping) else []
        )
        if not raw_items:
            knowledge = result.structured_result.get("knowledge", {})
            raw_items = (
                knowledge.get("hits", []) if isinstance(knowledge, Mapping) else []
            )
        if not isinstance(raw_items, list):
            raw_items = []
        items = [
            {
                "title": str(item.get("title") or item.get("chapter") or "课程资料"),
                "source_ref": str(
                    item.get("source_ref") or item.get("source_id") or ""
                ),
                "content_type": str(item.get("content_type") or "unknown"),
                "summary": str(
                    item.get("content_excerpt") or item.get("excerpt") or ""
                ),
            }
            for item in raw_items
            if isinstance(item, Mapping)
        ]
        source_refs = list(
            dict.fromkeys(
                [str(item["source_ref"]) for item in items if item.get("source_ref")]
                + [str(ref) for ref in result.citations if str(ref)]
            )
        )
        return {
            "status": str(result.evidence_status or "insufficient"),
            "source_refs": source_refs,
            "items": items,
            "note": (
                "仅使用实际返回的资料卡片；没有资料时不得生成外部引用。"
                if not items
                else "资料卡片需要结合标题、类型、摘要和来源链接人工复核。"
            ),
        }

    @staticmethod
    def _label(request: AgentRequest) -> str:
        scenario_id = str(
            request.options.get("scenario_id") or request.scenario_id or ""
        )
        return ScenarioOutputContractService._LABELS.get(scenario_id, "场景任务")

    @staticmethod
    def _append_contract_answer(
        answer: str, label: str, fields: Mapping[str, Any], review_boundary: str
    ) -> str:
        if "场景结构化输出" in answer:
            return answer
        del fields
        lines = [
            answer.rstrip(),
            "",
            f"## {label} · 场景结构化输出",
            "详细字段已同步到结构化结果和结果面板，避免在正文中重复序列化。",
        ]
        if review_boundary:
            lines.extend(["### review_boundary", review_boundary])
        return "\n".join(lines).strip()
