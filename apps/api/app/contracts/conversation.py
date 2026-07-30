from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.learning import TeachingMode


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM_EVENT = "system_event"


class MessageStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class MessageVisibility(StrEnum):
    USER_VISIBLE = "user_visible"
    DEVELOPER_ONLY = "developer_only"
    INTERNAL = "internal"


class ConversationMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: str = Field(validation_alias="id")
    session_id: str
    user_id: str
    sequence: int = Field(ge=1)
    role: MessageRole
    status: MessageStatus
    visibility: MessageVisibility
    content_text: str
    content_data: dict[str, Any] = Field(default_factory=dict)
    source_task_id: str | None = None
    reply_to_message_id: str | None = None
    revision_of_message_id: str | None = None
    origin_message_id: str | None = None
    attachment_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(
        default_factory=dict, validation_alias="metadata_data"
    )


class TeachingStateV1(BaseModel):
    """Short-lived session state; distinct from Memory and mastery."""

    model_config = ConfigDict(extra="forbid")

    version: str = "v1"
    teaching_mode: TeachingMode = TeachingMode.DIRECT_ANSWER
    source_task_id: str | None = None
    student_attempt_present: bool = False
    current_skill_ids: list[str] = Field(default_factory=list)
    current_problem_type: str | None = None
    current_hint_level: str | None = None
    hint_request_count: int = Field(default=0, ge=0)
    execution_path: str | None = None
    first_confirmed_error_step: str | None = None
    pending_check_question: str | None = None
    pending_check_question_id: str | None = None
    awaiting_student_response: bool = False
    solution_packet_task_id: str | None = None
    verification_report_task_id: str | None = None
    full_solution_disclosed: bool = False
    current_attempt_id: str | None = None
    previous_attempt_id: str | None = None
    attempt_sequence: int = Field(default=0, ge=0)
    last_feedback_uptake_status: str | None = None
    last_mastery_evidence_type: str | None = None
    pending_retest_plan_ids: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class SessionWorkingState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_goal: str = ""
    current_course: str = ""
    current_task_family: str = ""
    current_problem_id: str = ""
    confirmed_facts: list[str] = Field(default_factory=list)
    user_corrections: list[str] = Field(default_factory=list)
    active_assumptions: list[str] = Field(default_factory=list)
    completed_steps: list[str] = Field(default_factory=list)
    pending_steps: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    referenced_message_ids: list[str] = Field(default_factory=list)
    teaching_state: TeachingStateV1 | None = None
    updated_at: datetime | None = None
    version: int = Field(default=1, ge=1)


class ContextMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    sequence: int
    role: MessageRole
    content_text: str
    course_id: str = ""
    is_correction: bool = False


class ConversationContextBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    current_message_id: str | None = None
    session_summary: str = ""
    summary_id: str | None = None
    summary_version: int = 0
    recent_messages: list[ContextMessage] = Field(default_factory=list)
    relevant_earlier_messages: list[ContextMessage] = Field(default_factory=list)
    active_memories: list[dict[str, Any]] = Field(default_factory=list)
    learner_context: dict[str, Any] = Field(default_factory=dict)
    working_state: SessionWorkingState = Field(default_factory=SessionWorkingState)
    pinned_facts: list[str] = Field(default_factory=list)
    unresolved_items: list[str] = Field(default_factory=list)
    token_estimate: int = Field(ge=0)
    budget: int = Field(ge=1)
    estimation_method: str
    compaction_applied: bool = False
    context_trimmed: bool = False
    cache_status: str = "miss"
    cache_backend: str = "memory"
    build_latency_ms: float = Field(default=0, ge=0)
    source_message_ids: list[str] = Field(default_factory=list)
    source_memory_ids: list[str] = Field(default_factory=list)

    def safe_prompt_text(self) -> str:
        parts: list[str] = []
        if self.working_state.current_goal and self.current_message_id is None:
            parts.append(f"当前目标：{self.working_state.current_goal}")
        if self.working_state.user_corrections:
            parts.append(
                "用户纠正：" + "；".join(self.working_state.user_corrections[-3:])
            )
        if self.session_summary:
            parts.append(f"会话摘要：{self.session_summary}")
        if self.recent_messages:
            rendered = "\n".join(
                f"{'用户' if item.role == MessageRole.USER else '助手'}："
                f"{item.content_text}"
                for item in self.recent_messages
            )
            parts.append(f"最近对话：\n{rendered}")
        if self.active_memories:
            parts.append(
                "用户已启用的偏好："
                + "；".join(
                    str(item.get("content", "")) for item in self.active_memories
                )
            )
        return "\n\n".join(part for part in parts if part)


class SessionSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    version: int
    covers_from_sequence: int
    covers_through_sequence: int
    summary_text: str
    structured_state: dict[str, Any]
    source_message_ids: list[str]
    source_checksum: str
    generation_method: str
    model_name: str
    token_estimate: int
    status: str
    created_at: datetime
