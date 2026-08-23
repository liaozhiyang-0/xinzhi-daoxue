from __future__ import annotations

import base64
import hashlib
import json
import re
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from app.agents import AgentRegistry, TaskRouter
from app.contracts import AgentRequest, AttachmentRef, Intent
from app.contracts.solver import AcademicProblem
from app.core.config import Settings
from app.multimodal import MultiImageComposer, SourceImage
from app.services.solver_boundary_policy import SolverBoundaryPolicy
from PIL import Image

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "team_feedback_31_scenarios.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TEAM_MEMBER_TWO_HTML = REPOSITORY_ROOT / "组员反馈" / "组员二反馈.html"
_PROVIDER_FREE_MODEL_REQUIRED_SCENARIOS = frozenset(
    {"G2-05", "G2-12", "G2-13"}
)
_PROVIDER_FREE_EXTERNAL_RETRIEVAL_REQUIRED_SCENARIOS = frozenset(
    {"G2-01", "G2-06", "G2-14", "G2-15"}
)


class _TeamMemberTwoPromptParser(HTMLParser):
    """Extract the first italicized prompt under each numbered HTML heading."""

    def __init__(self) -> None:
        super().__init__()
        self._heading_number = ""
        self._heading_parts: list[str] = []
        self._in_heading = False
        self._in_prompt = False
        self._prompt_parts: list[str] = []
        self.prompts: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "h1":
            self._in_heading = True
            self._heading_parts = []
        elif tag == "em" and self._heading_number not in self.prompts:
            self._in_prompt = True
            self._prompt_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self._in_heading = False
            heading = "".join(self._heading_parts).strip()
            match = re.match(r"(?P<number>\d+)", heading)
            self._heading_number = match.group("number") if match else ""
        elif tag == "em" and self._in_prompt:
            self._in_prompt = False
            prompt = "".join(self._prompt_parts).strip()
            if self._heading_number and prompt:
                self.prompts[self._heading_number] = prompt

    def handle_data(self, data: str) -> None:
        if self._in_heading:
            self._heading_parts.append(data)
        elif self._in_prompt:
            self._prompt_parts.append(data)


def _team_member_two_raw_prompts() -> dict[str, str]:
    parser = _TeamMemberTwoPromptParser()
    parser.feed(TEAM_MEMBER_TWO_HTML.read_text(encoding="utf-8"))
    return parser.prompts


def _team_member_two_raw_cases() -> list[dict[str, Any]]:
    raw_prompts = _team_member_two_raw_prompts()
    cases: list[dict[str, Any]] = []
    for case in _cases():
        if not str(case["scenario_id"]).startswith("G2-"):
            continue
        match = re.search(r"html#(?P<number>\d+)", str(case["source_ref"]))
        assert match is not None, case["scenario_id"]
        raw_case = dict(case)
        raw_case["prompt"] = raw_prompts[match.group("number")]
        cases.append(raw_case)
    return cases


