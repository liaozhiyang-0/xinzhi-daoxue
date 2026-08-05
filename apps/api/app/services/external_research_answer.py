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
ACADEMIC_SEARCH_AGENT_ID = "RESEARCH_01_ACADEMIC_SEARCH_V1"
FOLLOW_UP_MARKERS = (
    "只有", "仅有", "还需要", "需要", "至少", "补充", "再找", "增加", "不够",
    "没找到", "仍然", "only", "need", "add", "more",
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
    return has_explicit_paper and (has_search or has_freshness) or (
        has_search and has_paper
    )


def is_academic_search_follow_up(
    query: str,
    *,
    previous_agent: str = "",
    previous_answer_summary: str = "",
) -> bool:
    """Keep short quantity/correction follow-ups on the academic search path."""

    if previous_agent != ACADEMIC_SEARCH_AGENT_ID:
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
    return has_follow_up and (has_count or has_paper_context)


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
