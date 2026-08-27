from __future__ import annotations

import html
import importlib
from time import perf_counter
from typing import Any, Literal

from app.circuit.contracts import (
    CircuitComponent,
    CircuitIR,
    CircuitRenderOptions,
    CircuitRenderResult,
    ValidationReport,
)
from app.circuit.layout import build_schematic_layout
from app.circuit.layout_contracts import (
    SchematicLabel,
    SchematicLayoutIR,
    SchematicPlacement,
)
from app.circuit.validator import validate_circuit


def render_circuit(
    circuit: CircuitIR, options: CircuitRenderOptions | None = None
) -> CircuitRenderResult:
    """Render a validated CircuitIR into a deterministic textbook-style SVG."""

    started = perf_counter()
    render_options = options or CircuitRenderOptions()
    validation = validate_circuit(circuit)
    if validation.status == "invalid":
        validation.render_status = "invalid"
        return CircuitRenderResult(
            status="failed",
            validation_state=validation.status,
            warnings=[
                *validation.warnings,
                *(issue.message for issue in validation.issues),
            ],
            validation=validation,
            render_latency_ms=(perf_counter() - started) * 1000,
            renderer="none",
            professional_renderer_success=False,
        )
    if (
        not render_options.professional_renderer
        or _try_schemdraw is not _DEFAULT_SCHEMDRAW_HOOK
    ):
        return _render_legacy_path(circuit, render_options, validation, started)
    try:
        layout = build_schematic_layout(
            circuit,
            render_options.template,
            width=render_options.width,
            height=render_options.height,
        )
        svg = _render_svg(circuit, layout, render_options)
        render_warnings = _validate_render_output(circuit, layout, svg)
    except Exception as exc:  # pragma: no cover - defensive renderer boundary
        validation.render_status = "invalid"
        return CircuitRenderResult(
            status="failed",
            validation_state=validation.status,
            warnings=[f"professional_renderer_failed:{type(exc).__name__}"],
            validation=validation,
            render_latency_ms=(perf_counter() - started) * 1000,
            renderer="none",
            professional_renderer_success=False,
        )
    warnings = list(
        dict.fromkeys(
            [
                *validation.warnings,
                *(issue.message for issue in validation.issues),
                *layout.warnings,
                *render_warnings,
            ]
        )
    )
    validation.render_status = (
        "degraded" if render_warnings or layout.warnings else "validated"
    )
    status: Literal["rendered", "degraded"] = (
        "degraded"
        if validation.status != "validated" or render_warnings or layout.warnings
        else "rendered"
    )
    return CircuitRenderResult(
        status=status,
        svg=svg,
        validation_state=validation.status,
        warnings=warnings,
        validation=validation,
        render_latency_ms=(perf_counter() - started) * 1000,
        renderer="professional_svg",
        professional_renderer_success=True,
        layout_schema_version=layout.schema_version,
        template=layout.template,
        width=layout.width,
        height=layout.height,
    )


