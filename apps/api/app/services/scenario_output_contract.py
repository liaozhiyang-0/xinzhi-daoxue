from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.contracts import AgentRequest, AgentResult


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
    }

    def enrich(self, result: AgentResult, request: AgentRequest) -> AgentResult:
        raw_contract = request.options.get("scenario_contract")
        if not isinstance(raw_contract, Mapping):
            return result

        contract = dict(raw_contract)
        expected_agent = str(contract.get("expected_agent", ""))
        if result.fallback_used or expected_agent != result.agent_id:
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
        if "external_retrieval" in result.structured_result:
            data.setdefault(
                "external_retrieval",
                result.structured_result.get("external_retrieval"),
            )
        scenario_id = str(
            request.options.get("scenario_id") or request.scenario_id or ""
        )
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
            if key in data and data[key] not in (None, "")
        ]
        missing_fields = [key for key in expected_output if key not in present_fields]
        has_unavailable = any(
            isinstance(data.get(key), Mapping)
            and data[key].get("status") == "not_available"
            for key in expected_output
        )
        evidence_status = str(
            result.evidence_status or evidence.get("status", "insufficient")
        )
        contract_status = (
            "completed_with_gaps"
            if has_unavailable or evidence_status != "sufficient"
            else "completed"
        )
        result.structured_result["scenario_contract"] = {
            **contract,
            "status": contract_status,
            "scenario_id": scenario_id,
            "presentation_label": self._label(request),
            "present_fields": present_fields,
            "missing_fields": missing_fields,
            "evidence_status": evidence_status,
            "evidence_source_refs": evidence.get("source_refs", []),
        }
        result.structured_result["scenario_id"] = scenario_id
        result.answer = self._append_contract_answer(
            result.answer,
            self._label(request),
            fields,
            str(contract.get("review_boundary", "")),
        )
        return result

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
            return self._governance_fields(data, evidence, review)
        if scenario_id == "research_frontier_radar_v1":
            return self._research_fields(data, evidence, review)
        if scenario_id == "faculty_course_copilot_v1":
            return self._lesson_fields(data, evidence, review)
        if scenario_id == "assessment_diagnosis_v1":
            return self._assignment_fields(data, evidence, review)
        return {"evidence": evidence, "review_boundary": review}

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
                {
                    "status": "partial",
                "basis": (
                    "用户在示例问题中提供了两次作答表现和复测要求；"
                    "系统未获得完整成绩历史。"
                ),
                    "retrieved_source_refs": evidence.get("source_refs", []),
                },
            ),
            "weak_knowledge_points": data.get(
                "weak_knowledge_points",
                [
                    {
                        "knowledge_point": "支路电流参考方向与符号约定",
                        "basis": "示例问题中的符号错误与该知识点直接相关",
                        "confidence": "tentative",
                        "qualification": "这是学习建议，不是正式能力认定。",
                    }
                ],
            ),
            "prerequisite_path": data.get(
                "prerequisite_path",
                [
                    "电流方向与符号约定",
                    "基尔霍夫电流定律（KCL）",
                    "支路/节点方程列写",
                    "带符号结果的量纲与合理性检查",
                ],
            ),
            "staged_plan": data.get(
                "staged_plan",
                [
                    {
                        "day": day,
                        "duration_minutes": 25,
                        "goal": goal,
                        "evidence_to_submit": evidence_to_submit,
                    }
                    for day, goal, evidence_to_submit in (
                        (
                            1,
                            "复习电流方向、参考方向和正负号约定",
                            "用自己的话解释两种参考方向",
                        ),
                        (2, "练习节点电流的正负号判断", "完成 3 道节点符号判断题"),
                        (3, "按固定步骤列写 KCL 方程", "提交 2 道带草稿步骤的 KCL 题"),
                        (
                            4,
                            "检查方程的单位、方向和守恒关系",
                            "逐项标注一次方程检查结果",
                        ),
                        (
                            5,
                            "完成含未知支路电流的综合题",
                            "保留正确步骤并标出首个不确定点",
                        ),
                        (
                            6,
                            "针对错误点做间隔复习和变式练习",
                            "完成 2 道变式题且说明符号选择",
                        ),
                        (7, "进行不看提示的复测", "提交 1 道新题的完整推导和自检清单"),
                    )
                ],
            ),
            "verification_tasks": data.get(
                "verification_tasks",
                [
                    "独立完成一道新的节点电流题，并解释每个电流方向的符号。",
                    "提交完整推导后，用 KCL、单位和结果符号各做一次自检。",
                ],
            ),
            "evidence": evidence,
            "review_boundary": review,
        }

    @classmethod
    def _governance_fields(
        cls, data: Mapping[str, Any], evidence: dict[str, Any], review: str
    ) -> dict[str, Any]:
        inventory = data.get("asset_inventory") or [
            {
                "title": item.get("title", "未命名资料"),
                "source_ref": item.get("source_ref", ""),
                "content_type": item.get("content_type", "unknown"),
            }
            for item in evidence.get("items", [])
        ]
        return {
            "asset_inventory": inventory
            or cls._not_available("当前检索未返回课程资产清单"),
            "version_conflicts": data.get(
                "version_conflicts", cls._not_available("未提供可核验的资产版本清单")
            ),
            "source_audit": data.get(
                "source_audit",
                {
                    "status": evidence.get("status", "insufficient"),
                    "sources": evidence.get("items", []),
                    "missing": "来源所有者、版本和审批记录未在当前证据中提供。",
                },
            ),
            "approval_status": data.get(
                "approval_status",
                cls._not_available("未提供审批记录，不能标记为已批准"),
            ),
            "publication_blockers": data.get(
                "publication_blockers",
                [
                    "缺少可核验的版本清单",
                    "缺少来源所有者和审批记录",
                    "发布前必须由授权教师或管理员复核",
                ],
            ),
            "traceability_links": data.get(
                "traceability_links", evidence.get("source_refs", [])
            ),
            "review_boundary": review,
        }

    @staticmethod
    def _research_fields(
        data: Mapping[str, Any], evidence: dict[str, Any], review: str
    ) -> dict[str, Any]:
        external = data.get("external_retrieval")
        if not isinstance(external, Mapping):
            external = {}
        items = external.get("items", [])
        if not isinstance(items, list):
            items = []
        table = [
            {
                "title": item.get("title", ""),
                "published_at": item.get("published_at", ""),
                "doi": item.get("doi", ""),
                "arxiv_id": item.get("arxiv_id", ""),
                "url": item.get("canonical_url", ""),
                "source_ref": item.get("source_ref", ""),
                "evidence_status": item.get("evidence_status", "candidate"),
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
        return {
            "research_scope": data.get(
                "research_scope",
                {
                    "status": "bounded_by_user_prompt",
                    "time_range": "按示例问题指定时间窗筛选；未扩大时间范围。",
                },
            ),
            "evidence_table": table or evidence.get("items", []),
            "doi_or_arxiv": identifiers,
            "evidence_summary": data.get(
                "evidence_summary",
                {
                    "status": evidence.get("status", "insufficient"),
                    "item_count": len(table),
                },
            ),
            "open_questions": data.get(
                "open_questions", ["未通过相关性和原文核验的候选结果不能作为最终证据。"]
            ),
            "limitations": data.get(
                "limitations", ["摘要、标识和链接必须由研究人员打开原文复核。"]
            ),
            "review_boundary": review,
        }

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
        lines = [answer.rstrip(), "", f"## {label} · 场景结构化输出"]
        for key, value in fields.items():
            if key == "review_boundary":
                continue
            rendered = (
                value
                if isinstance(value, str)
                else json.dumps(value, ensure_ascii=False, indent=2)
            )
            lines.extend([f"### {key}", str(rendered)])
        if review_boundary:
            lines.extend(["### review_boundary", review_boundary])
        return "\n".join(lines).strip()
