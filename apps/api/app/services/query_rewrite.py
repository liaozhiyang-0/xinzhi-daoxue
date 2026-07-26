from __future__ import annotations

import re
import unicodedata

from app.knowledge_catalog import KNOWLEDGE_COURSE_NAMES

COURSE_NAMES = KNOWLEDGE_COURSE_NAMES
POLITE_PREFIX = re.compile(
    r"^(?:请问|请帮我|帮我|麻烦(?:你)?|能否|可以(?:帮我)?)(?:解释|说明|分析|讲解|告诉我)?[，,：:\s]*"
)


def rewrite_retrieval_query(
    query: str,
    *,
    course_id: str,
    conversation_summary: str = "",
) -> tuple[str, list[str]]:
    """Apply deterministic, non-generative cleanup while preserving formulas."""

    normalized = " ".join(unicodedata.normalize("NFKC", query).split())
    rewritten = POLITE_PREFIX.sub("", normalized).strip() or normalized
    rewritten = rewritten.replace("虚短虚断", "虚短 和 虚断")
    rules: list[str] = []
    if rewritten != normalized:
        rules.append("remove_polite_prefix_or_normalize_term")
    if len(rewritten) <= 6 and conversation_summary.strip():
        summary = " ".join(conversation_summary.split())[:240]
        rewritten = f"{summary} {rewritten}".strip()
        rules.append("expand_short_follow_up")
    if rewritten and len(rewritten) <= 3 and course_id in COURSE_NAMES:
        rewritten = f"{COURSE_NAMES[course_id]} {rewritten}".strip()
        rules.append("add_course_scope_for_short_query")
    return rewritten, rules
