from __future__ import annotations

from app.circuit import render_circuit
from app.circuit.semantic import (
    circuit_ir_from_text,
    circuit_ir_from_vision_extraction,
)
from app.contracts import AgentRequest, AttachmentRef
from app.core.config import Settings
from app.services.circuit_visualization import (
    decide_circuit_visualization,
    extract_circuit_ir,
)
from app.services.unified_request_preparation import UnifiedRequestPreparationService


def test_explicit_text_divider_becomes_valid_renderable_circuit_ir() -> None:
    text = (
        "请画出典型分压电路：5V 电源串联 R1=1k 和 R2=2k，"
        "输出取 R2 两端，并标出 Vout、GND 和电压极性。"
    )
    circuit = circuit_ir_from_text(text)

    assert circuit is not None
    assert circuit.provenance["source_type"] == "text"
    assert [(item.id, item.ports) for item in circuit.components[:3]] == [
        ("V1", {"p": "vin", "n": "gnd"}),
        ("R1", {"p": "vin", "n": "vout"}),
        ("R2", {"p": "vout", "n": "gnd"}),
    ]
    result = render_circuit(circuit)
    assert result.status == "rendered"
    assert result.professional_renderer_success is True
    assert result.svg is not None
    assert 'data-component-id="R2"' in result.svg
    assert 'data-wire-net="vout"' in result.svg
    assert "Vout" in result.svg


def test_text_adapter_refuses_missing_value_or_topology() -> None:
    assert circuit_ir_from_text("请分析这个电路：V1=5V，R1 和 R2") is None
    assert circuit_ir_from_text("请分析：5V 电源、R1=1k、R2=2k") is None


def test_text_adapter_is_available_only_when_rendering_is_enabled() -> None:
    request = AgentRequest(
        session_id="semantic-session",
        user_id="semantic-user",
        canonical_input={"text": "请绘制：5V 电源串联 R1=1k 和 R2=2k，输出取 R2 两端"},
        options={"circuit_visualization_mode": "controlled"},
    )
    prepared = UnifiedRequestPreparationService(
        Settings(circuit_render_enabled=True, _env_file=None)
    ).attach(request)
    assert extract_circuit_ir(prepared) is not None
    assert decide_circuit_visualization(
        prepared, feature_mode="controlled", course_id="CT"
    ).should_schedule

    disabled = UnifiedRequestPreparationService(
        Settings(circuit_render_enabled=False, _env_file=None)
    ).attach(request)
    assert "circuit_ir" not in disabled.canonical_input


def test_controlled_toggle_triggers_circuit_intent_for_plain_draw_wording() -> None:
    request = AgentRequest(
        session_id="semantic-session-plain",
        user_id="semantic-user",
        canonical_input={
            "text": "请画出典型分压电路：5V 电源串联 R1=1k 和 R2=2k，输出取 R2 两端"
        },
        options={"circuit_visualization_mode": "controlled"},
    )
    prepared = UnifiedRequestPreparationService(Settings(_env_file=None)).attach(
        request
    )
    decision = decide_circuit_visualization(
        prepared, feature_mode="controlled", course_id="CT"
    )
    assert decision.circuit_ir_requested is True
    assert decision.should_schedule is True


def test_structured_vision_extraction_converts_only_with_explicit_terminal_map() -> (
    None
):
    extraction = {
        "diagram_description": "5 V source and a resistor to ground",
        "confidence": 0.96,
        "uncertain_info": [],
        "components": [
            {
                "component_type": "voltage source",
                "label": "V1",
                "value": "5V",
                "connections": ["vin", "gnd"],
                "terminal_map": {"p": "vin", "n": "gnd"},
            },
            {
                "component_type": "resistor",
                "label": "R1",
                "value": "1k",
                "connections": ["vin", "gnd"],
                "terminal_map": {"p": "vin", "n": "gnd"},
            },
            {
                "component_type": "ground",
                "label": "GND",
                "connections": ["gnd"],
                "terminal_map": {"g": "gnd"},
            },
        ],
    }
    circuit = circuit_ir_from_vision_extraction(extraction)
    assert circuit is not None
    assert circuit.provenance["source_type"] == "vision_extraction"
    assert (
        circuit_ir_from_vision_extraction(
            {**extraction, "uncertain_info": ["R1 polarity unclear"]}
        )
        is None
    )
    assert (
        circuit_ir_from_vision_extraction(
            {
                **extraction,
                "components": [
                    {**extraction["components"][1], "terminal_map": {}},
                ],
            }
        )
        is None
    )


def test_multi_image_input_never_falls_back_to_text_coordinates() -> None:
    request = AgentRequest(
        session_id="multi-image-semantic-session",
        user_id="multi-image-semantic-user",
        canonical_input={
            "text": "请画出典型分压电路：5V 电源串联 R1=1k 和 R2=2k，输出取 R2 两端"
        },
        attachments=[
            AttachmentRef(
                file_id="diagram-1",
                filename="diagram-1.png",
                content_type="image/png",
                size_bytes=10,
                storage_key="local:diagram-1",
            ),
            AttachmentRef(
                file_id="diagram-2",
                filename="diagram-2.png",
                content_type="image/png",
                size_bytes=10,
                storage_key="local:diagram-2",
            ),
        ],
        options={"circuit_visualization_mode": "controlled"},
    )
    prepared = UnifiedRequestPreparationService(Settings(_env_file=None)).attach(
        request
    )
    assert "circuit_ir" not in prepared.canonical_input
    assert extract_circuit_ir(prepared) is None
