from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from statistics import median
from typing import cast

from app.circuit.contracts import CircuitComponent, CircuitIR
from app.circuit.layout_contracts import (
    Direction,
    LabelKind,
    SchematicBoundingBox,
    SchematicJunction,
    SchematicLabel,
    SchematicLayoutIR,
    SchematicPlacement,
    SchematicPoint,
    SchematicPort,
    SchematicWire,
)

SUPPORTED_TEMPLATES = frozenset(
    {
        "series",
        "parallel",
        "divider",
        "ladder",
        "bridge",
        "rc_lowpass",
        "rc_highpass",
        "rlc_series",
        "opamp_inverting",
        "opamp_noninverting",
        "opamp_feedback",
        "source_load",
        "transistor_stage",
        "small_signal",
        "logic_flow",
        "generic_left_to_right",
        "generic_orthogonal",
    }
)

_TWO_TERMINAL_TYPES = frozenset(
    {
        "resistor",
        "capacitor",
        "inductor",
        "voltage_source",
        "current_source",
        "dependent_voltage_source",
        "dependent_current_source",
        "switch",
        "diode",
        "zener_diode",
        "open_circuit",
        "short_circuit",
        "coupled_inductor",
    }
)
_LOGIC_TYPES = frozenset(
    {
        "and_gate",
        "or_gate",
        "not_gate",
        "nand_gate",
        "nor_gate",
        "xor_gate",
        "xnor_gate",
        "buffer",
        "schmitt_trigger",
        "d_flip_flop",
        "jk_flip_flop",
        "t_flip_flop",
        "sr_latch",
        "mux",
        "demux",
        "encoder",
        "decoder",
        "half_adder",
        "full_adder",
        "clock",
        "logic_input",
        "logic_output",
        "bus",
    }
)


@dataclass(frozen=True, slots=True)
class PortPoint:
    component_id: str
    port: str
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class ComponentPlacement:
    component: CircuitComponent
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class CircuitLayout:
    placements: tuple[ComponentPlacement, ...]
    ports: tuple[PortPoint, ...]
    warnings: tuple[str, ...] = ()


def classify_topology(circuit: CircuitIR, requested: str | None = None) -> str:
    """Select a deterministic schematic template from semantic structure."""

    if requested in SUPPORTED_TEMPLATES:
        return str(requested)
    component_types = {component.type for component in circuit.components}
    if component_types & _LOGIC_TYPES:
        return "logic_flow"
    if "opamp" in component_types:
        return "opamp_feedback"
    if component_types & {"bjt", "mosfet"}:
        return "transistor_stage"
    resistors = sum(component.type == "resistor" for component in circuit.components)
    has_reference = any(component.type == "ground" for component in circuit.components)
    has_reference = has_reference or any(
        net.kind == "reference" or net.id.casefold() in {"gnd", "ground", "0"}
        for net in circuit.nets
    )
    if resistors >= 2 and has_reference:
        return "divider"
    return "generic_orthogonal"


def build_schematic_layout(
    circuit: CircuitIR,
    template: str | None = None,
    *,
    width: int = 900,
    height: int = 520,
) -> SchematicLayoutIR:
    """Build an orthogonal, renderer-independent schematic layout."""

    selected = classify_topology(circuit, template)
    warnings: list[str] = []
    if template and template not in SUPPORTED_TEMPLATES:
        warnings.append(f"unsupported_template:{template}")
    components = list(circuit.components)
    placements = _place_components(components, selected, width, height)
    ports = _place_ports(circuit, placements)
    wires, junctions = _route_nets(circuit, ports, placements, width, height, warnings)
    labels = _place_labels(circuit, placements, ports, warnings)
    return SchematicLayoutIR(
        template=selected,
        width=width,
        height=height,
        placements=placements,
        wires=wires,
        junctions=junctions,
        labels=labels,
        ports=ports,
        warnings=list(dict.fromkeys(warnings)),
    )


def build_layout(circuit: CircuitIR, template: str) -> CircuitLayout:
    """Compatibility projection for callers that still consume the old layout."""

    schematic = build_schematic_layout(circuit, template)
    by_id = {component.id: component for component in circuit.components}
    placements = tuple(
        ComponentPlacement(by_id[item.component_id], item.x, item.y)
        for item in schematic.placements
        if item.component_id in by_id
    )
    ports = tuple(
        PortPoint(item.component_id, item.port, item.point.x, item.point.y)
        for item in schematic.ports
    )
    return CircuitLayout(placements, ports, tuple(schematic.warnings))


