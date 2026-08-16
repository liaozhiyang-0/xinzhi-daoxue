from __future__ import annotations

import json
import re
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
        if "external_retrieval" in result.structured_result:
            data.setdefault(
                "external_retrieval",
                result.structured_result.get("external_retrieval"),
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
        model_synthesis_required = governance and (
            result.structured_result.get("mode") != "governance_model_generation"
        )
        contract_status = (
            "model_synthesis_required"
            if model_synthesis_required
            else (
                "completed_with_gaps"
                if has_unavailable or evidence_status != "sufficient"
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
                else "```json\n"
                + json.dumps(value, ensure_ascii=False, indent=2)
                + "\n```"
            )
            lines.extend([f"### {key}", str(rendered)])
        if review_boundary:
            lines.extend(["### review_boundary", review_boundary])
        return "\n".join(lines).strip()