def _render_svg(
    circuit: CircuitIR,
    layout: SchematicLayoutIR,
    options: CircuitRenderOptions,
) -> str:
    components = {item.id: item for item in circuit.components}
    view_x, view_y, view_width, view_height = _content_view_box(layout)
    pieces = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{view_width:.1f}" '
            f'height="{view_height:.1f}" '
            f'viewBox="{view_x:.1f} {view_y:.1f} {view_width:.1f} '
            f'{view_height:.1f}" role="img" '
            f'aria-label="电路图，布局模板 {html.escape(layout.template)}">'
        ),
        "<title>专业电路图</title>",
        "<desc>由 CircuitIR 确定性布局和 SVG 符号渲染生成</desc>",
        "<style>"
        ".wire{fill:none;stroke:#263746;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}"
        ".symbol{fill:#fff;stroke:#162534;stroke-width:2}"
        ".symbol-line{fill:none;stroke:#162534;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}"
        ".symbol-text{fill:#162534;font:14px system-ui,sans-serif}"
        ".label{fill:#162534;font:13px system-ui,sans-serif}"
        ".value{fill:#465b6b;font:11px system-ui,sans-serif}"
        ".net-label{fill:#0f5b78;font:12px system-ui,sans-serif;font-weight:600}"
        ".annotation{fill:#526475;font:12px system-ui,sans-serif}"
        ".polarity{fill:#162534;font:700 13px system-ui,sans-serif}"
        ".direction-arrow{fill:none;stroke:#0f5b78;stroke-width:1.8;stroke-linecap:round}"
        ".junction{fill:#162534}"
        ".port{fill:#fff;stroke:#0f5b78;stroke-width:1.5}"
        ".unknown{fill:#fff7ed;stroke:#b45309;stroke-width:2;stroke-dasharray:4 3}"
        "</style>",
        '<defs><marker id="circuit-arrow" markerWidth="8" markerHeight="8" '
        'refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8z" '
        'fill="#0f5b78"/></marker></defs>',
        (
            f'<rect x="{view_x:.1f}" y="{view_y:.1f}" '
            f'width="{view_width:.1f}" height="{view_height:.1f}" fill="#ffffff"/>'
        ),
    ]
    for wire in layout.wires:
        points = " ".join(f"{point.x:.1f},{point.y:.1f}" for point in wire.points)
        pieces.append(
            f'<polyline class="wire" data-wire-net="{html.escape(wire.net_id)}" '
            f'points="{points}"/>'
        )
    for junction in layout.junctions:
        pieces.append(
            f'<circle class="junction" '
            f'data-junction-net="{html.escape(junction.net_id)}" '
            f'cx="{junction.point.x:.1f}" cy="{junction.point.y:.1f}" r="4"/>'
        )
    for marker in layout.polarity_markers:
        component_id = html.escape(marker.component_id)
        pieces.extend(
            [
                f'<text class="polarity" data-polarity="{component_id}:positive" '
                f'x="{marker.positive_point.x + 7:.1f}" '
                f'y="{marker.positive_point.y - 7:.1f}">+</text>',
                f'<text class="polarity" data-polarity="{component_id}:negative" '
                f'x="{marker.negative_point.x + 7:.1f}" '
                f'y="{marker.negative_point.y - 7:.1f}">−</text>',
            ]
        )
    for arrow in layout.direction_arrows:
        target_id = html.escape(arrow.target_id or "")
        pieces.append(
            f'<line class="direction-arrow" data-direction-target="{target_id}" '
            f'x1="{arrow.start.x:.1f}" y1="{arrow.start.y:.1f}" '
            f'x2="{arrow.end.x:.1f}" y2="{arrow.end.y:.1f}" '
            'marker-end="url(#circuit-arrow)"/>'
        )
    for placement in layout.placements:
        component = components[placement.component_id]
        pieces.append(_render_component(component, placement))
    for port in layout.ports:
        component = components[port.component_id]
        if component.type in {
            "input",
            "output",
            "logic_input",
            "logic_output",
            "node_label",
        }:
            pieces.append(
                f'<circle class="port" '
                f'data-port="{html.escape(component.id)}.{html.escape(port.port)}" '
                f'cx="{port.point.x:.1f}" cy="{port.point.y:.1f}" r="4"/>'
            )
    if options.include_labels:
        pieces.extend(_render_labels(layout.labels))
        pieces.extend(_render_annotations(layout.annotations))
    pieces.append("</svg>")
    return "".join(pieces)


def _content_view_box(layout: SchematicLayoutIR) -> tuple[float, float, float, float]:
    """Return a padded view box around the actual drawing content.

    Layout coordinates remain in the requested canvas, while the SVG viewport
    is cropped to the content.  This keeps the public layout contract stable
    and prevents a narrow schematic from being rendered as a tiny object in a
    large empty 900x520 canvas.
    """

    left = float(layout.width)
    top = float(layout.height)
    right = 0.0
    bottom = 0.0

    def include_point(x: float, y: float) -> None:
        nonlocal left, top, right, bottom
        left = min(left, x)
        top = min(top, y)
        right = max(right, x)
        bottom = max(bottom, y)

    for placement in layout.placements:
        box = placement.bounding_box
        include_point(box.x, box.y)
        include_point(box.x + box.width, box.y + box.height)
    for wire in layout.wires:
        for point in wire.points:
            include_point(point.x, point.y)
    for junction in layout.junctions:
        include_point(junction.point.x - 4, junction.point.y - 4)
        include_point(junction.point.x + 4, junction.point.y + 4)
    for marker in layout.polarity_markers:
        for point in (marker.positive_point, marker.negative_point):
            include_point(point.x, point.y - 18)
            include_point(point.x + 16, point.y + 4)
    for arrow in layout.direction_arrows:
        include_point(arrow.start.x - 4, arrow.start.y - 4)
        include_point(arrow.end.x + 12, arrow.end.y + 4)
    for label in layout.labels:
        text_width = max(18.0, len(label.text) * 7.0)
        if label.anchor == "middle":
            label_left = label.point.x - text_width / 2
        elif label.anchor == "end":
            label_left = label.point.x - text_width
        else:
            label_left = label.point.x
        include_point(label_left, label.point.y - 18)
        include_point(label_left + text_width, label.point.y + 4)
    for annotation in layout.annotations:
        text_width = max(18.0, len(annotation.text) * 7.0)
        include_point(annotation.point.x, annotation.point.y - 18)
        include_point(annotation.point.x + text_width, annotation.point.y + 4)

    padding = 28.0
    return (
        left - padding,
        top - padding,
        max(1.0, right - left + padding * 2),
        max(1.0, bottom - top + padding * 2),
    )


