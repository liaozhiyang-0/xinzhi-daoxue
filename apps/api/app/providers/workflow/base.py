from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.contracts import ExecutionStatus


class WorkflowResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ExecutionStatus
    workflow_id: str
    answer_text: str = ""
    structured_result: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: int = Field(default=0, ge=0)


class WorkflowProvider(ABC):
    provider_name: str

    @abstractmethod
    async def invoke_workflow(
        self,
        workflow_id: str,
        payload: dict[str, Any],
        timeout_seconds: int | None = None,
    ) -> WorkflowResult: ...
