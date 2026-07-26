from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

import pytest
from app.agents import AgentRegistry
from app.contracts import AgentRequest, AttachmentRef, Intent
from app.core.config import Settings
from app.providers.xingchen import XingchenCloudProvider
from PIL import Image, ImageDraw

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_REAL_XINGCHEN_TESTS") != "1",
        reason="set RUN_REAL_XINGCHEN_TESTS=1 to consume real Xingchen quota",
    ),
]


@pytest.mark.parametrize(
    ("case_id", "question"),
    [
        (
            "series_resistors",
            "10 V理想电压源与2 Ω、3 Ω电阻串联，求回路电流以及两个电阻的电压。",
        ),
        (
            "thevenin_equivalent",
            "12 V理想电压源驱动4 Ω与8 Ω串联分压器，以8 Ω两端为端口，"
            "求戴维宁等效电压和等效电阻。",
        ),
        (
            "rc_transient",
            "100 μF电容初始电压为5 V，经10 kΩ电阻从t=0开始放电，"
            "求时间常数并写出电容电压表达式。",
        ),
        (
            "ac_impedance",
            "频率1 kHz时，10 Ω电阻与10 mH电感串联，求复阻抗的直角坐标形式和幅角形式。",
        ),
    ],
)
async def test_real_solver_ct_text_cases(case_id: str, question: str) -> None:
    settings = Settings(xingchen_enabled=True)
    registry = AgentRegistry()
    assert registry.is_runtime_available("SOLVER_CT_V1", settings)

    request = AgentRequest(
        task_id=f"real-solver-{case_id}",
        session_id="real-xingchen-solver-tests",
        user_id="real-xingchen-solver-tests",
        course_id="CT",
        intent=Intent.SOLVE_PROBLEM,
        canonical_input={"question": question},
        options={"request_id": f"real-solver-{case_id}"},
    )
    provider = XingchenCloudProvider(settings, registry=registry)
    try:
        result = await provider.run("SOLVER_CT_V1", request)
    finally:
        await provider.aclose()

    assert result.provider == "xingchen"
    assert result.agent_id == "SOLVER_CT_V1"
    assert result.answer.strip()
    assert result.structured_result["answer_text"].strip()
    assert result.structured_result["input_type"] == "text"
    assert result.metrics.provider_latency_ms > 0
    assert result.cloud_status.startswith("cloud_")


async def test_real_solver_ct_single_image(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    image_path = storage_root / "real-tests" / "series-circuit.png"
    image_path.parent.mkdir(parents=True)
    image = Image.new("RGB", (720, 360), "white")
    drawing = ImageDraw.Draw(image)
    drawing.line((100, 180, 240, 180), fill="black", width=5)
    drawing.rectangle((240, 145, 480, 215), outline="black", width=5)
    drawing.line((480, 180, 620, 180), fill="black", width=5)
    drawing.text((285, 165), "R = 10 ohm", fill="black")
    drawing.text((80, 120), "U = 5 V", fill="black")
    image.save(image_path, format="PNG")
    data = image_path.read_bytes()

    settings = Settings(
        xingchen_enabled=True,
        local_storage_path=storage_root,
    )
    registry = AgentRegistry()
    assert registry.is_runtime_available("SOLVER_CT_V1", settings)
    request = AgentRequest(
        task_id="real-solver-single-image",
        session_id="real-xingchen-solver-tests",
        user_id="real-xingchen-solver-tests",
        course_id="CT",
        intent=Intent.SOLVE_PROBLEM,
        canonical_input={"question": "请识别图中的已知量并求电阻电流。"},
        attachments=[
            AttachmentRef(
                file_id="real-series-circuit",
                filename=image_path.name,
                content_type="image/png",
                size_bytes=len(data),
                storage_key="local:real-tests/series-circuit.png",
                checksum_sha256=sha256(data).hexdigest(),
            )
        ],
        options={"request_id": "real-solver-single-image"},
    )
    provider = XingchenCloudProvider(settings, registry=registry)
    try:
        result = await provider.run("SOLVER_CT_V1", request)
    finally:
        await provider.aclose()

    assert result.provider == "xingchen"
    assert result.answer.strip()
    assert result.structured_result["input_type"] == "text_and_single_image"
    compact_answer = result.answer.replace(" ", "").casefold()
    assert any(token in compact_answer for token in ("0.5a", "0.50a", "500ma"))
    assert result.metrics.provider_latency_ms > 0
    assert result.cloud_status.startswith("cloud_")