def _try_schemdraw(circuit: CircuitIR, options: CircuitRenderOptions) -> str:
    """Compatibility hook for the pre-v2 renderer and debug-only fallback tests."""

    schemdraw = importlib.import_module("schemdraw")
    elements = importlib.import_module("schemdraw.elements")
    drawing = schemdraw.Drawing(show=False)
    cursor: tuple[float, float] = (0.0, 0.0)
    for component in circuit.components:
        element_type: Any = {
            "resistor": getattr(elements, "Resistor", None),
            "capacitor": getattr(elements, "Capacitor", None),
            "inductor": getattr(elements, "Inductor", None),
            "diode": getattr(elements, "Diode", None),
            "switch": getattr(elements, "Switch", None),
            "voltage_source": getattr(elements, "SourceV", None),
            "current_source": getattr(elements, "SourceI", None),
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


_DEFAULT_SCHEMDRAW_HOOK = _try_schemdraw


def _render_legacy_path(
    circuit: CircuitIR,
    options: CircuitRenderOptions,
    validation: ValidationReport,
    started: float,
) -> CircuitRenderResult:
    """Keep the old renderer contract available only when explicitly selected."""

    warnings = [*validation.warnings, *(issue.message for issue in validation.issues)]
    try:
        svg = _try_schemdraw(circuit, options)
        renderer = "schemdraw"
        status: Literal["rendered", "degraded"] = "rendered"
        validation.render_status = "validated"
        professional_success = False
    except Exception as exc:
        warnings.append(f"schemdraw_fallback:{type(exc).__name__}")
        try:
            svg = _render_fallback_svg(circuit, options)
        except Exception as fallback_exc:  # pragma: no cover - defensive boundary
            validation.render_status = "invalid"
            return CircuitRenderResult(
                status="failed",
                validation_state=validation.status,
                warnings=[
                    *warnings,
                    f"renderer_failed:{type(fallback_exc).__name__}",
                ],
                validation=validation,
                render_latency_ms=(perf_counter() - started) * 1000,
                renderer="fallback_svg",
            )
        renderer = "fallback_svg"
        status = "degraded"
        validation.render_status = "degraded"
        professional_success = False
    return CircuitRenderResult(
        status=status,
        svg=svg,
        validation_state=validation.status,
        warnings=list(dict.fromkeys(warnings)),
        validation=validation,
        render_latency_ms=(perf_counter() - started) * 1000,
        renderer=renderer,
        professional_renderer_success=professional_success,
    )


def _render_fallback_svg(circuit: CircuitIR, options: CircuitRenderOptions) -> str:
    """Legacy deterministic fallback retained for explicit debug compatibility."""

    layout = build_schematic_layout(
        circuit,
        options.template,
        width=options.width,
        height=options.height,
    )
    return _render_svg(circuit, layout, options)


def _render_component(
    component: CircuitComponent, placement: SchematicPlacement
) -> str:
    body = _symbol_body(component)
    return (
        f'<g data-component-id="{html.escape(component.id)}" '
        f'transform="translate({placement.x:.1f} {placement.y:.1f}) '
        f'rotate({placement.rotation})">'
        f"{body}</g>"
    )


def _symbol_body(component: CircuitComponent) -> str:
    kind = component.type
    if kind == "resistor":
        body = (
            '<path class="symbol-line" d="M-34 0H-24l6-12 12 24 12-24 12 24 6-12H34"/>'
        )
    elif kind == "capacitor":
        body = '<path class="symbol-line" d="M-34 0H-8M-8-16V16M8-16V16M8 0H34"/>'
    elif kind == "inductor":
        body = (
            '<path class="symbol-line" '
            'd="M-34 0h6c0-18 12-18 12 0s12 18 12 0 12-18 12 0h6"/>'
        )
    elif kind == "coupled_inductor":
        body = (
            '<path class="symbol-line" '
            'd="M-34 0h5c0-15 10-15 10 0s10 15 10 0 10-15 10 0h5 '
            "M-29 22h5c0-15 10-15 10 0s10 15 10 0 10-15 10 0h5 "
            'M-5 6v10M5 6v10"/>'
        )
    elif kind in {"voltage_source", "current_source"}:
        marker = "V" if kind == "voltage_source" else "I"
        arrow = (
            '<path class="symbol-line" d="M0 10V-10M0-10l-5 6M0-10l5 6"/>'
            if kind == "current_source"
            else '<path class="symbol-text" d="M-5-7h10M0-12v10M-5 10h10"/>'
        )
        body = (
            f'<circle class="symbol" cx="0" cy="0" r="22"/>'
            f'<text class="symbol-text" x="-5" y="5">{marker}</text>{arrow}'
        )
    elif kind in {"dependent_voltage_source", "dependent_current_source"}:
        marker = "V" if kind == "dependent_voltage_source" else "I"
        arrow = (
            '<path class="symbol-line" d="M0 9V-9M0-9l-4 5M0-9l4 5"/>'
            if kind == "dependent_current_source"
            else ""
        )
        body = (
            '<path class="symbol" d="M0-26L25 0 0 26-25 0z"/>'
            f'<text class="symbol-text" x="-5" y="5">{marker}</text>{arrow}'
        )
    elif kind in {"diode", "zener_diode"}:
        zener = "M20-14l-5 5 5 5" if kind == "zener_diode" else "M20-14V14"
        body = (
            '<path class="symbol-line" '
            f'd="M-34 0H-18M-18-14L12 0-18 14zM12-14V14M20 0H34 {zener}"/>'
        )
    elif kind == "switch":
        body = '<path class="symbol-line" d="M-34 0H-12M12 0H34M-10 0L10-16"/>'
    elif kind == "open_circuit":
        body = '<path class="symbol-line" d="M-34 0H-8M8 0H34M-8 0l-8-12M8 0l8 12"/>'
    elif kind == "short_circuit":
        body = '<path class="symbol-line" d="M-34 0H34"/>'
    elif kind == "ground":
        body = '<path class="symbol-line" d="M0-18V-4M-18 0H18M-11 8H11M-4 16H4"/>'
    elif kind == "opamp":
        body = (
            '<path class="symbol" d="M-24-34L34 0-24 34z"/>'
            '<text class="symbol-text" x="-18" y="-10">+</text>'
            '<text class="symbol-text" x="-18" y="20">−</text>'
        )
    elif kind == "bjt":
        body = (
            '<circle class="symbol" cx="0" cy="0" r="28"/>'
            '<path class="symbol-line" '
            'd="M-8-22V22M-8-12L20-28M-8 12L20 28M14 22l6 6-8-1"/>'
        )
    elif kind == "mosfet":
        body = (
            '<path class="symbol-line" '
            'd="M-12-24V24M-24-18V18M-24 0H-12M-12-18H16 '
            'M-12 18H16M16-18V18M8-4l8 4-8 4"/>'
        )
    elif kind in {"and_gate", "nand_gate", "buffer", "schmitt_trigger"}:
        body = '<path class="symbol" d="M-28-24H0a24 24 0 0 1 0 48h-28z"/>'
        if kind == "buffer" or kind == "schmitt_trigger":
            body = '<path class="symbol" d="M-28-24L24 0-28 24z"/>'
        if kind == "nand_gate":
            body += '<circle class="symbol" cx="31" cy="0" r="5"/>'
    elif kind in {"or_gate", "nor_gate", "xor_gate", "xnor_gate"}:
        body = '<path class="symbol" d="M-30-24Q-4-24 28 0Q-4 24-30 24Q-12 0-30-24z"/>'
        if kind in {"xor_gate", "xnor_gate"}:
            body = (
                '<path class="symbol-line" '
                'd="M-38-24Q-20 0-38 24M-30-24Q-4-24 28 0 '
                'Q-4 24-30 24Q-12 0-30-24z"/>'
            )
        if kind in {"nor_gate", "xnor_gate"}:
            body += '<circle class="symbol" cx="34" cy="0" r="5"/>'
    elif kind == "not_gate":
        body = (
            '<path class="symbol" d="M-28-24L24 0-28 24z"/>'
            '<circle class="symbol" cx="31" cy="0" r="5"/>'
        )
    elif kind in {"d_flip_flop", "jk_flip_flop", "t_flip_flop", "sr_latch"}:
        body = '<rect class="symbol" x="-34" y="-30" width="68" height="60" rx="3"/>'
        text = {
            "d_flip_flop": "D",
            "jk_flip_flop": "JK",
            "t_flip_flop": "T",
            "sr_latch": "SR",
        }[kind]
        body += (
            f'<text class="symbol-text" x="-8" y="5">{text}</text>'
            '<path class="symbol-line" d="M-34 14l8 5-8 5"/>'
        )
    elif kind in {
        "mux",
        "demux",
        "encoder",
        "decoder",
        "half_adder",
        "full_adder",
        "bus",
    }:
        text = {
            "mux": "MUX",
            "demux": "DEMUX",
            "encoder": "ENC",
            "decoder": "DEC",
            "half_adder": "HA",
            "full_adder": "FA",
            "bus": "BUS",
        }[kind]
        body = (
            '<path class="symbol" d="M-30-26L28-18V18L-30 26z"/>'
            f'<text class="symbol-text" x="-18" y="5">{text}</text>'
        )
    elif kind == "clock":
        body = (
            '<circle class="symbol" cx="0" cy="0" r="20"/>'
            '<path class="symbol-line" d="M-10 4V-6H0V6H10V-4"/>'
        )
    elif kind in {"logic_input", "input"}:
        body = (
            '<circle class="symbol" cx="0" cy="0" r="7"/>'
            '<path class="symbol-line" d="M-24 0H-7M-17-5l-7 5 7 5"/>'
        )
    elif kind in {"logic_output", "output"}:
        body = (
            '<circle class="symbol" cx="0" cy="0" r="7"/>'
            '<path class="symbol-line" d="M7 0H24M17-5l7 5-7 5"/>'
        )
    elif kind in {"vcc", "vdd", "vss", "vee"}:
        body = '<path class="symbol-line" d="M0 18V-4M-10-4H10M0-4l-7 8M0-4l7 8"/>'
    elif kind == "node_label":
        body = '<circle class="symbol" cx="0" cy="0" r="5"/>'
    else:
        body = (
            '<rect class="unknown" x="-26" y="-18" width="52" height="36" rx="4"/>'
            '<text class="symbol-text" x="-18" y="5">?</text>'
        )
    return body


def _render_labels(labels: list[SchematicLabel]) -> list[str]:
    rendered: list[str] = []
    for label in labels:
        cls = {
            "component": "label",
            "value": "value",
            "net": "net-label",
            "port": "net-label",
            "annotation": "annotation",
        }[label.kind]
        rendered.append(
            f'<text class="{cls}" '
            f'data-label-target="{html.escape(label.target_id or "")}" '
            f'x="{label.point.x:.1f}" y="{label.point.y:.1f}" '
            f'text-anchor="{label.anchor}">'
            f"{html.escape(label.text)}</text>"
        )
    return rendered


def _render_annotations(annotations: list[Any]) -> list[str]:
    return [
        f'<text class="annotation" '
        f'data-annotation-target="{html.escape(annotation.target_id or "")}" '
        f'x="{annotation.point.x:.1f}" y="{annotation.point.y:.1f}">'
        f"{html.escape(annotation.text)}</text>"
        for annotation in annotations
    ]


def _validate_render_output(
    circuit: CircuitIR, layout: SchematicLayoutIR, svg: str
) -> list[str]:
    warnings: list[str] = []
    if not svg.startswith("<svg"):
        warnings.append("render_svg_root_missing")
    for component in circuit.components:
        if f'data-component-id="{html.escape(component.id)}"' not in svg:
            warnings.append(f"render_component_missing:{component.id}")
    for wire in layout.wires:
        if f'data-wire-net="{html.escape(wire.net_id)}"' not in svg:
            warnings.append(f"render_wire_missing:{wire.net_id}")
    return list(dict.fromkeys(warnings))
