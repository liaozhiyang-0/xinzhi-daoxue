from __future__ import annotations

from dataclasses import dataclass

from app.contracts.agent import AgentRequest
from app.contracts.external_retrieval import (
    ExternalRetrievalIntentDecision,
    ExternalRetrievalPolicy,
)


@dataclass(frozen=True, slots=True)
class _SignalGroup:
    category: str
    reason_code: str
    weight: int
    terms: tuple[str, ...]


class ExternalRetrievalIntentRecognizer:
    """Recognize explicit freshness/research needs without another model call."""

    _SIGNALS = (
        _SignalGroup(
            "explicit_request",
            "explicit_web_request",
            3,
            (
                "联网",
                "上网搜索",
                "在线搜索",
                "网络检索",
                "帮我查",
                "搜索一下",
                "检索一下",
                "查找资料",
                "查资料",
                "查论文",
                "找论文",
                "找文献",
                "search online",
                "web search",
                "search the web",
                "look up",
            ),
        ),
        _SignalGroup(
            "research",
            "research_or_literature_request",
            2,
            (
                "论文",
                "文献",
                "研究进展",
                "研究现状",
                "学术研究",
                "参考文献",
                "文献综述",
                "arxiv",
                "doi",
                "literature",
                "research paper",
                "research trend",
                "state of the art",
                "survey paper",
            ),
        ),
        _SignalGroup(
            "citation",
            "source_or_citation_request",
            2,
            (
                "引用来源",
                "出处",
                "来源链接",
                "给出链接",
                "提供来源",
                "citation",
                "cite sources",
                "source link",
            ),
        ),
        _SignalGroup(
            "freshness",
            "freshness_request",
            2,
            (
                "最新",
                "新近",
                "近期",
                "最近的研究",
                "截至",
                "目前主流",
                "目前有哪些",
                "latest",
                "recent",
                "newest",
                "as of",
            ),
        ),
        _SignalGroup(
            "current_facts",
            "current_external_fact",
            3,
            (
                "新闻",
                "实时数据",
                "当前价格",
                "最新价格",
                "当前版本",
                "最新版本",
                "当前政策",
                "最新政策",
                "现行法规",
                "官方文档",
                "current price",
                "current version",
                "current policy",
                "official documentation",
                "real-time",
            ),
        ),
    )

    def classify(
        self,
        request: AgentRequest,
        policy: ExternalRetrievalPolicy,
        *,
        gate_enabled: bool = True,
    ) -> ExternalRetrievalIntentDecision:
        query = self._query(request)
        threshold = policy.intent_score_threshold
        if not query:
            return ExternalRetrievalIntentDecision(
                decision="skip",
                threshold=threshold,
                reason_codes=["empty_query"],
            )
        if not gate_enabled or policy.intent_gate_mode == "always":
            reason = "intent_gate_disabled" if not gate_enabled else "policy_always"
            return ExternalRetrievalIntentDecision(
                decision="retrieve",
                category="agent_intent",
                threshold=threshold,
                reason_codes=[reason],
            )

        normalized = " ".join(query.casefold().split())
        score = 0
        categories: list[str] = []
        reason_codes: list[str] = []
        matched_signals: list[str] = []
        for signal in self._SIGNALS:
            matched = next((term for term in signal.terms if term in normalized), None)
            if matched is None:
                continue
            score += signal.weight
            categories.append(signal.category)
            reason_codes.append(signal.reason_code)
            matched_signals.append(matched)

        if (
            policy.intent_gate_mode == "signals_or_intent"
            and request.intent.value.casefold() in policy.intent_allowlist
        ):
            return ExternalRetrievalIntentDecision(
                decision="retrieve",
                category="agent_intent",
                score=score,
                threshold=threshold,
                reason_codes=["allowlisted_agent_intent", *reason_codes][:8],
                matched_signals=matched_signals[:8],
            )

        if score >= threshold:
            category = next(
                (
                    value
                    for value in (
                        "explicit_request",
                        "current_facts",
                        "research",
                        "citation",
                        "freshness",
                    )
                    if value in categories
                ),
                "research",
            )
            return ExternalRetrievalIntentDecision(
                decision="retrieve",
                category=category,
                score=score,
                threshold=threshold,
                reason_codes=reason_codes[:8],
                matched_signals=matched_signals[:8],
            )

        return ExternalRetrievalIntentDecision(
            decision="skip",
            score=score,
            threshold=threshold,
            reason_codes=["no_external_intent", *reason_codes][:8],
            matched_signals=matched_signals[:8],
        )

    @staticmethod
    def _query(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""
