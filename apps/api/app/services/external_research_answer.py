from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from app.contracts.external_retrieval import (
    ExternalEvidenceItem,
    ExternalRetrievalResult,
)

SEARCH_TERMS = (
    "查找",
    "检索",
    "搜索",
    "找一下",
    "推荐",
    "搜集",
    "查询",
    "search",
    "find",
    "lookup",
)
PAPER_TERMS = (
    "论文",
    "文献",
    "研究",
    "paper",
    "papers",
    "publication",
    "literature",
    "article",
)
EXPLICIT_PAPER_TERMS = (
    "论文",
    "文献",
    "paper",
    "papers",
    "publication",
    "literature",
    "article",
)
FRESHNESS_TERMS = (
    "最新",
    "近期",
    "最近",
    "今年",
    "近几年",
    "新发表",
    "latest",
    "recent",
    "newest",
)
RESEARCH_TOPIC_TERMS = (
    "\u67d4\u6027\u7535\u5b50",
    "\u67d4\u6027\u5668\u4ef6",
    "\u795e\u7ecf\u5f62\u6001",
    "\u7535\u5b50\u76ae\u80a4",
    "\u4f20\u611f\u5668",
    "\u8584\u819c\u6676\u4f53\u7ba1",
    "\u5fc6\u963b\u5668",
    "flexible electronics",
    "neuromorphic",
    "electronic skin",
    "wearable",
    "sensor",
    "\u4eba\u5de5\u667a\u80fd",
    "\u673a\u5668\u5b66\u4e60",
    "\u6df1\u5ea6\u5b66\u4e60",
    "\u751f\u6210\u5f0f\u4eba\u5de5\u667a\u80fd",
    "\u5927\u6a21\u578b",
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "generative ai",
    "large language model",
    "foundation model",
)
RESEARCH_ACTION_TERMS = (
    "\u5173\u952e\u8fdb\u5c55",
    "\u6280\u672f\u65b9\u5411",
    "\u7814\u7a76\u65b9\u5411",
    "\u53d1\u5c55\u8d8b\u52bf",
    "\u7814\u7a76\u73b0\u72b6",
    "\u503c\u5f97\u5173\u6ce8",
    "\u5b66\u672f\u524d\u6cbf",
    "\u7814\u7a76\u6210\u679c",
    "\u7efc\u8ff0",
    "research trend",
)
RESEARCH_RECENCY_PATTERN = re.compile(
    r"\u8fd1(?:\d+|[\u4e00-\u9fff]{1,4})\s*\u5e74|\u8fd1\u5e74\u6765|\u8fd1\u671f|\u6700\u65b0|recent|latest|last\s+(?:few|several)\s+years",
    flags=re.IGNORECASE,
)
ACADEMIC_SEARCH_AGENT_ID = "RESEARCH_01_ACADEMIC_SEARCH_V1"
FOLLOW_UP_MARKERS = (
    "只有", "仅有", "还需要", "需要", "至少", "补充", "再找", "增加", "不够",
    "没找到", "仍然", "接着", "继续", "额外", "另外", "还有", "再提供",
    "下一批", "更多", "进一步", "补充一些", "请再", "其中", "上述", "上面",
    "这些", "分别", "产品化", "落地", "only", "need", "add", "more",
)

