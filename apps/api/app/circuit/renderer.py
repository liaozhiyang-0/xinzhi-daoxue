from __future__ import annotations

import html
import importlib
from time import perf_counter
from typing import Any, Literal

from app.circuit.contracts import CircuitIR, CircuitRenderOptions, CircuitRenderResult
from app.circuit.layout import (
    ComponentPlacement,
    PortPoint,
    build_layout,
)
from app.circuit.validator import validate_circuit


def render_circuit(
    circuit: CircuitIR, options: CircuitRenderOptions | None = None
) -> CircuitRenderResult:
    started = perf_counter()
    render_options = options or CircuitRenderOptions()
    validation = validate_circuit(circuit)
    warnings = [*validation.warnings, *(issue.message for issue in validation.issues)]
    if validation.status == "invalid":
        return CircuitRenderResult(
            status="failed",
            validation_state=validation.status,
            warnings=warnings,
            validation=validation,
            render_latency_ms=(perf_counter() - started) * 1000,
        )
    try:
        svg = _try_schemdraw(circuit, render_options)
        renderer = "schemdraw"
        status: Literal["rendered", "degraded"] = "rendered"
    except Exception as exc:
        warnings.append(f"schemdraw_fallback:{type(exc).__name__}")
        svg = _render_fallback_svg(circuit, render_options)
        renderer = "fallback_svg"
        status = "degraded"
    try:
        svg = _render_fallback_svg(circuit, render_options) if not svg else svg
    except Exception as exc:
        warnings.append(f"renderer_failed:{type(exc).__name__}")
        return CircuitRenderResult(
            status="failed",
            validation_state=validation.status,
            warnings=warnings,
            validation=validation,
            render_latency_ms=(perf_counter() - started) * 1000,
            renderer=renderer,
        )
    return CircuitRenderResult(
        status=status,
        svg=svg,
        validation_state=validation.status,
        warnings=list(dict.fromkeys(warnings)),
        validation=validation,
        render_latency_ms=(perf_counter() - started) * 1000,
        renderer=renderer,
    )


def _try_schemdraw(circuit: CircuitIR, options: CircuitRenderOptions) -> str:
    """Use SchemDraw when installed; callers retain a deterministic fallback."""

    schemdraw = importlib.import_module("schemdraw")
    elm = importlib.import_module("schemdraw.elements")

    drawing = schemdraw.Drawing(show=False)
    cursor: tuple[float, float] = (0.0, 0.0)
    for component in circuit.components:
        element_type: Any = {
            "resistor": getattr(elm, "Resistor", None),
            "capacitor": getattr(elm, "Capacitor", None),
            "inductor": getattr(elm, "Inductor", None),
            "diode": getattr(elm, "Diode", None),
            "switch": getattr(elm, "Switch", None),
            "voltage_source": getattr(elm, "SourceV", None),
            "current_source": getattr(elm, "SourceI", None),
        }.get(component.type)
        if element_type is None:
            raise RuntimeError(f"schemdraw_symbol_unavailable:{component.type}")
        element = element_type().at(cursor)
        if options.include_values and component.value is not None:
            element = element.label(str(component.value))
        drawing += element
        cursor = (cursor[0] + 2.5, cursor[1])
    image = drawing.get_imagedata("svg")
    return image.decode("utf-8") if isinstance(image, bytes) else str(image)


def _render_fallback_svg(circuit: CircuitIR, options: CircuitRenderOptions) -> str:
    layout = build_layout(circuit, options.template)
    port_map = {(point.component_id, point.port): point for point in layout.ports}
    net_ports: dict[str, list[PortPoint]] = {}
    for component in circuit.components:
        for port, net_id in component.ports.items():
            point = port_map.get((component.id, port))
            if point is not None:
                net_ports.setdefault(net_id, []).append(point)
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{options.width}" '
        f'height="{options.height}" viewBox="0 0 {options.width} {options.height}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    for points in net_ports.values():
        if not points:
            continue
        anchor = points[0]
        for point in points[1:]:
            pieces.append(
                f'<line x1="{anchor.x:.1f}" y1="{anchor.y:.1f}" '
                f'x2="{point.x:.1f}" y2="{point.y:.1f}" '
                'stroke="#334155" stroke-width="2"/>'
            )
        for point in points:
            pieces.append(
                f'<circle cx="{point.x:.1f}" cy="{point.y:.1f}" r="3" fill="#334155"/>'
            )
    for placement in layout.placements:
        pieces.extend(_component_svg(placement, options))
    for annotation in circuit.annotations:
        pieces.append(
            f'<text x="20" y="{30 + len(pieces) * 2}" '
            f'font-family="sans-serif" font-size="12">'
            f"{html.escape(annotation.text)}</text>"
        )
    pieces.append("</svg>")
    return "".join(pieces)


def _component_svg(
    placement: ComponentPlacement, options: CircuitRenderOptions
) -> list[str]:
    component = placement.component
    x, y = placement.x, placement.y
    label = html.escape(component.label or component.id)
    value = (
        html.escape(str(component.value))
        if options.include_values and component.value is not None
        else ""
    )
    if component.type == "opamp":
        shape = (
            f'<polygon points="{x - 24},{y - 32} {x - 24},{y + 32} '
            f'{x + 34},{y}" fill="#f8fafc" stroke="#0f172a"/>'
        )
    elif component.type in {"bjt", "mosfet"}:
        shape = f'<circle cx="{x}" cy="{y}" r="27" fill="#f8fafc" stroke="#0f172a"/>'
    elif component.type == "ground":
        shape = (
            f'<path d="M{x - 14},{y - 12} H{x + 14} '
            f'M{x - 9},{y - 5} H{x + 9} M{x - 4},{y + 2} H{x + 4}" '
            'stroke="#0f172a" stroke-width="2"/>'
        )
    elif component.type in {"voltage_source", "current_source"}:
        symbol = "V" if component.type == "voltage_source" else "I"
        shape = (
            f'<circle cx="{x}" cy="{y}" r="20" fill="#f8fafc" '
            f'stroke="#0f172a"/><text x="{x - 5}" y="{y + 5}" '
            f'font-family="sans-serif" font-size="13">{symbol}</text>'
        )
    elif component.type in {"input", "output", "node_label"}:
        shape = f'<circle cx="{x}" cy="{y}" r="6" fill="#2563eb" stroke="#0f172a"/>'
    else:
        shape = (
            f'<rect x="{x - 24}" y="{y - 14}" width="48" height="28" '
            'rx="4" fill="#f8fafc" stroke="#0f172a"/>'
        )
    text = (
        f'<text x="{x - 24}" y="{y - 24}" font-family="sans-serif" '
        f'font-size="12" fill="#0f172a">{label}</text>'
    )
    if value:
        text += (
            f'<text x="{x - 24}" y="{y + 33}" font-family="sans-serif" '
            f'font-size="11" fill="#475569">{value}</text>'
        )
    return [shape, text]
