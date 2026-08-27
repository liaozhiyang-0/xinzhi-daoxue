"""Shared response-depth policies used by task execution services.

Response depth is intentionally a small execution policy rather than a raw
token multiplier.  Each workflow can consume the policy through the same
contract while keeping its own useful interpretation of retrieval, structure,
and verification.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from app.contracts import ResponseDepth


@dataclass(frozen=True, slots=True)
class ResponseDepthPolicy:
    level: ResponseDepth
    max_output_tokens: int
    retrieval_limit: int
    evidence_limit: int
    verify: bool
    required_sections: tuple[str, ...]

    def metadata(self) -> dict[str, Any]:
        result = asdict(self)
        result["level"] = self.level.value
        result["required_sections"] = list(self.required_sections)
        return result


_POLICIES: dict[str, dict[ResponseDepth, ResponseDepthPolicy]] = {
    "general_question": {
        ResponseDepth.BRIEF: ResponseDepthPolicy(
            ResponseDepth.BRIEF, 1024, 0, 0, False, ("answer",)
        ),
        ResponseDepth.STANDARD: ResponseDepthPolicy(
            # A normal question should not reserve a multi-thousand-token
            # completion budget. Keep standard answers useful while leaving
            # room for the 15-second interactive response target.
            ResponseDepth.STANDARD, 2048, 0, 0, False, ("answer", "key_points")
        ),
        ResponseDepth.DEEP: ResponseDepthPolicy(
            ResponseDepth.DEEP,
            4096,
            0,
            0,
            True,
            ("answer", "key_points", "limitations"),
        ),
    },
    "knowledge_qa": {
        ResponseDepth.BRIEF: ResponseDepthPolicy(
            ResponseDepth.BRIEF, 1024, 3, 2, False, ("conclusion", "evidence")
        ),
        ResponseDepth.STANDARD: ResponseDepthPolicy(
            ResponseDepth.STANDARD,
            2048,
            6,
            4,
            True,
            ("conclusion", "explanation", "evidence", "next_step"),
        ),
        ResponseDepth.DEEP: ResponseDepthPolicy(
            ResponseDepth.DEEP,
            4096,
            10,
            8,
            True,
            (
                "conclusion",
                "explanation",
                "evidence",
                "limitations",
                "next_step",
            ),
        ),
    },
    "academic_solver": {
        ResponseDepth.BRIEF: ResponseDepthPolicy(
            ResponseDepth.BRIEF, 2048, 4, 3, False, ("answer", "key_steps")
        ),
        ResponseDepth.STANDARD: ResponseDepthPolicy(
            ResponseDepth.STANDARD,
            4096,
            6,
            4,
            True,
            ("answer", "key_steps", "assumptions", "check"),
        ),
        ResponseDepth.DEEP: ResponseDepthPolicy(
            ResponseDepth.DEEP,
            6144,
            8,
            6,
            True,
            ("answer", "key_steps", "alternative", "assumptions", "check"),
        ),
    },
    "lesson_prep": {
        ResponseDepth.BRIEF: ResponseDepthPolicy(
            ResponseDepth.BRIEF, 1024, 0, 0, False, ("objective", "flow")
        ),
        ResponseDepth.STANDARD: ResponseDepthPolicy(
            ResponseDepth.STANDARD,
            2048,
            0,
            0,
            True,
            ("objective", "flow", "assessment"),
        ),
        ResponseDepth.DEEP: ResponseDepthPolicy(
            ResponseDepth.DEEP,
            3072,
            0,
            0,
            True,
            ("objective", "flow", "assessment", "differentiation"),
        ),
    },
    "academic_search": {
        ResponseDepth.BRIEF: ResponseDepthPolicy(
            ResponseDepth.BRIEF,
            2048,
            3,
            2,
            False,
            ("research_scope", "evidence_summary"),
        ),
        ResponseDepth.STANDARD: ResponseDepthPolicy(
            ResponseDepth.STANDARD,
            4096,
            6,
            4,
            True,
            ("research_scope", "evidence_table", "limitations"),
        ),
        ResponseDepth.DEEP: ResponseDepthPolicy(
            ResponseDepth.DEEP,
            6144,
            10,
            8,
            True,
            ("research_scope", "evidence_table", "open_questions", "limitations"),
        ),
    },
}

# Assignment review and academic writing use the same bounded structured
# output budget as lesson preparation until they receive dedicated schemas.
_POLICIES["internal_structured"] = _POLICIES["lesson_prep"]


def resolve_response_depth(options: Mapping[str, Any] | None) -> ResponseDepth:
    """Return a validated depth while preserving backward-compatible options."""

    raw = (options or {}).get("response_depth", ResponseDepth.STANDARD)
    try:
        return raw if isinstance(raw, ResponseDepth) else ResponseDepth(str(raw))
    except (TypeError, ValueError):
        return ResponseDepth.STANDARD


def policy_for(
    options: Mapping[str, Any] | None, workflow: str
) -> ResponseDepthPolicy:
    depth = resolve_response_depth(options)
    policies = _POLICIES.get(workflow, _POLICIES["general_question"])
    return policies[depth]


def depth_instruction(policy: ResponseDepthPolicy) -> str:
    """Prompt fragment describing observable output requirements.

    It deliberately asks for a concise, verifiable summary instead of hidden
    chain-of-thought.
    """

    if policy.level is ResponseDepth.BRIEF:
        return "Response depth: brief. Give the direct answer and essential steps."
    if policy.level is ResponseDepth.DEEP:
        return (
            "Response depth: deep. Include the requested answer, supporting evidence, "
            "assumptions, limitations, and a concise verification or alternative. "
            "Do not reveal hidden chain-of-thought."
        )
    return (
        "Response depth: standard. Explain the answer with the key steps, evidence, "
        "and practical caveats."
    )


def output_constraint_instruction(text: str) -> str:
    """Translate explicit user format requests into a bounded prompt clause."""

    normalized = " ".join(text.casefold().split())
    if not normalized:
        return ""
    if any(
        marker in normalized
        for marker in ("直接给出公式", "给出公式", "公式即可", "formula only")
    ):
        return (
            "用户要求只输出可直接使用的公式；不要附加资料说明、引用列表或推导。"
            "若证据不足以可靠确定公式，只说明公式缺失。"
        )
    if re.search(
        r"不要资料(?:说明|介绍)?|不要引用|不要说明|不要解释|just give",
        normalized,
    ):
        return "用户要求直接回答；不要附加资料说明、引用列表或冗余解释。"
    if any(marker in normalized for marker in ("不要这么详细", "简洁回答", "只输出")):
        return "用户要求简洁输出；只保留直接答案和必要条件。"
    return ""
