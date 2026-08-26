"""Conservative semantic adapters for circuit rendering.

The renderer must receive a semantic graph, never coordinates guessed from a
sentence or from an image summary.  This module therefore accepts only small,
explicit topologies whose component values and connections are unambiguous.
Incomplete or ambiguous input returns ``None`` so the normal Solver answer can
continue without manufacturing a circuit drawing.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.circuit.contracts import (
    PORT_CONTRACTS,
    CircuitAnnotation,
    CircuitComponent,
    CircuitIR,
    CircuitNet,
)
from app.circuit.validator import validate_circuit

_VALUE = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*(?:[pnumkKMGTμµ])?(?:Ω|ohm|[VvAaFfHhWw])?"
_COMPONENT_TOKEN = re.compile(
    rf"(?P<id>[RCL]\d+)\s*(?:=|＝|:|为|是|\s)\s*(?P<value>{_VALUE})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_BARE_COMPONENT = re.compile(
    r"(?<![A-Za-z0-9])([RCL]\d+)(?![A-Za-z0-9])", re.IGNORECASE
)
_SOURCE_ASSIGNMENT = re.compile(
    rf"(?P<id>[VI]\d+)\s*(?:=|＝|:|为|是|\s)+\s*(?P<value>{_VALUE})(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_VALUE_BEFORE_SOURCE = re.compile(
    rf"(?P<value>{_VALUE})\s*(?P<kind>电压源|电流源|电源|voltage\s+source|current\s+source|voltage\s+supply)",
    re.IGNORECASE,
)

_COMPONENT_TYPES = {"r": "resistor", "c": "capacitor", "l": "inductor"}
_VISION_TYPE_ALIASES = {
    "r": "resistor",
    "resistor": "resistor",
    "电阻": "resistor",
    "c": "capacitor",
    "capacitor": "capacitor",
    "电容": "capacitor",
    "l": "inductor",
    "inductor": "inductor",
    "电感": "inductor",
    "voltage_source": "voltage_source",
    "voltage source": "voltage_source",
    "电压源": "voltage_source",
    "current_source": "current_source",
    "current source": "current_source",
    "电流源": "current_source",
    "ground": "ground",
    "gnd": "ground",
    "地": "ground",
    "diode": "diode",
    "二极管": "diode",
    "zener": "zener_diode",
    "zener_diode": "zener_diode",
    "稳压二极管": "zener_diode",
    "opamp": "opamp",
    "op-amp": "opamp",
    "运放": "opamp",
    "bjt": "bjt",
    "三极管": "bjt",
    "mosfet": "mosfet",
    "mos": "mosfet",
    "场效应管": "mosfet",
    "switch": "switch",
    "开关": "switch",
}


def circuit_ir_from_text(text: str) -> CircuitIR | None:
    """Parse one explicit, bounded textbook topology from text.

    Supported forms intentionally stay narrow: a single independent source
    followed by explicitly valued R/C/L components in series or parallel.
    A reference node is added deterministically.  Natural-language circuit
    questions without complete values or an explicit topology are rejected.
    """

    source = _parse_source(text)
    if source is None:
        return None
    component_matches = list(_COMPONENT_TOKEN.finditer(text))
    if not component_matches:
        return None
    bare_ids = {match.group(1).upper() for match in _BARE_COMPONENT.finditer(text)}
    parsed_ids = {match.group("id").upper() for match in component_matches}
    if bare_ids != parsed_ids:
        return None
    topology = _topology_kind(text)
    if topology is None:
        return None
    if len(component_matches) > 12:
        return None

    specs = sorted(
        [
            (
                match.group("id").upper(),
                match.group("value").replace(" ", ""),
                match.start(),
            )
            for match in component_matches
        ],
        key=lambda item: item[2],
    )
    components: list[CircuitComponent] = [
        CircuitComponent(
            id=source[0],
            type=source[1],
            ports={"p": "vin", "n": "gnd"},
            value=source[2],
            label=source[0],
        )
    ]
    nets = [
        CircuitNet(id="vin", label="Vin", kind="power"),
        CircuitNet(id="gnd", label="GND", kind="reference"),
    ]
    annotations: list[CircuitAnnotation] = []
    output_id = _output_component_id(text, specs)
    if topology == "series":
        previous = "vin"
        for index, (component_id, value, _) in enumerate(specs):
            is_last = index == len(specs) - 1
            next_net = "gnd" if is_last else f"n{index + 1}"
            if not is_last and specs[index + 1][0] == output_id:
                next_net = "vout"
            components.append(
                CircuitComponent(
                    id=component_id,
                    type=_COMPONENT_TYPES[component_id[0].lower()],
                    ports={"p": previous, "n": next_net},
                    value=value,
                    label=component_id,
                )
            )
            if next_net not in {item.id for item in nets}:
                nets.append(
                    CircuitNet(
                        id=next_net,
                        label="Vout" if next_net == "vout" else None,
                        kind="signal",
                    )
                )
            previous = next_net
    else:
        nets.append(CircuitNet(id="vout", label="Vout", kind="signal"))
        for component_id, value, _ in specs:
            components.append(
                CircuitComponent(
                    id=component_id,
                    type=_COMPONENT_TYPES[component_id[0].lower()],
                    ports={"p": "vin", "n": "vout"},
                    value=value,
                    label=component_id,
                )
            )

    components.append(
        CircuitComponent(id="GND", type="ground", ports={"g": "gnd"}, label="GND")
    )
    if output_id is not None:
        annotations.append(
            CircuitAnnotation(
                kind="arrow",
                text="Vout: 输出取 " + output_id + " 两端",
                target_id=output_id,
            )
        )
    circuit = CircuitIR(
        components=components,
        nets=nets,
        annotations=annotations,
        assumptions=["仅依据题干中明确给出的元件、数值和串并联关系建立拓扑"],
        provenance={
            "source_type": "text",
            "parser": "circuit_text_v1",
            "trusted": True,
            "source_excerpt": text.strip()[:1000],
        },
        topology_hint="series" if topology == "series" else "parallel",
    )
    report = validate_circuit(circuit)
    return circuit if report.status == "validated" else None


def circuit_ir_from_vision_extraction(
    extraction: Mapping[str, Any] | Any,
) -> CircuitIR | None:
    """Convert an already structured, high-confidence VisionExtraction.

    No geometry is inferred here.  Every component must carry an explicit
    terminal map; uncertain or incomplete model output is refused.
    """

    data = _mapping(extraction)
    if not data or float(data.get("confidence", 0) or 0) < 0.75:
        return None
    if data.get("uncertain_info"):
        return None
    raw_components = data.get("components")
    if not isinstance(raw_components, list) or not raw_components:
        return None
    components: list[CircuitComponent] = []
    net_ids: set[str] = set()
    labels: set[str] = set()
    annotations: list[CircuitAnnotation] = []
    for raw in raw_components:
        item = _mapping(raw)
        if not item or item.get("certainty", "certain") != "certain":
            return None
        component_id = str(item.get("label") or "").strip()
        if not component_id or component_id in labels:
            return None
        labels.add(component_id)
        component_type = _normalise_component_type(item.get("component_type"))
        if component_type is None:
            return None
        terminal_map = _string_mapping(item.get("terminal_map"))
        if not terminal_map:
            return None
        required, _ = PORT_CONTRACTS[component_type]
        if not required.issubset(terminal_map):
            return None
        for net_id in terminal_map.values():
            if not net_id:
                return None
            normalized = _normalise_net_id(net_id)
            net_ids.add(normalized)
            terminal_map = {
                port: (normalized if value == net_id else value)
                for port, value in terminal_map.items()
            }
        components.append(
            CircuitComponent(
                id=component_id,
                type=component_type,
                ports=terminal_map,
                value=item.get("value"),
                label=component_id,
            )
        )
        if item.get("polarity"):
            annotations.append(
                CircuitAnnotation(
                    kind="text",
                    text=f"极性: {str(item['polarity'])[:120]}",
                    target_id=component_id,
                )
            )
        if item.get("reference_direction"):
            annotations.append(
                CircuitAnnotation(
                    kind="arrow",
                    text=str(item["reference_direction"])[:120],
                    target_id=component_id,
                )
            )
    if "ground" not in {item.type for item in components} and not any(
        net.casefold() in {"gnd", "ground", "0"} for net in net_ids
    ):
        return None
    nets = [
        CircuitNet(
            id=net_id,
            label="GND" if net_id == "gnd" else None,
            kind="reference" if net_id == "gnd" else "unknown",
        )
        for net_id in sorted(net_ids)
    ]
    circuit = CircuitIR(
        components=components,
        nets=nets,
        annotations=annotations,
        assumptions=["拓扑仅来自视觉模型输出中的显式 terminal_map"],
        provenance={"source_type": "vision_extraction", "trusted": True},
        topology_hint="vision_structured",
    )
    return circuit if validate_circuit(circuit).status == "validated" else None


def _parse_source(text: str) -> tuple[str, str, str] | None:
    assignment = _SOURCE_ASSIGNMENT.search(text)
    if assignment:
        source_id = assignment.group("id").upper()
        value = assignment.group("value").replace(" ", "")
        source_type = (
            "current_source" if source_id.startswith("I") else "voltage_source"
        )
        return source_id, source_type, value
    match = _VALUE_BEFORE_SOURCE.search(text)
    if not match:
        return None
    value = match.group("value").replace(" ", "")
    kind = match.group("kind").casefold()
    source_type = (
        "current_source" if "电流" in kind or "current" in kind else "voltage_source"
    )
    return ("I1" if source_type == "current_source" else "V1", source_type, value)


def _topology_kind(text: str) -> str | None:
    normalized = text.casefold()
    if any(marker in normalized for marker in ("并联", "parallel")):
        return "parallel"
    if any(marker in normalized for marker in ("串联", "series", "分压", "divider")):
        return "series"
    return None


def _output_component_id(text: str, specs: list[tuple[str, str, int]]) -> str | None:
    normalized = text.casefold()
    if not any(marker in normalized for marker in ("输出", "vout", "output")):
        return None
    # Prefer the first output marker that is followed by a component.  A
    # common textbook sentence says "输出取 R2 两端，并标出 Vout"; using the
    # last marker would start at Vout and lose the actual output component.
    marker_positions = sorted(
        position
        for marker in ("输出", "vout", "output")
        for position in [normalized.find(marker)]
        if position >= 0
    )
    for marker_position in marker_positions:
        tail = normalized[marker_position:]
        for component_id, _, _ in specs:
            if re.search(
                rf"(?<![a-z0-9]){re.escape(component_id.casefold())}(?![a-z0-9])",
                tail,
            ):
                return component_id
    return None


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _string_mapping(value: Any) -> dict[str, str]:
    data = _mapping(value)
    if data is None:
        return {}
    return {
        str(key).strip(): _normalise_net_id(str(item).strip())
        for key, item in data.items()
        if str(key).strip() and str(item).strip()
    }


def _normalise_net_id(value: str) -> str:
    normalized = re.sub(r"\s+", "_", value.strip())
    return (
        "gnd" if normalized.casefold() in {"gnd", "ground", "0", "地"} else normalized
    )


def _normalise_component_type(value: Any) -> str | None:
    normalized = str(value or "").strip().casefold().replace("_", " ")
    return _VISION_TYPE_ALIASES.get(normalized) or _VISION_TYPE_ALIASES.get(
        normalized.replace(" ", "_")
    )


__all__ = ["circuit_ir_from_text", "circuit_ir_from_vision_extraction"]
