from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MathBlockType(StrEnum):
    INLINE = "inline"
    DISPLAY = "display"
    ALIGNED = "aligned"
    MATRIX = "matrix"
    CASES = "cases"
    EQUATION_SYSTEM = "equation_system"
    RAW_TEXT = "raw_text"


class MathSegmentType(StrEnum):
    TEXT = "text"
    INLINE_MATH = "inline_math"
    DISPLAY_MATH = "display_math"
    CODE = "code"
    TABLE = "table"
    HTML = "html"


class MathExpression(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression_id: str
    latex: str
    block_type: MathBlockType
    source_text: str | None = None
    normalized: bool = False
    validation_status: str = "unchecked"
    variables: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RichTextSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_type: MathSegmentType
    text: str | None = None
    math: MathExpression | None = None


class MathRichContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plain_text: str
    markdown: str
    segments: list[RichTextSegment] = Field(default_factory=list)
    math_expressions: list[MathExpression] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
