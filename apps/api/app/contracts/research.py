from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ResearchSourceKind = Literal["academic_paper", "web_report", "conference"]


class ResearchIntentDecision(BaseModel):
    """Model-judged intent for the research frontier radar."""

    goal: Literal[
        "frontier_brief",
        "paper_search",
        "news_report",
        "conference_radar",
        "technology_compare",
        "explain",
        "follow_up",
    ]
    topic: str = Field(min_length=1, max_length=300)
    requires_web: bool = True
    source_kinds: list[ResearchSourceKind] = Field(
        default=["academic_paper", "web_report", "conference"], max_length=3
    )
    freshness_days: int = Field(default=1095, ge=1, le=3650)
    response_depth: Literal["brief", "standard", "deep"] = "deep"
    research_questions: list[str] = Field(default_factory=list, max_length=6)
    reason_codes: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(default=0.7, ge=0, le=1)


class ResearchFinding(BaseModel):
    claim: str = Field(min_length=1, max_length=1200)
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)
    why_it_matters: str = Field(default="", max_length=800)
    confidence: Literal["high", "medium", "low"] = "medium"


class ResearchSourceGroup(BaseModel):
    category: ResearchSourceKind
    count: int = Field(default=0, ge=0)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    note: str = Field(default="", max_length=600)


class ResearchTimelineItem(BaseModel):
    date_label: str = Field(min_length=1, max_length=40)
    event: str = Field(min_length=1, max_length=600)
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)


class ResearchBriefDraft(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    scope: str = Field(min_length=1, max_length=800)
    executive_summary: str = Field(min_length=1, max_length=2400)
    key_findings: list[ResearchFinding] = Field(min_length=1, max_length=8)
    source_landscape: list[ResearchSourceGroup] = Field(
        default_factory=list, max_length=6
    )
    timeline: list[ResearchTimelineItem] = Field(default_factory=list, max_length=8)
    open_questions: list[str] = Field(default_factory=list, max_length=8)
    next_steps: list[str] = Field(default_factory=list, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=8)
