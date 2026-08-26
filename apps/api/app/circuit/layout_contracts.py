from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Orientation = Literal["horizontal", "vertical"]
Anchor = Literal["start", "middle", "end"]
Direction = Literal["up", "down", "left", "right"]
LabelKind = Literal["component", "value", "net", "port", "annotation"]


class SchematicPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class SchematicBoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class SchematicPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: str = Field(min_length=1, max_length=128)
    x: float
    y: float
    rotation: Literal[0, 90, 180, 270] = 0
    orientation: Orientation = "horizontal"
    symbol_variant: str = "default"
    bounding_box: SchematicBoundingBox


class SchematicPort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: str = Field(min_length=1, max_length=128)
    port: str = Field(min_length=1, max_length=64)
    net_id: str = Field(min_length=1, max_length=128)
    point: SchematicPoint
    direction: Direction


class SchematicWire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    net_id: str = Field(min_length=1, max_length=128)
    points: list[SchematicPoint] = Field(min_length=2, max_length=64)
    junction: bool = False


class SchematicJunction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    net_id: str = Field(min_length=1, max_length=128)
    point: SchematicPoint


class SchematicLabel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)
    point: SchematicPoint
    anchor: Anchor = "start"
    target_id: str | None = None
    priority: int = Field(default=3, ge=0, le=9)
    kind: LabelKind = "annotation"


class SchematicLayoutIR(BaseModel):
    """Deterministic visual projection of semantic CircuitIR.

    CircuitIR stays semantic; this contract owns only positions, routes and
    presentation anchors so renderers never need to infer coordinates.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["schematic_layout.v1"] = "schematic_layout.v1"
    template: str = "generic_orthogonal"
    width: int = Field(ge=320, le=4000)
    height: int = Field(ge=180, le=2400)
    style: Literal["ansi_textbook"] = "ansi_textbook"
    placements: list[SchematicPlacement] = Field(default_factory=list)
    wires: list[SchematicWire] = Field(default_factory=list)
    junctions: list[SchematicJunction] = Field(default_factory=list)
    labels: list[SchematicLabel] = Field(default_factory=list)
    ports: list[SchematicPort] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list, max_length=64)