def _place_components(
    components: list[CircuitComponent], template: str, width: int, height: int
) -> list[SchematicPlacement]:
    ground = [item for item in components if item.type == "ground"]
    visible = [item for item in components if item.type != "ground"]
    placements: list[SchematicPlacement] = []
    if template == "divider":
        x = width / 2
        step = max(78.0, min(112.0, (height - 130) / max(1, len(visible))))
        for index, component in enumerate(visible):
            placements.append(_placement(component, x, 60 + index * step, 90))
        for index, component in enumerate(ground):
            placements.append(_placement(component, x, height - 48 - index * 40, 0))
        return placements
    if template == "parallel":
        step = max(110.0, min(180.0, (width - 160) / max(1, len(visible))))
        for index, component in enumerate(visible):
            placements.append(_placement(component, 80 + index * step, height / 2, 90))
        for index, component in enumerate(ground):
            placements.append(_placement(component, 80, height - 55 - index * 36, 0))
        return placements
    if template in {"opamp_inverting", "opamp_noninverting", "opamp_feedback"}:
        opamp = next((item for item in visible if item.type == "opamp"), None)
        if opamp is not None:
            placements.append(_placement(opamp, width * 0.64, height * 0.52, 0))
        rest = [item for item in visible if item is not opamp]
        for index, component in enumerate(rest):
            row = -1 if index % 2 == 0 else 1
            placements.append(
                _placement(
                    component, 150 + (index // 2) * 145, height / 2 + row * 105, 0
                )
            )
        for index, component in enumerate(ground):
            placements.append(
                _placement(component, width * 0.64, height - 48 - index * 36, 0)
            )
        return placements
    if template in {"transistor_stage", "small_signal"}:
        transistor = next(
            (item for item in visible if item.type in {"bjt", "mosfet"}), None
        )
        if transistor is not None:
            placements.append(_placement(transistor, width * 0.55, height * 0.52, 0))
        rest = [item for item in visible if item is not transistor]
        for index, component in enumerate(rest):
            placements.append(_placement(component, 110 + index * 145, height / 2, 0))
        for index, component in enumerate(ground):
            placements.append(
                _placement(component, width * 0.55, height - 48 - index * 36, 0)
            )
        return placements
    step = max(105.0, min(170.0, (width - 150) / max(1, len(visible))))
    for index, component in enumerate(visible):
        placements.append(_placement(component, 85 + index * step, height / 2, 0))
    for index, component in enumerate(ground):
        placements.append(
            _placement(
                component,
                85 + min(len(visible), 2) * step,
                height - 52 - index * 36,
                0,
            )
        )
    return placements


def _placement(
    component: CircuitComponent, x: float, y: float, rotation: int
) -> SchematicPlacement:
    width, height = _symbol_size(component.type, rotation)
    return SchematicPlacement(
        component_id=component.id,
        x=x,
        y=y,
        rotation=rotation,  # type: ignore[arg-type]
        orientation="vertical" if rotation in {90, 270} else "horizontal",
        symbol_variant=str(component.parameters.get("symbol_variant", "default")),
        bounding_box=SchematicBoundingBox(
            x=x - width / 2, y=y - height / 2, width=width, height=height
        ),
    )


def _symbol_size(component_type: str, rotation: int) -> tuple[float, float]:
    if component_type == "opamp":
        base = (92.0, 72.0)
    elif component_type in {"bjt", "mosfet"}:
        base = (82.0, 78.0)
    elif component_type in _LOGIC_TYPES:
        base = (92.0, 58.0)
    elif component_type == "ground":
        base = (36.0, 36.0)
    else:
        base = (66.0, 48.0)
    return base[::-1] if rotation in {90, 270} else base


def _place_ports(
    circuit: CircuitIR, placements: list[SchematicPlacement]
) -> list[SchematicPort]:
    components = {component.id: component for component in circuit.components}
    result: list[SchematicPort] = []
    for placement in placements:
        component = components[placement.component_id]
        for port, net_id in component.ports.items():
            dx, dy, direction = _port_offset(component.type, port, placement.rotation)
            result.append(
                SchematicPort(
                    component_id=component.id,
                    port=port,
                    net_id=net_id,
                    point=SchematicPoint(x=placement.x + dx, y=placement.y + dy),
                    direction=direction,
                )
            )
    return result


def _port_offset(
    component_type: str, port: str, rotation: int
) -> tuple[float, float, Direction]:
    base: tuple[float, float, Direction]
    if component_type == "ground":
        base = (0.0, -18.0, "up")
    elif component_type == "opamp":
        base = cast(
            tuple[float, float, Direction],
            {
                "plus": (-46.0, -18.0, "left"),
                "minus": (-46.0, 18.0, "left"),
                "out": (46.0, 0.0, "right"),
                "vplus": (0.0, -36.0, "up"),
                "vminus": (0.0, 36.0, "down"),
            }.get(port, (0.0, 0.0, "right")),
        )
    elif component_type == "bjt":
        base = cast(
            tuple[float, float, Direction],
            {
                "b": (-42.0, 0.0, "left"),
                "c": (32.0, -28.0, "right"),
                "e": (32.0, 28.0, "right"),
            }.get(port, (0.0, 0.0, "right")),
        )
    elif component_type == "mosfet":
        base = cast(
            tuple[float, float, Direction],
            {
                "g": (-42.0, 0.0, "left"),
                "d": (32.0, -28.0, "right"),
                "s": (32.0, 28.0, "right"),
                "b": (43.0, 0.0, "right"),
            }.get(port, (0.0, 0.0, "right")),
        )
    elif component_type in _LOGIC_TYPES:
        base = _logic_port_offset(port)
    elif component_type in _TWO_TERMINAL_TYPES:
        if rotation in {90, 270}:
            base = (
                (0.0, -34.0, "up")
                if port in {"p", "a", "cp", "p1"}
                else (0.0, 34.0, "down")
            )
        else:
            base = (
                (-34.0, 0.0, "left")
                if port in {"p", "a", "cp", "p1"}
                else (34.0, 0.0, "right")
            )
    elif len(port) == 1:
        base = (-38.0, 0.0, "left")
    else:
        base = (0.0, 0.0, "right")
    if rotation not in {90, 270}:
        return base
    dx, dy, direction = base
    rotated = (-dy, dx)
    direction_map: dict[Direction, Direction] = {
        "left": "up",
        "up": "right",
        "right": "down",
        "down": "left",
    }
    return rotated[0], rotated[1], direction_map[direction]


def _logic_port_offset(port: str) -> tuple[float, float, Direction]:
    output_ports = {
        "out",
        "out1",
        "out2",
        "y",
        "q",
        "qb",
        "sum",
        "carry",
        "y0",
        "y1",
        "y2",
        "y3",
    }
    if port in output_ports:
        return (46.0, 0.0, "right")
    if port in {"clk", "clock", "enable", "en", "reset", "set"}:
        return (0.0, 32.0, "down")
    return (
        -46.0,
        -16.0 if port.endswith("0") or port in {"in1", "a", "d", "j", "s"} else 16.0,
        "left",
    )


def _route_nets(
    circuit: CircuitIR,
    ports: list[SchematicPort],
    placements: list[SchematicPlacement],
    width: int,
    height: int,
    warnings: list[str],
) -> tuple[list[SchematicWire], list[SchematicJunction]]:
    by_net: dict[str, list[SchematicPort]] = {}
    for port in ports:
        by_net.setdefault(port.net_id, []).append(port)
    obstacles = [item.bounding_box for item in placements]
    wires: list[SchematicWire] = []
    junctions: list[SchematicJunction] = []
    for net_id, net_ports in by_net.items():
        if len(net_ports) < 2:
            continue
        anchor = net_ports[0]
        if len(net_ports) == 2:
            points = _route_pair(
                anchor.point, net_ports[1].point, obstacles, width, height
            )
            wires.append(SchematicWire(net_id=net_id, points=points))
            continue
        horizontal_bus = (
            max(item.point.x for item in net_ports)
            - min(item.point.x for item in net_ports)
        ) >= (
            max(item.point.y for item in net_ports)
            - min(item.point.y for item in net_ports)
        )
        if horizontal_bus:
            bus_y = _grid(median(item.point.y for item in net_ports))
            bus_start = SchematicPoint(
                x=min(item.point.x for item in net_ports), y=bus_y
            )
            bus_end = SchematicPoint(x=max(item.point.x for item in net_ports), y=bus_y)
            wires.append(
                SchematicWire(net_id=net_id, points=[bus_start, bus_end], junction=True)
            )
            for item in net_ports:
                point = SchematicPoint(x=item.point.x, y=bus_y)
                if point.y != item.point.y:
                    wires.append(
                        SchematicWire(
                            net_id=net_id, points=[item.point, point], junction=True
                        )
                    )
                junctions.append(SchematicJunction(net_id=net_id, point=point))
        else:
            bus_x = _grid(median(item.point.x for item in net_ports))
            bus_start = SchematicPoint(
                x=bus_x, y=min(item.point.y for item in net_ports)
            )
            bus_end = SchematicPoint(x=bus_x, y=max(item.point.y for item in net_ports))
            wires.append(
                SchematicWire(net_id=net_id, points=[bus_start, bus_end], junction=True)
            )
            for item in net_ports:
                point = SchematicPoint(x=bus_x, y=item.point.y)
                if point.x != item.point.x:
                    wires.append(
                        SchematicWire(
                            net_id=net_id, points=[item.point, point], junction=True
                        )
                    )
                junctions.append(SchematicJunction(net_id=net_id, point=point))
    return _dedupe_wires(wires), _dedupe_junctions(junctions)


def _route_pair(
    first: SchematicPoint,
    second: SchematicPoint,
    obstacles: list[SchematicBoundingBox],
    width: int,
    height: int,
) -> list[SchematicPoint]:
    if first.x == second.x or first.y == second.y:
        return [first, second]
    candidates = [
        [first, SchematicPoint(x=second.x, y=first.y), second],
        [first, SchematicPoint(x=first.x, y=second.y), second],
    ]
    for offset in (24.0, -24.0, 48.0, -48.0):
        candidates.extend(
            [
                [
                    first,
                    SchematicPoint(x=first.x, y=first.y + offset),
                    SchematicPoint(x=second.x, y=first.y + offset),
                    second,
                ],
                [
                    first,
                    SchematicPoint(x=first.x + offset, y=first.y),
                    SchematicPoint(x=first.x + offset, y=second.y),
                    second,
                ],
            ]
        )
    for points in candidates:
        if all(
            not _segment_hits_obstacle(a, b, obstacles)
            for a, b in zip(points, points[1:], strict=False)
        ):
            return _simplify_points(points)
    return _simplify_points(candidates[0])


def _segment_hits_obstacle(
    first: SchematicPoint, second: SchematicPoint, obstacles: list[SchematicBoundingBox]
) -> bool:
    if first.x != second.x and first.y != second.y:
        return True
    for box in obstacles:
        expanded = SchematicBoundingBox(
            x=box.x - 8, y=box.y - 8, width=box.width + 16, height=box.height + 16
        )
        if first.x == second.x:
            if expanded.x < first.x < expanded.x + expanded.width and _interval_overlap(
                first.y, second.y, expanded.y, expanded.y + expanded.height
            ):
                return True
        elif expanded.y < first.y < expanded.y + expanded.height and _interval_overlap(
            first.x, second.x, expanded.x, expanded.x + expanded.width
        ):
            return True
    return False


def _interval_overlap(first: float, second: float, low: float, high: float) -> bool:
    return max(min(first, second), low) < min(max(first, second), high)


def _place_labels(
    circuit: CircuitIR,
    placements: list[SchematicPlacement],
    ports: list[SchematicPort],
    warnings: list[str],
) -> list[SchematicLabel]:
    labels: list[SchematicLabel] = []
    occupied = [item.bounding_box for item in placements]
    components = {component.id: component for component in circuit.components}
    for placement in placements:
        component = components[placement.component_id]
        text_candidates: list[tuple[str, LabelKind, int]] = []
        if component.type != "ground":
            text_candidates.append((component.label or component.id, "component", 1))
            if component.value is not None:
                text_candidates.append((str(component.value), "value", 2))
            elif component.type in _TWO_TERMINAL_TYPES:
                text_candidates.append(("?", "value", 2))
        for text, kind, priority in text_candidates:
            point = _collision_free_label_point(text, placement, occupied, kind)
            if point is None:
                warnings.append("label_collision_unresolved")
                point = SchematicPoint(x=placement.x, y=max(18.0, placement.y - 40.0))
            labels.append(
                SchematicLabel(
                    text=text,
                    point=point,
                    anchor="middle",
                    target_id=component.id,
                    priority=priority,
                    kind=kind,
                )
            )  # type: ignore[arg-type]
    port_by_net: dict[str, SchematicPort] = {}
    for port in ports:
        port_by_net.setdefault(port.net_id, port)
    visible_net_ids = {
        "in",
        "out",
        "vin",
        "vout",
        "gnd",
        "ground",
        "vcc",
        "vdd",
        "vss",
        "vee",
    }
    for net in circuit.nets:
        text = net.label or (net.id if net.id.casefold() in visible_net_ids else "")
        net_port = port_by_net.get(net.id)
        if text and net_port is not None:
            labels.append(
                SchematicLabel(
                    text=text,
                    point=SchematicPoint(
                        x=net_port.point.x + 8, y=net_port.point.y - 10
                    ),
                    target_id=net.id,
                    priority=3,
                    kind="net",
                )
            )
    for annotation in circuit.annotations:
        target = next(
            (item for item in placements if item.component_id == annotation.target_id),
            None,
        )
        point = (
            SchematicPoint(x=target.x, y=target.y - 72)
            if target
            else SchematicPoint(x=24, y=24 + len(labels) * 16)
        )
        labels.append(
            SchematicLabel(
                text=annotation.text,
                point=point,
                anchor="start",
                target_id=annotation.target_id,
                priority=4,
                kind="annotation",
            )
        )
    return labels


def _collision_free_label_point(
    text: str,
    placement: SchematicPlacement,
    occupied: list[SchematicBoundingBox],
    kind: str,
) -> SchematicPoint | None:
    text_width = max(18.0, len(text) * 7.0)
    label_height = 16.0
    offset = 32.0 if kind == "component" else 54.0
    candidates = [
        SchematicPoint(x=placement.x, y=placement.bounding_box.y - offset),
        SchematicPoint(
            x=placement.x,
            y=placement.bounding_box.y + placement.bounding_box.height + offset - 16,
        ),
        SchematicPoint(x=placement.bounding_box.x - text_width / 2, y=placement.y),
        SchematicPoint(
            x=placement.bounding_box.x + placement.bounding_box.width + text_width / 2,
            y=placement.y,
        ),
    ]
    for point in candidates:
        label_box = SchematicBoundingBox(
            x=point.x - text_width / 2,
            y=point.y - label_height,
            width=text_width,
            height=label_height,
        )
        if not any(_boxes_overlap(label_box, box) for box in occupied):
            return point
    return None


def _boxes_overlap(first: SchematicBoundingBox, second: SchematicBoundingBox) -> bool:
    return not (
        first.x + first.width <= second.x
        or second.x + second.width <= first.x
        or first.y + first.height <= second.y
        or second.y + second.height <= first.y
    )


def _dedupe_wires(wires: Iterable[SchematicWire]) -> list[SchematicWire]:
    seen: set[tuple[str, tuple[tuple[float, float], ...]]] = set()
    result: list[SchematicWire] = []
    for wire in wires:
        points = tuple((item.x, item.y) for item in wire.points)
        reverse = tuple(reversed(points))
        key = (wire.net_id, min(points, reverse))
        if key not in seen:
            seen.add(key)
            result.append(wire)
    return result


def _dedupe_junctions(
    junctions: Iterable[SchematicJunction],
) -> list[SchematicJunction]:
    seen: set[tuple[str, float, float]] = set()
    result: list[SchematicJunction] = []
    for junction in junctions:
        key = (junction.net_id, junction.point.x, junction.point.y)
        if key not in seen:
            seen.add(key)
            result.append(junction)
    return result


def _simplify_points(points: list[SchematicPoint]) -> list[SchematicPoint]:
    result: list[SchematicPoint] = []
    for point in points:
        if result and point == result[-1]:
            continue
        if len(result) >= 2:
            previous, current = result[-1], point
            before = result[-2]
            if (before.x == previous.x == current.x) or (
                before.y == previous.y == current.y
            ):
                result[-1] = current
                continue
        result.append(point)
    return result


def _grid(value: float, spacing: float = 10.0) -> float:
    return round(value / spacing) * spacing