# Conservative topic signatures used to isolate conversational evidence.
RESEARCH_TOPIC_FAMILIES = {
    "artificial_intelligence": (
        "\u4eba\u5de5\u667a\u80fd",
        "\u673a\u5668\u5b66\u4e60",
        "\u6df1\u5ea6\u5b66\u4e60",
        "\u751f\u6210\u5f0f\u4eba\u5de5\u667a\u80fd",
        "\u5927\u6a21\u578b",
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "generative ai",
        "large language model",
        "foundation model",
    ),
    "flexible_electronics": (
        "\u67d4\u6027\u7535\u5b50",
        "\u67d4\u6027\u5668\u4ef6",
        "\u7535\u5b50\u76ae\u80a4",
        "\u53ef\u62c9\u4f38\u7535\u5b50",
        "flexible electronics",
        "stretchable electronics",
        "electronic skin",
    ),
    "electronics_education": (
        "电子信息",
        "电子信息课程",
        "电子信息工程",
        "电子工程",
        "电气工程",
        "电子技术课程",
        "电子信息专业",
        "电子信息类",
        "electronics engineering",
        "electrical engineering",
        "engineering education",
        "electronics education",
        "electronics course",
        "electrical engineering education",
        "arduino",
        "circuit design",
        "circuit theory",
        "analog electronics",
        "digital electronics",
        "signal processing",
        "telecommunications",
        "embedded systems",
        "computer engineering",
    ),
}
ACTIVE_LEARNING_ENGINEERING_EDUCATION_TERMS = (
    "\u4e3b\u52a8\u5b66\u4e60",
    "\u5de5\u7a0b\u6559\u80b2",
    "\u5de5\u7a0b\u6559\u5b66",
    "\u5de5\u79d1\u6559\u80b2",
    "active learning",
    "engineering education",
    "engineering teaching",
    "engineering pedagogy",
    "stem education",
)
ACTIVE_LEARNING_TERMS = (
    "\u4e3b\u52a8\u5b66\u4e60",
    "active learning",
)
ACTIVE_LEARNING_EQUIVALENT_TERMS = (
    "\u95ee\u9898\u5bfc\u5411\u5b66\u4e60",
    "\u9879\u76ee\u5f0f\u5b66\u4e60",
    "\u63a2\u7a76\u5f0f\u5b66\u4e60",
    "\u534f\u4f5c\u5b66\u4e60",
    "problem-based learning",
    "project-based learning",
    "inquiry-based learning",
    "collaborative learning",
)
ENGINEERING_EDUCATION_EVIDENCE_TERMS = (
    "\u5de5\u7a0b",
    "\u5de5\u79d1",
    "engineering",
    "stem",
    "computer science education",
    "electrical engineering",
    "electronics engineering",
)
COMPOUND_TOPIC_TERM_GROUPS = (
    ("\u91cf\u5b50", "quantum"),
    ("\u73ca\u745a", "coral"),
    ("sic", "\u78b3\u5316\u7845", "silicon carbide"),
    ("gan", "\u6c2e\u5316\u9553", "gallium nitride"),
    (
        "\u529f\u7387\u5668\u4ef6",
        "\u529f\u7387\u534a\u5bfc\u4f53",
        "power device",
        "power semiconductor",
    ),
    ("\u591a\u6a21\u6001", "multimodal", "vision-language", "vlm"),
    (
        "\u590d\u6742\u89c6\u89c9\u7406\u89e3",
        "\u89c6\u89c9\u7406\u89e3",
        "complex visual understanding",
        "visual understanding",
        "visual reasoning",
    ),
    ("llm", "large language model", "\u5927\u8bed\u8a00\u6a21\u578b"),
    ("\u8fb9\u7f18", "edge device", "edge deployment", "edge"),
    ("yolo",),
    ("\u526a\u679d", "pruning", "\u7a00\u758f\u5316", "sparsification"),
    ("\u91cf\u5316", "quantization"),
    ("risc-v", "riscv"),
    ("\u4fa7\u4fe1\u9053", "side-channel", "side channel"),
    (
        "\u786c\u4ef6\u9632\u5fa1",
        "hardware defense",
        "hardware countermeasure",
        "countermeasure",
    ),
    ("cmos",),
    (
        "ota",
        "\u8fd0\u7b97\u653e\u5927\u5668",
        "operational amplifier",
        "operational transconductance amplifier",
    ),
)
ELECTRONICS_EDUCATION_REQUEST_TERMS = (
    "电子信息",
    "电子工程",
    "电气工程",
    "电子技术",
    "electronics engineering",
    "electrical engineering",
    "electronics course",
    "electrical engineering education",
)
EDUCATION_CONTEXT_TERMS = (
    "课程",
    "教育",
    "教学",
    "辅导",
    "学习",
    "course",
    "education",
    "teaching",
    "tutoring",
    "learning",
)
AI_METHOD_TERMS = (
    "artificial intelligence",
    "ai-based",
    "machine learning",
    "deep learning",
    "generative ai",
    "large language model",
    "llm",
    "foundation model",
    "transformer",
    "multimodal",
    "reinforcement learning",
    "neural network",
    "natural language processing",
    "computer vision",
    "diffusion model",
    "reasoning",
    "agentic",
)
STRONG_WRITING_MARKERS = (
    "改写", "润色", "修改稿", "写成", "学术表达", "rewrite", "write an abstract",
)
COUNT_PATTERN = re.compile(
    r"(?:\d+|[一二三四五六七八九十百]+)\s*(?:篇|个|项|篇论文|papers?|articles?)?"
)
QUERY_NOISE_TERMS = (
    "请",
    "帮我",
    "查找",
    "检索",
    "搜索",
    "找一下",
    "查询",
    "推荐",
    "搜集",
    "最新的",
    "最新",
    "近期",
    "最近",
    "相关的",
    "相关",
    "论文",
    "文献",
    "并提供",
    "并给出",
    "并",
    "和",
    "与",
    "提供链接",
    "给出链接",
    "摘要",
    "大致内容",
    "latest",
    "recent",
    "newest",
    "papers",
    "paper",
    "publications",
    "publication",
)


