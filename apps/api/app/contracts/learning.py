from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LearningAction = Literal[
    "add_wrong_answer",
    "get_hint",
    "check_answer",
    "generate_variant",
    "related_knowledge",
    "mark_mastered",
]


class LearnerKnowledgeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: str
    knowledge_point: str
    mastery_score: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    correct_count: int = Field(ge=0)
    incorrect_count: int = Field(ge=0)
    hint_count: int = Field(ge=0)


class AnswerReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["correct", "partially_correct", "incorrect", "insufficient"]
    aligned_steps: list[dict[str, Any]] = Field(default_factory=list)
    first_error: dict[str, Any] | None = None
    error_types: list[str] = Field(default_factory=list)
    feedback: list[str] = Field(default_factory=list)
    mastery_delta: float = Field(ge=-1, le=1)


class PracticeProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "unsupported", "invalid"]
    problem_text: str = ""
    known_conditions: list[dict[str, Any]] = Field(default_factory=list)
    target_quantities: list[dict[str, Any]] = Field(default_factory=list)
    reference_answer: dict[str, Any] = Field(default_factory=dict)
    validation_checks: list[dict[str, Any]] = Field(default_factory=list)
    source_task_id: str


class LearningActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_task_id: str
    user_id: str
    action: LearningAction
    idempotency_key: str = Field(min_length=8, max_length=128)
    student_answer: str = Field(default="", max_length=10_000)
    payload: dict[str, Any] = Field(default_factory=dict)


class LearningFollowUpContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_task_id: str
    course_id: str
    intent: str
    action: LearningAction


class LearningActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interaction_id: str
    action: LearningAction
    status: Literal["completed", "accepted", "needs_task"]
    message: str
    follow_up_prompt: str = ""
    follow_up_context: LearningFollowUpContext | None = None
    review: AnswerReviewResult | None = None
    practice: PracticeProblem | None = None
    mastery: list[LearnerKnowledgeState] = Field(default_factory=list)
