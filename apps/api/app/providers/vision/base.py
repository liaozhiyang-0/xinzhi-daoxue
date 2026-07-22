from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class VisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recognized_text: str = ""
    diagram_description: str = ""
    confidence: float = Field(default=0, ge=0, le=1)
    conflicts: list[str] = Field(default_factory=list)
    uncertain_info: list[str] = Field(default_factory=list)
    provider: str = ""


class VisionProvider(ABC):
    provider_name: str

    @property
    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    async def analyze_image(self, image: Path, *, prompt: str) -> VisionResult: ...