def is_academic_search_request(query: str) -> bool:
    """Return true for finding papers, but not for writing or explaining them."""

    normalized = " ".join(query.casefold().split())
    has_paper = any(term.casefold() in normalized for term in PAPER_TERMS)
    has_explicit_paper = any(
        term.casefold() in normalized for term in EXPLICIT_PAPER_TERMS
    )
    has_search = any(term.casefold() in normalized for term in SEARCH_TERMS)
    has_freshness = any(term.casefold() in normalized for term in FRESHNESS_TERMS)
    has_research_topic = any(
        term.casefold() in normalized for term in RESEARCH_TOPIC_TERMS
    )
    has_research_action = any(
        term.casefold() in normalized for term in RESEARCH_ACTION_TERMS
    )
    has_research_recency = bool(RESEARCH_RECENCY_PATTERN.search(normalized))
    return has_explicit_paper and (has_search or has_freshness) or (
        has_search and has_paper
    ) or (has_research_topic and (has_research_action or has_research_recency))


def is_academic_search_follow_up(
    query: str,
    *,
    previous_agent: str = "",
    previous_answer_summary: str = "",
    previous_query: str = "",
) -> bool:
    """Keep short quantity/correction follow-ups on the academic search path."""

    if previous_agent != ACADEMIC_SEARCH_AGENT_ID:
        return False
    if previous_query and research_topic_conflicts(query, previous_query):
        return False
    normalized = " ".join(query.casefold().split())
    if any(marker.casefold() in normalized for marker in STRONG_WRITING_MARKERS):
        return False
    if is_academic_search_request(query):
        return False
    has_count = bool(COUNT_PATTERN.search(normalized))
    has_follow_up = any(
        marker.casefold() in normalized for marker in FOLLOW_UP_MARKERS
    )
    has_paper_context = any(
        term.casefold() in normalized
        for term in (*PAPER_TERMS, "论文", "文献", "paper", "article")
    ) or "论文" in previous_answer_summary
    # A short continuation may omit the topic entirely (for example,
    # "接着提供一些额外的论文信息").  The previous research agent and
    # answer summary are sufficient evidence that the user is continuing the
    # same evidence thread; explicit writing markers still take precedence.
    return has_follow_up and (
        has_count or has_paper_context or bool(previous_answer_summary.strip())
    )


def research_topic_families(text: str) -> set[str]:
    """Return known topic families present in a query or evidence text."""

    normalized = " ".join(text.casefold().split())
    families: set[str] = set()
    for family, terms in RESEARCH_TOPIC_FAMILIES.items():
        if any(term.casefold() in normalized for term in terms):
            families.add(family)
    return families


def research_topic_conflicts(current_query: str, previous_query: str) -> bool:
    """Detect an explicit topic switch before reusing conversational evidence."""

    current = research_topic_families(current_query)
    previous = research_topic_families(previous_query)
    return bool(current and previous and current.isdisjoint(previous))