def _cases() -> list[dict[str, Any]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return payload


def _request(case: dict[str, Any]) -> AgentRequest:
    attachments = [
        AttachmentRef(
            file_id=f"team-feedback-{case['scenario_id']}-{index}",
            filename=str(item["filename"]),
            content_type=str(item["content_type"]),
            size_bytes=1,
            storage_key=f"fixture:{item['filename']}",
        )
        for index, item in enumerate(case.get("attachments", []), start=1)
    ]
    options: dict[str, object] = {
        "allow_cloud": False,
        "team_feedback_scenario_id": str(case["scenario_id"]),
    }
    for key in ("previous_agent", "previous_intent", "task_subtype"):
        if key in case:
            options[key] = case[key]
    if case.get("visual_acceptance"):
        options["visual_acceptance"] = case["visual_acceptance"]
    if case.get("formula_output_contract"):
        options["formula_output_contract"] = case["formula_output_contract"]
    return AgentRequest(
        session_id="team-feedback-matrix",
        user_id="team-feedback-matrix-user",
        scene="dispatch",
        course_id=str(case["course_id"]),
        intent=Intent.UNKNOWN,
        canonical_input={"text": str(case["prompt"])},
        attachments=attachments,
        options=options,
    )


def test_team_feedback_fixture_has_all_31_scenarios_and_required_metadata() -> None:
    cases = _cases()
    ids = [str(case["scenario_id"]) for case in cases]

    assert len(cases) == 31
    assert len(set(ids)) == 31
    assert {item.split("-")[0] for item in ids} == {"G1", "G2"}
    assert sum(item.startswith("G1-") for item in ids) == 14
    assert sum(item.startswith("G2-") for item in ids) == 17

    required = {
        "scenario_id",
        "source",
        "source_ref",
        "course_id",
        "prompt",
        "expected_agent_id",
        "expected_intent",
        "attachments",
        "required_contracts",
    }
    assert all(required <= set(case) for case in cases)
    assert all(str(case["prompt"]).strip() for case in cases)
    assert all(case["required_contracts"] for case in cases)
    assert all(
        not case["attachments"]
        or (
            case.get("visual_acceptance", {}).get("must_capture")
            and case.get("visual_acceptance", {}).get("refuse_if_missing")
        )
        for case in cases
    )
    assert all(
        bool(case["attachments"])
        == (case["scenario_id"] in {f"G1-Q{i:02d}" for i in range(1, 10)})
        for case in cases
    )


def test_math_feedback_cases_declare_formula_output_contracts() -> None:
    cases = {str(case["scenario_id"]): case for case in _cases()}

    g2_03 = cases["G2-03"]["formula_output_contract"]
    assert g2_03["minimum_equations"] >= 1
    assert g2_03["require_step_expressions"] is True
    assert g2_03["require_formula_ast"] is True
    assert "频移" in g2_03["required_markers"]

    g2_07 = cases["G2-07"]["formula_output_contract"]
    assert g2_07["minimum_equations"] >= 2
    assert g2_07["require_formula_ast"] is True
    assert g2_07["require_unit_consistency"] is True
    assert "Hz" in g2_07["required_units"]
    assert set(("闭环带宽", "相位", "幅值")) <= set(
        g2_07["required_markers"]
    )


def test_team_feedback_image_fixture_matches_original_feedback_bytes() -> None:
    image_cases = [case for case in _cases() if case["attachments"]]

    assert len(image_cases) == 9
    for case in image_cases:
        attachment = case["attachments"][0]
        source_path = (REPOSITORY_ROOT / str(attachment["source_path"])).resolve()

        assert source_path.is_relative_to(REPOSITORY_ROOT)
        assert source_path.is_file(), case["scenario_id"]
        payload = source_path.read_bytes()
        assert len(payload) == attachment["size_bytes"], case["scenario_id"]
        assert (
            hashlib.sha256(payload).hexdigest() == attachment["sha256"]
        ), case["scenario_id"]

        with Image.open(source_path) as image:
            assert image.format == "PNG"
            assert image.size == (attachment["width"], attachment["height"])


def test_team_feedback_images_pass_multimodal_preparation() -> None:
    settings = Settings(app_env="test", _env_file=None)
    image_cases = [case for case in _cases() if case["attachments"]]

    for case in image_cases:
        attachment = case["attachments"][0]
        source_path = REPOSITORY_ROOT / str(attachment["source_path"])
        prepared = MultiImageComposer(settings).prepare(
            [
                SourceImage(
                    filename=str(attachment["filename"]),
                    mime_type=str(attachment["content_type"]),
                    data=source_path.read_bytes(),
                )
            ]
        )

        assert prepared.strategy == "single"
        assert prepared.source_count == 1
        image_input = prepared.images[0]
        assert image_input.source_type == "base64"
        encoded = image_input.value.split(",", maxsplit=1)[1]
        with Image.open(BytesIO(base64.b64decode(encoded))) as image:
            assert image.width <= settings.image_max_long_edge
            assert image.height <= settings.image_max_long_edge


@pytest.mark.parametrize(
    "case",
    [case for case in _cases() if case["attachments"]],
    ids=lambda case: f"unstructured-{case['scenario_id']}",
)
def test_team_feedback_image_without_structured_visual_data_is_blocked(
    case: dict[str, Any],
) -> None:
    problem = AcademicProblem(
        course=str(case["course_id"]),
        problem_text=str(case["prompt"]),
        figures_given=[{"filename": case["attachments"][0]["filename"]}],
    )

    decision = SolverBoundaryPolicy().evaluate(problem)

    assert decision.intercepted
    assert decision.reason == "visual_topology_not_structured"
    assert decision.can_continue is False


@pytest.mark.parametrize(
    "case",
    _cases(),
    ids=lambda case: str(case["scenario_id"]),
)
def test_team_feedback_scenario_routes_to_declared_capability(
    case: dict[str, Any],
) -> None:
    decision = TaskRouter(AgentRegistry()).route(_request(case))

    assert decision.route_status.value == "selected", case["scenario_id"]
    assert decision.agent_id == case["expected_agent_id"], case["scenario_id"]
    assert decision.intent == case["expected_intent"], case["scenario_id"]


def test_team_member_two_raw_html_prompts_route_to_declared_capability() -> None:
    assert TEAM_MEMBER_TWO_HTML.is_file()
    member_two_cases = _team_member_two_raw_cases()

    assert len(member_two_cases) == 17
    for case in member_two_cases:
        decision = TaskRouter(AgentRegistry()).route(_request(case))

        assert decision.route_status.value == "selected", case["scenario_id"]
        assert decision.agent_id == case["expected_agent_id"], case["scenario_id"]
        assert decision.intent == case["expected_intent"], case["scenario_id"]


@pytest.mark.parametrize(
    "case",
    _team_member_two_raw_cases(),
    ids=lambda case: f"local-runtime-{case['scenario_id']}",
)
def test_team_member_two_raw_prompt_reaches_local_runtime_contract(
    case: dict[str, Any], api
) -> None:
    session = api.create_session()
    options: dict[str, Any] = {
        "allow_cloud": False,
        "use_local_rag": False,
        "team_feedback_scenario_id": str(case["scenario_id"]),
    }
    for key in ("previous_agent", "previous_intent", "task_subtype"):
        if key in case:
            options[key] = case[key]
    payload = api.task_payload(
        session["id"],
        intent="unknown",
        user_role="admin",
        options=options,
    )
    payload.update(
        {
            "scene": "dispatch",
            "course_id": str(case["course_id"]),
            "canonical_input": {"text": str(case["prompt"])},
        }
    )
    response = api.client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 202, response.text
    created = response.json()
    assert created["route_status"] == "selected", case["scenario_id"]
    assert created["agent_id"] == case["expected_agent_id"], case["scenario_id"]
    assert created["intent"] == case["expected_intent"], case["scenario_id"]
    routing = created["input_content"]["options"].get("_routing") or {}
    availability = routing.get("availability") or {}
    contract = created["input_content"]["options"].get("scenario_contract")
    if isinstance(contract, dict) and str(case["course_id"]).upper() not in {
        "",
        "AUTO",
        "UNKNOWN",
    }:
        assert contract["course"] == str(created["course_id"]).upper()

    completed = api.wait_for_task(
        created["id"],
        statuses={"completed", "failed", "waiting_review", "waiting_user"},
        timeout=30,
    )
    if completed["status"] == "waiting_review":
        controls = api.client.get(
            f"/api/v1/tasks/{created['id']}/runtime-controls"
        )
        assert controls.status_code == 200, controls.text
        projection = controls.json()
        approval = api.client.post(
            f"/api/v1/tasks/{created['id']}/approve",
            params={"runtime_run_id": projection["runtime_run_id"]},
            json={
                "decision": "approved",
                "reason": "feedback runtime contract replay",
                "expected_state_version": projection["state_version"],
            },
        )
        assert approval.status_code in {200, 202}, approval.text
        completed = api.wait_for_task(created["id"], timeout=30)

    if case["scenario_id"] in _PROVIDER_FREE_EXTERNAL_RETRIEVAL_REQUIRED_SCENARIOS:
        assert availability["external_retrieval_required"] is True
        assert availability["external_retrieval_available"] is False
        assert completed["status"] == "failed", json.dumps(
            completed, ensure_ascii=False, sort_keys=True
        )
        assert completed["failure_category"] == "external_retrieval_unavailable"
        assert completed["result_content"] is None
        assert str(completed["error_message"] or "").strip()
        return

    if case["scenario_id"] in _PROVIDER_FREE_MODEL_REQUIRED_SCENARIOS:
        assert availability["generation_required"] is True
        assert availability["generation_available"] is False
        assert completed["status"] == "failed", json.dumps(
            completed, ensure_ascii=False, sort_keys=True
        )
        assert completed["failure_category"] == "model_generation_required"
        assert completed["result_content"] is None
        assert str(completed["error_message"] or "").strip()
        return

    assert completed["status"] == "completed", json.dumps(
        completed, ensure_ascii=False, sort_keys=True
    )
    result = completed["result_content"]
    assert isinstance(result, dict)
    assert str(result.get("answer") or "").strip()
    assert isinstance(result.get("structured_result"), dict)
    assert "```json" not in str(result.get("answer") or "")


def test_team_feedback_image_cases_pass_input_capability_preflight() -> None:
    image_cases = [case for case in _cases() if case["attachments"]]

    assert len(image_cases) == 9
    for case in image_cases:
        decision = TaskRouter(AgentRegistry()).route(_request(case))
        assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
        assert decision.availability["input_mode_supported"] is True
        assert "image/png" in decision.material_extraction["attachment_types"]
        assert any(
            candidate.agent_id == "ACADEMIC_PROBLEM_SOLVER"
            and "multimodal_solver_contract" in candidate.reason_codes
            for candidate in decision.candidate_agents
        )


@pytest.mark.parametrize("case_id", ["G2-16", "G2-17"])
def test_team_feedback_circuit_diagnosis_does_not_reuse_research_context(
    case_id: str,
) -> None:
    case = next(item for item in _cases() if item["scenario_id"] == case_id)
    decision = TaskRouter(AgentRegistry()).route(_request(case))

    assert decision.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert decision.intent == "solve_problem"
    assert "domain_contract:circuit_diagnosis" in decision.reason_codes
    assert "context_boundary:research_not_reused" in decision.reason_codes
