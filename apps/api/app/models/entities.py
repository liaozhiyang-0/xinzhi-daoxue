from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


def db_id() -> str:
    return uuid4().hex


class TaskStatus(StrEnum):
    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    WAITING_REVIEW = "waiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"


class FileIngestionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"


class KnowledgeMaterialStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


class CourseMaterialReviewStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


task_status_enum = Enum(
    TaskStatus,
    values_callable=lambda enum: [item.value for item in enum],
    native_enum=False,
    length=32,
)


class AccountModel(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("login_normalized", name="uq_accounts_login_normalized"),
        Index("ix_accounts_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    login: Mapped[str] = mapped_column(String(255))
    login_normalized: Mapped[str] = mapped_column(String(255), index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(32), default="student", index=True)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(
            AccountStatus,
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
            length=32,
        ),
        default=AccountStatus.ACTIVE,
    )
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    auth_sessions: Mapped[list[AuthSessionModel]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class AuthSessionModel(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_account_active", "account_id", "revoked_at"),
        Index("ix_auth_sessions_access_expires", "access_expires_at"),
        Index("ix_auth_sessions_refresh_expires", "refresh_expires_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    access_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    account: Mapped[AccountModel] = relationship(back_populates="auth_sessions")


class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_actor_created", "actor_account_id", "created_at"),
        Index("ix_audit_logs_action_created", "action", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    actor_account_id: Mapped[str | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(96), index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class SystemSettingModel(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SessionModel(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_last_message", "user_id", "last_message_at"),
        Index("ix_sessions_user_archived", "user_id", "archived_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    course_id: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    title_source: Mapped[str] = mapped_column(String(32), default="default")
    context_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    session_revision: Mapped[int] = mapped_column(Integer, default=0)
    parent_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("sessions.id"), nullable=True, index=True
    )
    branch_from_message_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_memory_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    context_compaction_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    tasks: Mapped[list[TaskModel]] = relationship(back_populates="session")
    messages: Mapped[list[ConversationMessageModel]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class TaskModel(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_status_created_at", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    course_id: Mapped[str] = mapped_column(String(32), index=True)
    intent: Mapped[str] = mapped_column(String(64))
    status: Mapped[TaskStatus] = mapped_column(
        task_status_enum, default=TaskStatus.CREATED
    )
    provider: Mapped[str] = mapped_column(String(32), default="mock")
    agent_id: Mapped[str] = mapped_column(String(64))
    route_status: Mapped[str] = mapped_column(String(32), default="selected")
    route_reason: Mapped[str] = mapped_column(Text, default="")
    input_content: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_content: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id"), nullable=True, index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    execution_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    failure_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_message_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    assistant_message_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped[SessionModel] = relationship(back_populates="tasks")
    artifacts: Mapped[list[ArtifactModel]] = relationship(back_populates="task")
    events: Mapped[list[TaskEventModel]] = relationship(back_populates="task")


class ConversationMessageModel(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        UniqueConstraint(
            "session_id", "sequence", name="uq_conversation_message_sequence"
        ),
        UniqueConstraint("source_task_id", "role", name="uq_conversation_task_role"),
        Index("ix_conversation_session_sequence", "session_id", "sequence"),
        Index("ix_conversation_user_created", "user_id", "created_at"),
        Index("ix_conversation_reply_to", "reply_to_message_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    visibility: Mapped[str] = mapped_column(String(32), index=True)
    content_text: Mapped[str] = mapped_column(Text, default="")
    content_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id"), nullable=True, index=True
    )
    reply_to_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_messages.id"), nullable=True
    )
    revision_of_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_messages.id"), nullable=True, index=True
    )
    origin_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_messages.id"), nullable=True
    )
    attachment_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    session: Mapped[SessionModel] = relationship(back_populates="messages")


class SessionWorkingStateModel(Base):
    __tablename__ = "session_working_states"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    state_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SessionSummaryModel(Base):
    __tablename__ = "session_summaries"
    __table_args__ = (
        UniqueConstraint("session_id", "version", name="uq_session_summary_version"),
        Index("ix_session_summary_latest", "session_id", "version"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    covers_from_sequence: Mapped[int] = mapped_column(Integer)
    covers_through_sequence: Mapped[int] = mapped_column(Integer)
    summary_text: Mapped[str] = mapped_column(Text)
    structured_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_message_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_checksum: Mapped[str] = mapped_column(String(64))
    generation_method: Mapped[str] = mapped_column(String(32))
    model_name: Mapped[str] = mapped_column(String(128), default="")
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class MemoryModel(Base):
    __tablename__ = "memories"
    __table_args__ = (
        Index("ix_memories_user_status_updated", "user_id", "status", "updated_at"),
        Index("ix_memories_user_course", "user_id", "course_id"),
        Index("ix_memories_source_session", "source_session_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    memory_type: Mapped[str] = mapped_column(String(32), index=True)
    scope: Mapped[str] = mapped_column(String(32), default="global")
    course_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    content_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    source_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1)


class FileModel(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    owner_user_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str] = mapped_column(String(64), default="generic")
    course_id: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )
    material_key: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    material_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    knowledge_status: Mapped[KnowledgeMaterialStatus] = mapped_column(
        Enum(
            KnowledgeMaterialStatus,
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
            length=32,
        ),
        default=KnowledgeMaterialStatus.DRAFT,
        index=True,
    )
    knowledge_index_status: Mapped[str] = mapped_column(
        String(32), default="not_indexed"
    )
    knowledge_published_by: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    knowledge_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    material_review_status: Mapped[CourseMaterialReviewStatus] = mapped_column(
        String(32), default=CourseMaterialReviewStatus.NOT_REQUIRED, index=True
    )
    material_reviewed_by: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    material_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    material_review_note: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    detected_content_type: Mapped[str] = mapped_column(
        String(128), default="application/octet-stream"
    )
    ingestion_status: Mapped[FileIngestionStatus] = mapped_column(
        Enum(
            FileIngestionStatus,
            values_callable=lambda enum: [item.value for item in enum],
            native_enum=False,
            length=32,
        ),
        default=FileIngestionStatus.PENDING,
        index=True,
    )
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    extraction_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_version: Mapped[str] = mapped_column(String(32), default="1")
    extraction_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    extraction_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    chunks: Mapped[list[DocumentChunkModel]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
    )


class DocumentChunkModel(Base):
    __tablename__ = "file_chunks"
    __table_args__ = (
        UniqueConstraint("file_id", "ordinal", name="uq_file_chunks_file_ordinal"),
        Index("ix_file_chunks_file_page", "file_id", "page_number"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    file_id: Mapped[str] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    char_end: Mapped[int] = mapped_column(Integer, default=0)
    source_ref: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    file: Mapped[FileModel] = relationship(back_populates="chunks")


class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    task: Mapped[TaskModel] = relationship(back_populates="artifacts")


class AgentRunModel(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    agent_id: Mapped[str] = mapped_column(String(64))
    run_kind: Mapped[str] = mapped_column(String(32), default="agent")
    parent_run_id: Mapped[str] = mapped_column(
        String(64), default="", index=True
    )
    parent_node_id: Mapped[str] = mapped_column(String(100), default="")
    plan_id: Mapped[str] = mapped_column(String(120), default="")
    plan_version: Mapped[str] = mapped_column(String(32), default="1")
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    budget_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    state_version: Mapped[int] = mapped_column(Integer, default=1)
    agent_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    provider: Mapped[str] = mapped_column(String(32))
    workflow_version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    status: Mapped[str] = mapped_column(String(32))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0)
    retrieval_calls: Mapped[int] = mapped_column(Integer, default=0)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metrics_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    terminal_reason: Mapped[str] = mapped_column(String(256), default="")
    control_request: Mapped[str] = mapped_column(String(32), default="")
    control_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRunNodeModel(Base):
    """Durable node execution state for the incremental Agent Runtime."""

    __tablename__ = "agent_run_nodes"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "node_id", name="uq_agent_run_nodes_run_node"
        ),
        Index("ix_agent_run_nodes_run_status", "run_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[str] = mapped_column(String(100))
    node_type: Mapped[str] = mapped_column(String(32))
    handler_id: Mapped[str] = mapped_column(String(160))
    target_id: Mapped[str] = mapped_column(String(160), default="")
    execution_key: Mapped[str] = mapped_column(String(240), default="")
    effect_status: Mapped[str] = mapped_column(
        String(32), default="not_started", index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=0)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list)
    input_artifact_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_artifact_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    observation_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error_code: Mapped[str] = mapped_column(String(128), default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class AgentCheckpointModel(Base):
    """Append-only durable snapshots used for replay and restart recovery."""

    __tablename__ = "agent_checkpoints"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "sequence", name="uq_agent_checkpoints_run_sequence"
        ),
        Index("ix_agent_checkpoints_run_created", "run_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    state_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(32))
    state_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    event_sequence: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class AgentPlanProposalModel(Base):
    """Durable, reviewable replacement plan for one Runtime Run."""

    __tablename__ = "agent_plan_proposals"
    __table_args__ = (
        Index(
            "ix_agent_plan_proposals_run_status",
            "run_id",
            "status",
        ),
        Index(
            "ix_agent_plan_proposals_task_created",
            "task_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    base_iteration: Mapped[int] = mapped_column(Integer)
    target_iteration: Mapped[int] = mapped_column(Integer)
    base_state_version: Mapped[int] = mapped_column(Integer)
    state_version: Mapped[int] = mapped_column(Integer)
    base_plan_id: Mapped[str] = mapped_column(String(120))
    base_plan_version: Mapped[str] = mapped_column(String(32))
    proposed_plan_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text)
    affected_node_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    budget_impact_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    decision_reason: Mapped[str] = mapped_column(String(2_000), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class TaskEventModel(Base):
    __tablename__ = "task_events"
    __table_args__ = (
        UniqueConstraint("task_id", "sequence", name="uq_task_events_sequence"),
        Index("ix_task_events_task_sequence", "task_id", "sequence"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    task: Mapped[TaskModel] = relationship(back_populates="events")


class TaskFeedbackModel(Base):
    __tablename__ = "task_feedback"
    __table_args__ = (
        UniqueConstraint(
            "task_id", "user_id", name="uq_task_feedback_task_user"
        ),
        Index("ix_task_feedback_created_course", "created_at", "course_id"),
        Index("ix_task_feedback_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    user_role: Mapped[str] = mapped_column(String(32), default="student")
    course_id: Mapped[str] = mapped_column(String(32), index=True)
    task_type: Mapped[str] = mapped_column(String(64))
    agent_id: Mapped[str] = mapped_column(String(64))
    agent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider: Mapped[str] = mapped_column(String(32), default="unknown")
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rag_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    retrieval_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    satisfaction: Mapped[str | None] = mapped_column(String(32), nullable=True)
    problem_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manual_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    citation_coverage: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ResearchEvidenceModel(Base):
    """Durable metadata for the dedicated research evidence vector index."""

    __tablename__ = "research_evidence"
    __table_args__ = (
        UniqueConstraint("evidence_id", name="uq_research_evidence_id"),
        Index("ix_research_evidence_topic_seen", "topic", "last_seen_at"),
        Index("ix_research_evidence_status_updated", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    evidence_id: Mapped[str] = mapped_column(String(64), nullable=False)
    topic: Mapped[str] = mapped_column(String(500), default="", index=True)
    source_type: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    source_ref: Mapped[str] = mapped_column(String(512), default="")
    canonical_url: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str] = mapped_column(String(1000))
    content_excerpt: Mapped[str] = mapped_column(Text, default="")
    authors: Mapped[list[str]] = mapped_column(JSON, default=list)
    venue: Mapped[str] = mapped_column(String(500), default="")
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    doi: Mapped[str] = mapped_column(String(256), default="")
    arxiv_id: Mapped[str] = mapped_column(String(128), default="")
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(128), default="")
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    trust_level: Mapped[str] = mapped_column(String(32), default="unknown")
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json", JSON, default=dict
    )
    vector_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class LearnerKnowledgeStateModel(Base):
    __tablename__ = "learner_knowledge_states"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "course_id", "knowledge_point", name="uq_learner_point"
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    course_id: Mapped[str] = mapped_column(String(32), index=True)
    knowledge_point: Mapped[str] = mapped_column(String(255), index=True)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.2)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0)
    hint_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class WrongAnswerRecordModel(Base):
    __tablename__ = "wrong_answer_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    source_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    course_id: Mapped[str] = mapped_column(String(32), index=True)
    chapter: Mapped[str | None] = mapped_column(String(255), nullable=True)
    knowledge_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    problem_summary: Mapped[str] = mapped_column(Text)
    student_answer: Mapped[str] = mapped_column(Text, default="")
    error_types: Mapped[list[str]] = mapped_column(JSON, default=list)
    feedback: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    mastery_before: Mapped[float] = mapped_column(Float, default=0.5)
    mastery_after: Mapped[float] = mapped_column(Float, default=0.5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class PracticeAttemptModel(Base):
    __tablename__ = "practice_attempts"
    __table_args__ = (
        UniqueConstraint(
            "source_task_id",
            "attempt_sequence",
            name="uq_practice_attempt_source_sequence",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_practice_attempt_user_idempotency",
        ),
        Index("ix_practice_attempt_user_created", "user_id", "created_at"),
        Index(
            "ix_practice_attempt_session_sequence",
            "session_id",
            "attempt_sequence",
        ),
        Index(
            "ix_practice_attempt_source_sequence",
            "source_task_id",
            "attempt_sequence",
        ),
        Index("ix_practice_attempt_revision", "revision_of_attempt_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    source_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    course_id: Mapped[str] = mapped_column(String(32), index=True)
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=True
    )
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    attempt_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revision_of_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("practice_attempts.id"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    problem: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    reference_answer: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    student_answer: Mapped[str] = mapped_column(Text, default="")
    steps_data: Mapped[list[dict[str, Any]]] = mapped_column(
        "steps_json", JSON, default=list
    )
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    student_confidence: Mapped[float | None] = mapped_column(
        "confidence", Float, nullable=True
    )
    teaching_mode: Mapped[str] = mapped_column(String(32), default="direct_answer")
    hint_level_used: Mapped[str | None] = mapped_column(String(8), nullable=True)
    full_solution_seen: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verification_report: Mapped[dict[str, Any]] = mapped_column(
        "verification_report_json", JSON, default=dict
    )
    feedback_uptake: Mapped[dict[str, Any]] = mapped_column(
        "feedback_uptake_json", JSON, default=dict
    )
    mastery_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        "mastery_evidence_json", JSON, default=list
    )
    review_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="generated")
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RetestPlanModel(Base):
    __tablename__ = "retest_plans"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "skill_id",
            "source_task_id",
            "interval_days",
            name="uq_retest_plan_source_interval",
        ),
        Index("ix_retest_user_status_due", "user_id", "status", "due_at"),
        Index("ix_retest_skill_due", "skill_id", "due_at"),
        Index("ix_retest_source_task", "source_task_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    skill_id: Mapped[str] = mapped_column(String(255))
    source_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"))
    source_attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey("practice_attempts.id"), nullable=True
    )
    interval_days: Mapped[int] = mapped_column(Integer)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="scheduled")
    reason_code: Mapped[str] = mapped_column(String(64))
    generated_problem_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    completed_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("tasks.id"), nullable=True
    )
    result: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class LearningInteractionModel(Base):
    __tablename__ = "learning_interactions"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_learning_action_key"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=db_id)
    source_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