def _contains_compound_term(normalized_text: str, term: str) -> bool:
    """Match ASCII abbreviations as tokens while keeping Chinese phrase matching."""

    normalized_term = term.casefold()
    if normalized_term.isascii():
        suffix = r"(?:s|v\d+)?" if normalized_term in {"llm", "yolo"} else ""
        return re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_term)}{suffix}(?![a-z0-9])",
            normalized_text,
        ) is not None
    return normalized_term in normalized_text


def filter_research_evidence(
    query: str, items: list[ExternalEvidenceItem]
) -> list[ExternalEvidenceItem]:
    """Drop evidence that explicitly belongs to a different known domain."""

    requested = research_topic_families(query)
    normalized_query = " ".join(query.casefold().split())
    electronics_education_request = (
        any(term in normalized_query for term in ELECTRONICS_EDUCATION_REQUEST_TERMS)
        and any(term in normalized_query for term in EDUCATION_CONTEXT_TERMS)
    )
    active_learning_engineering_request = (
        any(
            term.casefold() in normalized_query
            for term in ACTIVE_LEARNING_TERMS
        )
        and any(
            term.casefold() in normalized_query
            for term in ENGINEERING_EDUCATION_EVIDENCE_TERMS
        )
        and any(
            term.casefold() in normalized_query
            for term in EDUCATION_CONTEXT_TERMS
        )
    )
    required_compound_topic_groups = [
        group
        for group in COMPOUND_TOPIC_TERM_GROUPS
        if any(_contains_compound_term(normalized_query, term) for term in group)
    ]
    if not requested and not electronics_education_request:
        if (
            not active_learning_engineering_request
            and not required_compound_topic_groups
        ):
            return items
    filtered: list[ExternalEvidenceItem] = []
    for item in items:
        evidence_text = f"{item.title}\n{item.content_excerpt}"
        normalized_evidence = evidence_text.casefold()
        evidence_families = research_topic_families(evidence_text)
        if requested and evidence_families and requested.isdisjoint(evidence_families):
            continue
        if "artificial_intelligence" in requested:
            # A flexible/wearable paper may mention AI as an incidental tool.
            # Keep it out of a broad AI frontier answer unless the evidence
            # materially discusses an AI method in its title or abstract.
            method_hits = sum(
                term in normalized_evidence for term in AI_METHOD_TERMS
            )
            if "flexible_electronics" in evidence_families and method_hits < 2:
                continue
            if method_hits == 0:
                continue
        if electronics_education_request:
            if not any(
                term in normalized_evidence
                for term in RESEARCH_TOPIC_FAMILIES["electronics_education"]
            ):
                continue
        if active_learning_engineering_request:
            if not any(
                term.casefold() in normalized_evidence
                for term in (*ACTIVE_LEARNING_TERMS, *ACTIVE_LEARNING_EQUIVALENT_TERMS)
            ) or not any(
                term.casefold() in normalized_evidence
                for term in ENGINEERING_EDUCATION_EVIDENCE_TERMS
            ):
                continue
        if any(
            not any(
                _contains_compound_term(normalized_evidence, term)
                for term in group
            )
            for group in required_compound_topic_groups
        ):
            continue
        filtered.append(item)
    return filtered


def is_academic_writing_source_follow_up(
    query: str,
    *,
    previous_agent: str = "",
) -> bool:
    """Detect a writing request that explicitly refers to a prior paper result."""

    if previous_agent != ACADEMIC_SEARCH_AGENT_ID:
        return False
    normalized = " ".join(query.casefold().split())
    source_markers = (
        "\u4e0a\u9762",
        "\u4e0a\u8ff0",
        "\u4e0a\u4e00\u8f6e",
        "\u4e0a\u6b21",
        "\u7b2c1\u7bc7",
        "\u7b2c\u4e00\u7bc7",
        "above",
        "previous paper",
        "paper 1",
        "first paper",
    )
    return any(marker in normalized for marker in source_markers)


