from __future__ import annotations

from dataclasses import dataclass

from app.circuit.contracts import CircuitComponent, CircuitIR

SUPPORTED_TEMPLATES = frozenset(
    {
        "series",
        "parallel",
        "divider",
        "rc_lowpass",
        "rc_highpass",
        "rlc_series",
        "opamp_inverting",
        "opamp_noninverting",
        "source_load",
        "generic_left_to_right",
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


def build_layout(circuit: CircuitIR, template: str) -> CircuitLayout:
    warnings: list[str] = []
    if template not in SUPPORTED_TEMPLATES:
        warnings.append(f"unsupported_template:{template}")
        template = "generic_left_to_right"
    placements: list[ComponentPlacement] = []
    x = 100.0
    for index, component in enumerate(circuit.components):
        row = 0
        if template == "parallel":
            row = index % 3 - 1
        elif (
            template in {"opamp_inverting", "opamp_noninverting"}
            and component.type == "opamp"
        ):
            x = 420.0
        elif template in {"divider", "rc_lowpass", "rc_highpass"} and index == 1:
            x = 300.0
        placements.append(ComponentPlacement(component, x, 180.0 + row * 90.0))
        x += 140.0
    ports = tuple(
        point for placement in placements for point in _port_points(placement)
    )
    return CircuitLayout(tuple(placements), ports, tuple(warnings))


def _port_points(placement: ComponentPlacement) -> list[PortPoint]:
    component = placement.component
    x, y = placement.x, placement.y
    if component.type in {"opamp"}:
        offsets = {
            "plus": (-45, -18),
            "minus": (-45, 18),
            "out": (45, 0),
            "vplus": (0, -35),
            "vminus": (0, 35),
        }
    elif component.type == "bjt":
        offsets = {"b": (-42, 0), "c": (30, -28), "e": (30, 28)}
    elif component.type == "mosfet":
        offsets = {"g": (-42, 0), "d": (30, -28), "s": (30, 28), "b": (45, 0)}
    elif component.type == "ground":
        offsets = {"g": (0, -28)}
    elif len(component.ports) == 1:
        offsets = {next(iter(component.ports)): (-38, 0)}
    else:
        offsets = {
            "p": (-42, 0),
            "n": (42, 0),
            "a": (-42, 0),
            "k": (42, 0),
            "cp": (-42, -25),
            "cn": (-42, 25),
        }
    return [
        PortPoint(
            component.id,
            port,
            x + offsets.get(port, (0, 0))[0],
            y + offsets.get(port, (0, 0))[1],
        )
        for port in component.ports
    ]
