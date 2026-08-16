"""Shared response-depth policies used by task execution services.

Response depth is intentionally a small execution policy rather than a raw
token multiplier.  Each workflow can consume the policy through the same
contract while keeping its own useful interpretation of retrieval, structure,
and verification.
"""

from __future__ import annotations

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
            ResponseDepth.BRIEF, 2048, 0, 0, False, ("answer",)
        ),
        ResponseDepth.STANDARD: ResponseDepthPolicy(
            ResponseDepth.STANDARD, 4096, 0, 0, False, ("answer", "key_points")
        ),
        ResponseDepth.DEEP: ResponseDepthPolicy(
            ResponseDepth.DEEP,
            6144,
            0,
            0,
            True,
            ("answer", "key_points", "limitations"),
        ),
    },
    "knowledge_qa": {
        ResponseDepth.BRIEF: ResponseDepthPolicy(
            ResponseDepth.BRIEF, 2048, 3, 2, False, ("conclusion", "evidence")
        ),
        ResponseDepth.STANDARD: ResponseDepthPolicy(
            ResponseDepth.STANDARD,
            4096,
            6,
            4,
            True,
            ("conclusion", "explanation", "evidence", "next_step"),
        ),
        ResponseDepth.DEEP: ResponseDepthPolicy(
            ResponseDepth.DEEP,
            6144,
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
