from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from app.agents.internal import InternalAgentHub
from app.contracts import (
    AgentRequest,
    AgentResult,
    Artifact,
    ArtifactType,
    ExternalEvidenceItem,
    ExternalRetrievalResult,
    ExternalSourceScope,
    RunMetrics,
)
from app.contracts.research import (
    ResearchBriefDraft,
    ResearchFinding,
    ResearchIntentDecision,
    ResearchSourceGroup,
    ResearchSourceKind,
)
from app.services.academic_search_planner import relative_freshness_days
from app.services.external_research_answer import (
    external_search_view,
    filter_research_evidence,
)
from app.services.research_knowledge import ResearchKnowledgeService

logger = logging.getLogger(__name__)
_RELATIVE_DATE_WINDOW_PATTERN = re.compile(
    r"近(?:\d+|[一二三四五六七八九十几]+)\s*年|近年|最近|近期|"
    r"(?:近|过去|最近)\s*(?:\d+|[一二三四五六七八九十几]+)\s*(?:个)?月|"
    r"recent|latest|(?:last|past)\s+(?:few|several|\d+)\s+(?:years?|months?)",
    flags=re.IGNORECASE,
)


class ResearchFrontierService:
    """Turn multi-source evidence into a cited, auditable research brief."""

    agent_id = "RESEARCH_01_ACADEMIC_SEARCH_V1"
    intent_agent_id = "RESEARCH_INTENT_CLASSIFIER_LOCAL_V1"
    brief_agent_id = "RESEARCH_FRONTIER_BRIEF_LOCAL_V1"
    knowledge_agent_id = "RESEARCH_FRONTIER_KNOWLEDGE_LOCAL_V1"

    def __init__(
        self,
        hub: InternalAgentHub,
        research_knowledge: ResearchKnowledgeService | None = None,
    ) -> None:
        self.hub = hub
        self.research_knowledge = research_knowledge

    def available(self) -> bool:
        # The service has a deterministic evidence-grounded fallback, so it is
        # locally runnable even when an optional text model is not configured.
        return True

    async def classify_intent(
        self, request: AgentRequest
    ) -> ResearchIntentDecision | None:
        question = self._question(request)
        if not question:
            return None
        if not self._model_agent_configured(self.intent_agent_id):
            return self._deterministic_intent(question)
        try:
            result = await self.hub.run_text(
                self.intent_agent_id,
                input_text=json.dumps(
                    {
                        "user_query": question[:4000],
                        "previous_intent": request.options.get("research_intent", {}),
                    },
                    ensure_ascii=False,
                ),
                request_id=str(request.options.get("request_id", request.task_id)),
                max_tokens=500,
                extra_options={"_allow_route_fallback": False},
            )
            model_intent = ResearchIntentDecision.model_validate(
                result.structured_result
            )
            return self._merge_deterministic_intent(question, model_intent)
        except Exception:
            logger.warning(
                "research_intent_classification_failed task_id=%s",
                request.task_id,
                exc_info=True,
            )
            return self._deterministic_intent(question)

    async def run(self, request: AgentRequest) -> AgentResult:
        question = self._question(request)
        external = self._external_result(request)
        intent = self._intent(request) or self._deterministic_intent(question)
        evidence = external.items if external is not None else []
        filtered_evidence = filter_research_evidence(question, evidence)
        if external is not None and len(filtered_evidence) != len(evidence):
            external = external.model_copy(
                update={
                    "items": filtered_evidence,
                    "warnings": [
                        *external.warnings,
                        "cross-topic evidence was removed before generation",
                    ][:20],
                }
            )
        evidence = filtered_evidence
        evidence_status = self._evidence_status(evidence)
        answer_mode = "external_retrieval"
        # A failed/empty external retrieval is a verified absence signal for
        # this request. Do not silently replace it with semantically similar
        # historical evidence, which can reintroduce a prior domain. Local
        # research evidence is only a fallback when no external retrieval was
        # attempted at all.
        if not evidence and external is None and self.research_knowledge is not None:
            try:
                evidence = await self.research_knowledge.search_evidence(question)
            except Exception:
                logger.warning(
                    "research_local_knowledge_restore_failed task_id=%s",
                    request.task_id,
                    exc_info=True,
                )
            evidence = filter_research_evidence(question, evidence)
            if evidence:
                answer_mode = "local_research_knowledge"
                external = ExternalRetrievalResult(
                    query=question,
                    normalized_query=question,
                    source_scopes=[ExternalSourceScope.ACADEMIC],
                    items=evidence,
                    status="partial",
                    warnings=[
                        "evidence restored from local research knowledge base"
                    ],
                )
        model_metadata: dict[str, Any]
        if not evidence:
            brief = self._no_verified_evidence_brief(question)
            model_metadata = {"status": "no_external_evidence", "model_calls": 0}
            answer = self.render(brief, [], external)
            return AgentResult(
                agent_id=self.agent_id,
                provider="local_agent",
                answer=answer,
                structured_result={
                    "status": "completed",
                    "answer_mode": (
                        "no_verified_evidence"
                        if answer_mode == "external_retrieval"
                        else answer_mode
                    ),
                    "research_intent": intent.model_dump(mode="json"),
                    "research_brief": brief.model_dump(mode="json"),
                    "external_references": [],
                    "external_retrieval": (
                        external.model_dump(mode="json") if external is not None else {}
                    ),
                    "external_search_view": [],
                    "evidence_summary": {
                        "status": evidence_status,
                        "item_count": len(evidence),
                    },
                    "model_execution": model_metadata,
                },
                warnings=[],
                confidence=0.15,
                evidence_status="insufficient",
                cloud_status="not_required",
                metrics=RunMetrics(
                    model_calls=int(model_metadata.get("model_calls", 0)),
                    provider_latency_ms=int(model_metadata.get("elapsed_ms", 0)),
                ),
            )

        assert external is not None
        evidence_context = self._evidence_context(evidence)
        prompt = json.dumps(
            {
                "user_query": question[:4000],
                "research_intent": intent.model_dump(mode="json"),
                "retrieval_status": (
                    external.status if external is not None else "failed"
                ),
                "retrieved_at": [item.retrieved_at.isoformat() for item in evidence],
                "evidence": evidence_context,
                "requirements": [
                    "先阅读每条证据的title、abstract/excerpt和published_at，再综合回答用户问题",
                    "不要复用上一轮会话的领域、答案或证据；必须直接回答本轮用户问题和时间范围",
                    "按当前主题归纳有证据支持的进展、方法、应用或局限；不要套用固定学科分类",
                    "每条关键发现都必须引用一个或多个输入中的evidence_id",
                    "不要把来源数量、检索过程或论文标题本身当作核心结论；核心结论必须说明进展是什么以及为什么重要",
                    "只能使用输入证据支持的事实，不得补造论文、作者、日期、数值或实验结果；证据不足时明确说明限制",
                ],
            },
            ensure_ascii=False,
        )
        try:
            internal = await self.hub.run_text(
                self.brief_agent_id,
                input_text=prompt,
                request_id=str(request.options.get("request_id", request.task_id)),
                max_tokens=5000,
                extra_options={"_allow_route_fallback": True},
            )
            brief = ResearchBriefDraft.model_validate(internal.structured_result)
            brief = self._sanitize_brief(brief, evidence)
            if self._brief_exceeds_requested_date_scope(question, brief):
                logger.warning(
                    "research_brief_date_scope_exceeded task_id=%s; "
                    "using evidence fallback",
                    request.task_id,
                )
                brief = self._fallback_brief(question, intent, evidence, external)
                model_metadata = {
                    **self._execution_metadata(internal),
                    "status": "fallback_date_scope",
                }
            else:
                model_metadata = self._execution_metadata(internal)
        except Exception:
            logger.warning(
                "research_brief_generation_failed task_id=%s",
                request.task_id,
                exc_info=True,
            )
            brief = self._fallback_brief(question, intent, evidence, external)
            model_metadata = {"status": "fallback", "model_calls": 0}

        answer = self.render(brief, evidence, external)
        artifact = Artifact(
            artifact_type=ArtifactType.REPORT,
            owner_id=request.user_id,
            task_id=request.task_id,
            course_id=request.course_id,
            content={
                "research_brief": brief.model_dump(mode="json"),
                "research_intent": intent.model_dump(mode="json"),
                "answer_mode": answer_mode,
                "external_references": [item.evidence_id for item in evidence],
                "external_search_view": external_search_view(external),
            },
            source_refs=[str(item.canonical_url) for item in evidence],
        )
        return AgentResult(
            agent_id=self.agent_id,
            provider="local_agent",
            answer=answer,
            structured_result={
                "status": "completed",
                "answer_mode": answer_mode,
                "research_intent": intent.model_dump(mode="json"),
                "research_brief": brief.model_dump(mode="json"),
                "external_references": [item.evidence_id for item in evidence],
                "external_retrieval": (
                    external.model_dump(mode="json") if external is not None else {}
                ),
                "external_search_view": external_search_view(external),
                "evidence_summary": {
                    "status": evidence_status,
                    "item_count": len(evidence),
                },
                "model_execution": model_metadata,
            },
            artifacts=[artifact],
            citations=[str(item.canonical_url) for item in evidence],
            warnings=list(external.warnings) if external is not None else [],
            confidence=0.82 if evidence else 0.3,
            metrics=RunMetrics(
                provider_latency_ms=int(model_metadata.get("elapsed_ms", 0)),
                model_calls=int(model_metadata.get("model_calls", 0)),
                input_tokens=model_metadata.get("input_tokens"),
                output_tokens=model_metadata.get("output_tokens"),
            ),
            evidence_status=evidence_status,
            cloud_status="not_required",
        )

    @staticmethod
    def _evidence_status(evidence: list[ExternalEvidenceItem]) -> str:
        if not evidence:
            return "insufficient"
        return "sufficient" if len(evidence) >= 3 else "partial"

    @staticmethod
    def render(
        brief: ResearchBriefDraft,
        evidence: list[ExternalEvidenceItem],
        external: ExternalRetrievalResult | None,
    ) -> str:
        lines = [
            f"# {brief.title}",
            f"**检索范围**：{brief.scope}",
            "",
            "## 核心结论",
            brief.executive_summary,
            "",
            "## 关键发现",
        ]
        for index, finding in enumerate(brief.key_findings, start=1):
            refs = " ".join(f"[{ref}]" for ref in finding.evidence_ids)
            suffix = f" {refs}" if refs else "（证据不足，需复核）"
            lines.append(
                f"{index}. **{finding.claim}**{suffix}\n"
                f"   - 意义：{finding.why_it_matters or '待结合原文进一步判断'}\n"
                f"   - 置信度：{finding.confidence}"
            )
        if brief.source_landscape:
            lines.extend(["", "## 来源结构"])
            for group in brief.source_landscape:
                refs = " ".join(f"[{ref}]" for ref in group.evidence_ids)
                lines.append(
                    f"- {group.category}：{group.count} 条。{group.note} {refs}".strip()
                )
        if brief.timeline:
            lines.extend(["", "## 时间线"])
            for item in brief.timeline:
                refs = " ".join(f"[{ref}]" for ref in item.evidence_ids)
                lines.append(f"- **{item.date_label}**：{item.event} {refs}".strip())
        return "\n".join(lines)

    @staticmethod
    def _question(request: AgentRequest) -> str:
        for key in ("text", "question", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return "科研前沿研究进展"

    @staticmethod
    def _external_result(request: AgentRequest) -> ExternalRetrievalResult | None:
        value = request.options.get("external_retrieval")
        if not isinstance(value, dict):
            return None
        try:
            return ExternalRetrievalResult.model_validate(value)
        except Exception:
            return None

    @staticmethod
    def _intent(request: AgentRequest) -> ResearchIntentDecision | None:
        value = request.options.get("research_intent")
        if not isinstance(value, dict):
            return None
        try:
            return ResearchIntentDecision.model_validate(value)
        except Exception:
            return None

    @staticmethod
    def _evidence_context(items: list[ExternalEvidenceItem]) -> list[dict[str, Any]]:
        return [
            {
                "evidence_id": item.evidence_id,
                "source_type": item.source_type.value,
                "provider": item.provider,
                "title": item.title,
                "authors": item.authors[:8],
                "venue": item.venue,
                "published_at": (
                    item.published_at.isoformat() if item.published_at else None
                ),
                "url": str(item.canonical_url),
                "excerpt": item.content_excerpt[:3500],
                "metadata": item.metadata,
            }
            for item in items
        ]

    @staticmethod
    def _sanitize_brief(
        brief: ResearchBriefDraft, evidence: list[ExternalEvidenceItem]
    ) -> ResearchBriefDraft:
        allowed = {item.evidence_id for item in evidence}
        findings: list[ResearchFinding] = []
        for item in brief.key_findings:
            refs = [ref for ref in item.evidence_ids if ref in allowed]
            # A key finding without a surviving source reference is not an
            # evidence-grounded finding. Dropping it prevents the generator
            # from presenting an unsupported claim with high confidence.
            if not refs:
                continue
            findings.append(item.model_copy(update={"evidence_ids": refs}))
        if not findings and evidence:
            findings = [
                ResearchFrontierService._fallback_finding(evidence[0], brief.scope)
            ]
        groups = [
            item.model_copy(
                update={
                    "evidence_ids": [ref for ref in item.evidence_ids if ref in allowed]
                }
            )
            for item in brief.source_landscape
        ]
        timeline = [
            item.model_copy(
                update={
                    "evidence_ids": [ref for ref in item.evidence_ids if ref in allowed]
                }
            )
            for item in brief.timeline
        ]
        return brief.model_copy(
            update={
                "key_findings": findings,
                "source_landscape": groups,
                "timeline": timeline,
            }
        )

    @staticmethod
    def _brief_exceeds_requested_date_scope(
        question: str, brief: ResearchBriefDraft
    ) -> bool:
        """Reject generated date claims outside the user-requested window."""

        normalized = "\n".join(
            [
                brief.executive_summary,
                *(item.claim for item in brief.key_findings),
                *(item.why_it_matters for item in brief.key_findings),
                *(item.note for item in brief.source_landscape),
                *(item.date_label for item in brief.timeline),
                *(item.event for item in brief.timeline),
                *brief.open_questions,
                *brief.next_steps,
                *brief.limitations,
            ]
        )
        years = {int(value) for value in re.findall(r"20\d{2}", normalized)}
        if not years:
            return False
        explicit_years = sorted(
            {int(value) for value in re.findall(r"20\d{2}", question)}
        )
        if len(explicit_years) >= 2:
            return any(
                year < explicit_years[0] or year > explicit_years[-1]
                for year in years
            )
        if not _RELATIVE_DATE_WINDOW_PATTERN.search(question):
            return False
        now = datetime.now(UTC)
        start = now - timedelta(days=relative_freshness_days(question))
        return any(year < start.year or year > now.year for year in years)

    @classmethod
    def _fallback_brief(
        cls,
        question: str,
        intent: ResearchIntentDecision,
        evidence: list[ExternalEvidenceItem],
        external: ExternalRetrievalResult | None,
    ) -> ResearchBriefDraft:
        findings = [cls._fallback_finding(item, question) for item in evidence[:5]]
        groups: dict[ResearchSourceKind, list[ExternalEvidenceItem]] = {}
        for item in evidence:
            kind: ResearchSourceKind = (
                "academic_paper"
                if item.source_type.value == "academic_paper"
                else "conference"
                if item.metadata.get("category") == "conference"
                else "web_report"
            )
            groups.setdefault(kind, []).append(item)
        source_groups = [
            ResearchSourceGroup(
                category=kind,
                count=len(items),
                evidence_ids=[item.evidence_id for item in items],
                note="由检索源返回，正式引用前需人工核验",
            )
            for kind, items in groups.items()
        ]
        fallback_findings = findings or [
            ResearchFinding(
                claim="当前证据不足以形成稳定的关键进展判断",
                evidence_ids=[],
                why_it_matters="需要扩大来源或补充全文核验",
                confidence="low",
            )
        ]
        brief = ResearchBriefDraft(
            title="科研前沿证据简报",
            scope=question,
            executive_summary=(
                f"围绕“{question}”生成候选证据摘要："
                f"{('、'.join(item.claim for item in fallback_findings[:3]))}。"
            ),
            key_findings=fallback_findings,
            source_landscape=source_groups,
        )
        return brief.model_copy(
            update={
                "executive_summary": (
                    f"围绕“{question}”检索到 {len(evidence)} 条候选证据。"
                    "以下内容仅依据来源标题和摘要整理，正式结论仍需核验原文。"
                ),
                "key_findings": findings
                or [
                    ResearchFinding(
                        claim=f"当前证据不足以形成“{question}”的稳定进展判断",
                        evidence_ids=[],
                        why_it_matters="需要补充相关来源或全文核验。",
                        confidence="low",
                    )
                ],
            }
        )

    @staticmethod
    def _no_verified_evidence_brief(question: str) -> ResearchBriefDraft:
        """Return a scoped empty result instead of inventing a domain answer."""

        return ResearchBriefDraft(
            title="科研前沿检索结果",
            scope=question,
            executive_summary=(
                f"当前未获得与“{question}”直接匹配且可核验的外部证据，"
                "暂不生成代表性进展结论。"
            ),
            key_findings=[
                ResearchFinding(
                    claim=f"未找到与“{question}”直接对应的可展示证据",
                    evidence_ids=[],
                    why_it_matters="避免把其他领域的旧结果或本地知识误当作当前问题的结论。",
                    confidence="low",
                )
            ],
            source_landscape=[],
        )

    @staticmethod
    def _legacy_fallback_finding(item: ExternalEvidenceItem) -> ResearchFinding:
        text = f"{item.title} {item.content_excerpt}".casefold()
        if any(
            term in text for term in ("电子皮肤", "传感器", "sensor", "sensing")
        ):
            claim = "多功能传感器与电子皮肤推动柔性器件向人体界面应用发展"
            why = (
                "检索内容直接涉及柔性传感、热感知或电子皮肤，说明器件正在从单点感知"
                "扩展到贴合人体的多功能信息采集。"
            )
        elif any(
            term in text
            for term in ("bist", "igzo", "tft", "mixed-signal", "电路")
        ):
            claim = "柔性电子从单个器件性能提升走向薄膜晶体管和混合信号电路级集成与测试"
            why = (
                "检索内容涉及柔性电子中的薄膜晶体管、混合信号电路或测试方法，"
                "反映出系统级可靠性与可测试性成为新重点。"
            )
        elif any(
            term in text
            for term in ("印刷", "manufactur", "封装", "reliab", "可靠性")
        ):
            claim = "制造工艺、封装和可靠性成为柔性器件规模化落地的关键约束"
            why = (
                "检索内容涉及制造、封装或可靠性问题，说明研究重点已从实验室器件"
                "延伸到长期稳定运行和批量制备。"
            )
        else:
            claim = "柔性电子器件持续向可弯折、低功耗和系统集成方向演进"
            why = item.content_excerpt[:240] or item.title
        return ResearchFinding(
            claim=claim,
            evidence_ids=[item.evidence_id],
            why_it_matters=why,
            confidence="medium",
        )

    @staticmethod
    def _fallback_finding(
        item: ExternalEvidenceItem, question: str
    ) -> ResearchFinding:
        """Keep a generation failure evidence-grounded and topic-neutral."""

        title = item.title.strip()[:220]
        excerpt = item.content_excerpt.strip()[:240]
        return ResearchFinding(
            claim=f"来源《{title}》与当前主题“{question[:120]}”相关，提供了一条候选研究证据",
            evidence_ids=[item.evidence_id],
            why_it_matters=excerpt or "需要打开原文核验其具体结论。",
            confidence="medium",
        )

    async def _local_knowledge_brief(
        self,
        question: str,
        intent: ResearchIntentDecision,
        request: AgentRequest,
    ) -> tuple[ResearchBriefDraft, dict[str, Any]]:
        """Keep the user-facing flow useful when external sources are unavailable."""

        payload = {
            "user_query": question[:4000],
            "research_intent": intent.model_dump(mode="json"),
            "answer_mode": "no_verified_evidence",
            "requirements": [
                "直接回答用户问题，不返回检索失败提示",
                "不要编造论文、作者、期刊、日期、数字或实验结果",
                "每个key_finding的evidence_ids必须为空",
                "明确说明这是本地知识初步回答，外部来源需后续核验",
            ],
        }
        try:
            internal = await self.hub.run_text(
                self.knowledge_agent_id,
                input_text=json.dumps(payload, ensure_ascii=False),
                request_id=str(request.options.get("request_id", request.task_id)),
                max_tokens=4200,
                extra_options={"_allow_route_fallback": True},
            )
            brief = ResearchBriefDraft.model_validate(internal.structured_result)
            brief = brief.model_copy(
                update={
                    "scope": question,
                    "key_findings": [
                        item.model_copy(update={"evidence_ids": []})
                        for item in brief.key_findings
                    ],
                    "source_landscape": [],
                    "timeline": [
                        item.model_copy(update={"evidence_ids": []})
                        for item in brief.timeline
                    ],
                    "limitations": list(
                        dict.fromkeys(
                            [
                                "本回答基于本地模型知识，未使用可核验外部文献作为依据",
                                *brief.limitations,
                            ]
                        )
                    )[:8],
                }
            )
            return brief, self._execution_metadata(internal)
        except Exception:
            return self._local_knowledge_fallback_brief(question, intent), {
                "status": "fallback",
                "model_calls": 0,
            }

    @staticmethod
    def _local_knowledge_fallback_brief(
        question: str, intent: ResearchIntentDecision
    ) -> ResearchBriefDraft:
        # Kept for compatibility with older callers; never emit a hard-coded
        # domain answer when external evidence is unavailable.
        return ResearchFrontierService._no_verified_evidence_brief(question)

        flexible = any(
            term in question.casefold()
            for term in (
                "柔性电子",
                "柔性器件",
                "可拉伸电子",
                "电子皮肤",
                "flexible electronics",
                "stretchable electronics",
            )
        )
        if flexible:
            findings = [
                ResearchFinding(
                    claim="柔性与可拉伸器件从单一传感走向多模态、低功耗和系统级集成",
                    why_it_matters="研究重点已从能否弯曲扩展到在形变、汗液、温度和长期佩戴条件下同时完成感知、信号处理与通信。",
                    confidence="medium",
                ),
                ResearchFinding(
                    claim="电子皮肤、可穿戴生物电子和自供能传感器持续成为重要应用方向",
                    why_it_matters="柔性器件与人体界面结合更紧密，压力、应变、温度、生理信号等多类信息可以在同一系统中采集。",
                    confidence="medium",
                ),
                ResearchFinding(
                    claim="柔性显示、柔性电路、存储与能源器件的异质集成逐步加强",
                    why_it_matters="关键瓶颈从单个器件性能转向器件之间的互连、封装、供能和协同工作。",
                    confidence="medium",
                ),
                ResearchFinding(
                    claim="印刷制造、低温工艺、薄膜材料和可靠性封装成为走向规模化的关键",
                    why_it_matters="实验室样品要进入产品，需要同时解决良率、耐弯折、环境稳定性、皮肤安全和批量制造问题。",
                    confidence="medium",
                ),
            ]
            summary = (
                "近三年的主线不是单一器件指标的孤立提升，而是柔性材料、可拉伸结构、传感/显示/逻辑/能源器件和封装制造共同向系统化演进。"
                "其中最值得关注的是人体贴合的多模态感知、低功耗与自供能、柔性异质集成，以及面向量产的印刷制造和可靠性。"
            )
        else:
            findings = [
                ResearchFinding(
                    claim=f"围绕“{intent.topic}”应优先从材料、器件、系统和应用四个层次梳理进展",
                    why_it_matters="分层检索可以避免把单篇论文或单条报道误认为整个领域的趋势。",
                    confidence="low",
                )
            ]
            summary = (
                f"围绕“{question}”先给出本地知识框架：应分别核对核心材料与器件结构、关键性能、系统集成、应用验证和规模化约束。"
            )
        return ResearchBriefDraft(
            title="科研前沿本地知识初步回答",
            scope=question,
            executive_summary=summary,
            key_findings=findings,
            open_questions=[
                "各项判断需要结合近三年正式论文全文、数据和实验条件进行核验",
                "不同器件路线在耐久性、舒适性、制造成本和可规模化方面仍可能存在差异",
            ],
            next_steps=[
                "按材料与器件结构、传感与人机界面、显示/逻辑/能源、制造与可靠性四条线分别检索",
                "优先核验综述、顶级期刊论文和公开会议资料，再比较不同路线的实验指标",
            ],
            limitations=[
                "本回答基于本地模型知识，未使用可核验外部文献作为依据",
                "未提供具体论文、作者、日期或定量指标，不能替代正式文献综述",
            ],
        )

    @staticmethod
    def _deterministic_intent(question: str) -> ResearchIntentDecision:
        normalized = question.casefold()
        ai_topic = any(
            term in normalized
            for term in (
                "\u4eba\u5de5\u667a\u80fd",
                "\u673a\u5668\u5b66\u4e60",
                "\u6df1\u5ea6\u5b66\u4e60",
                "\u751f\u6210\u5f0f\u4eba\u5de5\u667a\u80fd",
                "\u5927\u6a21\u578b",
                "artificial intelligence",
                "machine learning",
                "deep learning",
                "generative ai",
            )
        )
        conference = any(
            term in normalized
            for term in ("会议", "conference", "workshop", "symposium")
        )
        report = any(
            term in normalized
            for term in ("报道", "新闻", "产业", "report", "news")
        )
        explain = not ai_topic and not any(
            term in normalized
            for term in (
                "最新",
                "进展",
                "论文",
                "文献",
                "报道",
                "会议",
                "研究现状",
                "趋势",
            )
        )
        goal: Literal["explain", "frontier_brief"] = (
            "explain" if explain else "frontier_brief"
        )
        kinds: list[ResearchSourceKind] = ["academic_paper"]
        if report:
            kinds.append("web_report")
        if conference:
            kinds.append("conference")
        if not report and not conference:
            kinds.extend(["web_report", "conference"])
        return ResearchIntentDecision(
            goal=goal,
            topic=question[:300],
            requires_web=not explain,
            source_kinds=kinds[:3],
            research_questions=ResearchFrontierService._research_questions(question),
            reason_codes=["deterministic_fallback"],
            confidence=0.45,
        )

    @classmethod
    def _merge_deterministic_intent(
        cls, question: str, model_intent: ResearchIntentDecision
    ) -> ResearchIntentDecision:
        """Keep model classification while enforcing obvious frontier signals."""

        fallback = cls._deterministic_intent(question)
        if not fallback.requires_web:
            return model_intent

        source_kinds = list(model_intent.source_kinds)
        for source_kind in fallback.source_kinds:
            if source_kind not in source_kinds and len(source_kinds) < 3:
                source_kinds.append(source_kind)
        reason_codes = list(model_intent.reason_codes)
        if "deterministic_frontier_signal" not in reason_codes:
            reason_codes.append("deterministic_frontier_signal")
        return model_intent.model_copy(
            update={
                "goal": (
                    "frontier_brief"
                    if model_intent.goal == "explain"
                    else model_intent.goal
                ),
                "requires_web": True,
                "source_kinds": source_kinds[:3],
                "research_questions": list(
                    dict.fromkeys(
                        [
                            *model_intent.research_questions,
                            *fallback.research_questions,
                        ]
                    )
                )[:6],
                "reason_codes": reason_codes[:8],
                "confidence": max(model_intent.confidence, fallback.confidence),
            }
        )

    @staticmethod
    def _research_questions(question: str) -> list[str]:
        normalized = question.casefold()
        flexible = any(
            term in normalized
            for term in (
                "柔性电子",
                "柔性器件",
                "可拉伸电子",
                "电子皮肤",
                "flexible electronics",
                "stretchable electronics",
            )
        )
        if flexible:
            return [
                f"{question} 材料与器件结构 柔性基底 可拉伸 导电材料",
                f"{question} 传感器 电子皮肤 可穿戴 生物电子",
                f"{question} 柔性显示 柔性电路 晶体管 存储器",
                f"{question} 柔性电池 自供能 能源 器件集成",
                f"{question} 印刷电子 制造工艺 封装 可靠性 规模化",
            ]
        return [
            f"{question} materials and device structure",
            f"{question} system integration and applications",
            f"{question} manufacturing reliability and limitations",
        ]

    @staticmethod
    def _execution_metadata(result: Any) -> dict[str, Any]:
        return {
            "status": "success",
            "agent_id": result.agent_id,
            "task_type": result.task_type,
            "model_route": result.model,
            "elapsed_ms": result.elapsed_ms,
            "model_calls": 2 if "->" in result.model else 1,
            "input_tokens": result.prompt_tokens,
            "output_tokens": result.completion_tokens,
        }

    def _model_agent_configured(self, agent_id: str) -> bool:
        return any(
            item["agent_id"] == agent_id
            and bool(item["configured"])
            and bool(item["enabled"])
            for item in self.hub.list_agents()
        )