def normalize_academic_search_query(query: str) -> str:
    """Remove request instructions so providers receive the research topic."""

    normalized = query.casefold()
    for term in sorted(QUERY_NOISE_TERMS, key=len, reverse=True):
        normalized = normalized.replace(term.casefold(), " ")
    normalized = re.sub(r"[，。！？；：、,.!?;:()（）\[\]]", " ", normalized)
    normalized = " ".join(normalized.split())
    normalized = normalized.replace(
        "电子信息领域",
        "electronics engineering information technology",
    )
    normalized = normalized.replace(
        "人工智能领域",
        "artificial intelligence machine learning deep learning generative ai",
    )
    normalized = normalized.replace(
        "人工智能",
        "artificial intelligence machine learning deep learning",
    )
    normalized = normalized.replace("电子信息", "electronics information")
    normalized = normalized.replace(
        "\u4eba\u5de5\u667a\u80fd",
        "artificial intelligence machine learning deep learning generative ai",
    )
    normalized = " ".join(normalized.split())
    return normalized or (
        "electronics engineering information technology"
    )


def external_search_view(result: ExternalRetrievalResult) -> list[dict[str, Any]]:
    """Build a frontend-safe view while keeping raw excerpts out of markdown."""

    return [_item_view(item) for item in result.items]


def render_external_search_answer(result: ExternalRetrievalResult) -> str:
    count = len(result.items)
    if not count:
        warning = (
            _user_facing_warnings(result.warnings)[0]
            if result.warnings
            else "当前检索源没有返回通过审核的论文"
        )
        return f"未找到可展示的论文结果。{warning}"

    lines = [
        f"已找到 {count} 篇通过模型相关性审核的论文。",
        "结果卡片中提供了发表时间、作者、摘要概览、来源和可点击原文链接；编号可用于引用对应论文。",
    ]
    for index, item in enumerate(result.items, start=1):
        date = _date_label(item.updated_at or item.published_at)
        date_suffix = f"（{date}）" if date else ""
        lines.append(
            f"{index}. [{item.evidence_id}] {item.title}{date_suffix} "
            f"[直达链接]({item.canonical_url})"
        )
    if False:
        lines.append(f"提示：{'；'.join(result.warnings[:4])}")
    if result.warnings:
        lines.append(
            f"提示：{'；'.join(_user_facing_warnings(result.warnings))}"
        )
    return "\n".join(lines)


def _user_facing_warnings(warnings: list[str]) -> list[str]:
    """Hide provider internals while preserving useful recovery information."""

    messages: list[str] = []
    for warning in warnings:
        normalized = warning.casefold()
        if "http_429" in normalized or (
            "rate" in normalized and "limit" in normalized
        ):
            message = "部分学术来源暂时限流，已自动使用其他来源"
        elif "not_configured" in normalized or "authorized json" in normalized:
            message = "部分学术来源尚未配置授权接口，已自动使用其他来源"
        elif "missing abstract" in normalized:
            message = "部分候选论文缺少可验证摘要，已排除"
        elif "timed out" in normalized or "timeout" in normalized:
            message = "部分检索或审核超时，已保留当前可验证结果"
        elif "minimum" in normalized or "requested at least" in normalized:
            message = "当前通过审核的论文数量仍低于用户要求"
        else:
            message = "部分候选论文未通过相关性或可验证性审核"
        if message not in messages:
            messages.append(message)
        if len(messages) >= 3:
            break
    return messages or ["部分检索来源未返回可验证结果"]


def _item_view(item: ExternalEvidenceItem) -> dict[str, Any]:
    return {
        "evidence_id": item.evidence_id,
        "title": item.title,
        "url": str(item.canonical_url),
        "provider": item.provider,
        "source_type": item.source_type.value,
        "metadata": item.metadata,
        "authors": item.authors,
        "venue": item.venue,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "date_label": _date_label(item.updated_at or item.published_at),
        "abstract": item.content_excerpt,
        "doi": item.doi,
        "arxiv_id": item.arxiv_id,
        "citation_count": item.citation_count,
        "relevance_score": item.relevance_score,
        "trust_level": item.trust_level,
    }


def _date_label(value: datetime | None) -> str:
    if value is None:
        return ""
    normalized = value.astimezone(UTC)
    return normalized.strftime("%Y-%m-%d")
