from __future__ import annotations

import json
from statistics import quantiles
from time import perf_counter
from typing import Any

import pytest
from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, AttachmentRef
from app.core.config import PROJECT_ROOT, Settings

CASES_PATH = PROJECT_ROOT / "evaluation" / "automatic_routing" / "cases.json"


def _cases() -> list[dict[str, Any]]:
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return payload


def _settings() -> Settings:
    return Settings(
        app_env="test",
        _env_file=None,
    )


def _request(case: dict[str, Any]) -> AgentRequest:
    attachments = [
        AttachmentRef(
            file_id=f"file-{index}",
            filename=str(item["filename"]),
            content_type=str(item["content_type"]),
            size_bytes=100,
            storage_key=f"local:{item['filename']}",
        )
        for index, item in enumerate(case["attachments"], start=1)
    ]
    return AgentRequest(
        session_id="session-routing-fixture",
        user_id="user-routing-fixture",
        scene="dispatch",
        course_id=str(case.get("course_hint", "AUTO")),
        intent="unknown",
        canonical_input={"text": case["user_input"]},
        attachments=attachments,
        options={
            **dict(case.get("session_context", {})),
        },
    )


def test_automatic_routing_fixture_has_exactly_70_contract_cases() -> None:
    cases = _cases()

    assert len(cases) == 70
    assert len({str(case["case_id"]) for case in cases}) == 70
    required_keys = {
        "case_id",
        "user_input",
        "session_context",
        "attachments",
        "expected_agent_id",
        "expected_intent",
        "expected_status",
        "required_fields",
        "forbidden_agent_ids",
        "manual_review_required",
    }
    assert all(required_keys <= set(case) for case in cases)


@pytest.mark.parametrize("case", _cases(), ids=lambda case: str(case["case_id"]))
def test_automatic_routing_case(case: dict[str, Any]) -> None:
    decision = TaskRouter(AgentRegistry(), _settings()).route(_request(case))

    assert decision.route_status.value == case["expected_status"]
    assert decision.agent_id == case["expected_agent_id"]
    if case["expected_status"] == "selected":
        assert decision.intent == case["expected_intent"]
        assert decision.course_id == case["expected_course_id"]
    assert decision.agent_id not in set(case["forbidden_agent_ids"])
    extracted = decision.material_extraction.get("materials", {})
    for field in case["required_fields"]:
        assert extracted.get(field), f"{case['case_id']} missing extracted {field}"
    assert decision.requires_pipeline is bool(case.get("requires_pipeline", False))


def test_local_router_and_material_extractor_p95_are_below_50ms() -> None:
    router = TaskRouter(AgentRegistry(), _settings())
    timings: list[float] = []
    material_timings: list[float] = []
    cases = _cases()
    for _ in range(5):
        for case in cases:
            started = perf_counter()
            decision = router.route(_request(case))
            timings.append((perf_counter() - started) * 1000)
            material_timings.append(
                float(decision.material_extraction.get("latency_ms", 0))
            )
    route_p95 = quantiles(timings, n=20)[18]
    material_p95 = quantiles(material_timings, n=20)[18]

    assert route_p95 < 50
    assert material_p95 < 50
