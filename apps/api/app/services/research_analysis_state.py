from __future__ import annotations

from typing import Final

from app.contracts.research_analysis import AnalysisStatus


class InvalidResearchAnalysisTransition(ValueError):
    """Raised when an analysis skips a required scientific workflow gate."""


ALLOWED_ANALYSIS_TRANSITIONS: Final[
    dict[AnalysisStatus, frozenset[AnalysisStatus]]
] = {
    "planning": frozenset(
        {"quality_blocked", "ready_for_execution", "insufficient_data", "failed"}
    ),
    "quality_blocked": frozenset({"planning", "failed"}),
    "ready_for_execution": frozenset({"executed", "failed", "quality_blocked"}),
    "executed": frozenset({"needs_review", "failed"}),
    "needs_review": frozenset({"executed", "failed"}),
    "insufficient_data": frozenset({"planning", "failed"}),
    "failed": frozenset({"planning"}),
}


def transition_analysis_status(
    current: AnalysisStatus, target: AnalysisStatus
) -> AnalysisStatus:
    if target not in ALLOWED_ANALYSIS_TRANSITIONS[current]:
        raise InvalidResearchAnalysisTransition(
            f"科研分析状态不能从 {current} 转为 {target}"
        )
    return target
