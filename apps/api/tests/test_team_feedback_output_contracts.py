from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from app.contracts import AgentRequest, AgentResult
from app.services.scenario_output_contract import ScenarioOutputContractService

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "team_feedback_31_scenarios.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TEAM_MEMBER_TWO_HTML = REPOSITORY_ROOT / "组员反馈" / "组员二反馈.html"

_CONTRACT_CASES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "G1-Q10": (
        "faculty_course_copilot_v1",
        "TEACH_01_LESSON_PREP_V1",
        (
            "learning_objectives",
            "lesson_flow",
            "common_misconceptions",
            "differentiated_practice",
            "evidence",
            "review_boundary",
        ),
    ),
    "G1-Q11": (
        "assessment_diagnosis_v1",
        "TEACH_02_ASSIGNMENT_REVIEW_V1",
        (
            "first_error",
            "error_cause",
            "preserved_correct_steps",
            "tiered_hints",
            "verification_problem",
            "evidence",
            "review_boundary",
        ),
    ),
    "G1-Q12": (
        "student_learning_path_v1",
        "LEARN_01_LOCAL_RETRIEVAL_V1",
        (
            "evidence_summary",
            "weak_knowledge_points",
            "prerequisite_path",
            "staged_plan",
            "verification_tasks",
            "evidence",
            "review_boundary",
        ),
    ),
    "G1-Q13": (
        "research_frontier_radar_v1",
        "RESEARCH_01_ACADEMIC_SEARCH_V1",
        (
            "research_scope",
            "evidence_table",
            "doi_or_arxiv",
            "evidence_summary",
            "open_questions",
            "limitations",
            "review_boundary",
        ),
    ),
    "G1-Q14": (
        "department_knowledge_governance_v1",
        "LEARN_01_LOCAL_RETRIEVAL_V1",
        (
            "asset_inventory",
            "version_conflicts",
            "source_audit",
            "approval_status",
            "publication_blockers",
            "traceability_links",
            "review_boundary",
        ),
    ),
}

_CONTRACT_CASES.update(
    {
        "G2-01": _CONTRACT_CASES["G1-Q13"],
        "G2-02": _CONTRACT_CASES["G1-Q10"],
        "G2-03": _CONTRACT_CASES["G1-Q10"],
        "G2-05": _CONTRACT_CASES["G1-Q12"],
        "G2-06": _CONTRACT_CASES["G1-Q13"],
        "G2-08": _CONTRACT_CASES["G1-Q10"],
        "G2-10": _CONTRACT_CASES["G1-Q11"],
        "G2-11": _CONTRACT_CASES["G1-Q11"],
        "G2-12": _CONTRACT_CASES["G1-Q12"],
        "G2-13": _CONTRACT_CASES["G1-Q12"],
        "G2-14": _CONTRACT_CASES["G1-Q13"],
        "G2-15": _CONTRACT_CASES["G1-Q13"],
    }
)


class _TeamMemberTwoPromptParser(HTMLParser):
    """Extract the first italicized prompt under each numbered heading."""

    def __init__(self) -> None:
        super().__init__()
        self._heading_number = ""
        self._heading_parts: list[str] = []
        self._in_heading = False
        self._in_prompt = False
        self._prompt_parts: list[str] = []
        self.prompts: dict[str, str] = {}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
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


def _cases_by_id() -> dict[str, dict[str, Any]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    return {str(case["scenario_id"]): case for case in payload}


def _request(
    case: dict[str, Any],
    scenario_id: str,
    expected_agent: str,
    expected_output: tuple[str, ...],
) -> AgentRequest:
    return AgentRequest(
        session_id="team-feedback-contracts",
        user_id="team-feedback-contracts-user",
        scenario_id=scenario_id,
        course_id=str(case["course_id"]),
        canonical_input={"text": str(case["prompt"])},
        options={
            "scenario_id": scenario_id,
            "scenario_contract": {
                "demo_case_id": str(case["scenario_id"]),
                "expected_agent": expected_agent,
                "expected_output": list(expected_output),
                "review_boundary": "教师/研究人员必须复核，系统不得自动发布。",
            },
            **(
                {"formula_output_contract": case["formula_output_contract"]}
                if case.get("formula_output_contract")
                else {}
            ),
        },
    )


def _result(agent_id: str) -> AgentResult:
    return AgentResult(
        agent_id=agent_id,
        provider="local",
        answer="基于当前输入和可用证据生成的暂定结果。",
        evidence_status="partial",
        citations=["course://feedback/fixture"],
        structured_result={
            "evidence_packet": {
                "sources": [
                    {
                        "title": "反馈场景脱敏证据",
                        "source_ref": "course://feedback/fixture",
                        "content_type": "fixture",
                        "content_excerpt": "仅用于契约回归的脱敏摘要。",
                    }
                ]
            }
        },
    )


@pytest.mark.parametrize(
    "scenario_id",
    sorted(_CONTRACT_CASES),
)
def test_feedback_scenario_uses_existing_structured_output_contract(
    scenario_id: str,
) -> None:
    case = _cases_by_id()[scenario_id]
    contract_id, agent_id, expected_output = _CONTRACT_CASES[scenario_id]

    result = ScenarioOutputContractService().enrich(
        _result(agent_id),
        _request(case, contract_id, agent_id, expected_output),
    )

    contract = result.structured_result["scenario_contract"]
    assert contract["status"] != "not_applied"
    assert set(contract["present_fields"]) | set(contract["missing_fields"]) == set(
        expected_output
    )
    assert set(expected_output) <= set(result.business_data)
    assert "```json" not in result.answer
    assert "详细字段已同步到结构化结果和结果面板" in result.answer


def test_feedback_contract_binding_covers_all_non_solver_business_workflows() -> None:
    cases = _cases_by_id()

    assert set(_CONTRACT_CASES) <= set(cases)
    assert len(_CONTRACT_CASES) == 17
    assert all(
        cases[scenario_id]["expected_agent_id"] == expected_agent
        for scenario_id, (_, expected_agent, _) in _CONTRACT_CASES.items()
    )


@pytest.mark.parametrize(
    "scenario_id",
    sorted(
        scenario_id
        for scenario_id in _CONTRACT_CASES
        if scenario_id.startswith("G2-")
    ),
)
def test_raw_team_member_two_prompt_preserves_output_contract_binding(
    scenario_id: str,
) -> None:
    cases = _cases_by_id()
    raw_prompts = _team_member_two_raw_prompts()
    case = cases[scenario_id]
    match = re.search(r"html#(?P<number>\d+)", str(case["source_ref"]))
    assert match is not None
    raw_prompt = raw_prompts[match.group("number")]

    contract_id, agent_id, expected_output = _CONTRACT_CASES[scenario_id]
    request = _request(case, contract_id, agent_id, expected_output).model_copy(
        update={"canonical_input": {"text": raw_prompt}}
    )
    result = ScenarioOutputContractService().enrich(
        _result(agent_id),
        request,
    )

    contract = result.structured_result["scenario_contract"]
    assert contract["status"] != "not_applied"
    assert set(contract["present_fields"]) | set(contract["missing_fields"]) == set(
        expected_output
    )
    assert set(expected_output) <= set(result.business_data)


def test_research_contract_blocks_incomplete_paper_provenance() -> None:
    case = _cases_by_id()["G2-14"]
    contract_id, agent_id, expected_output = _CONTRACT_CASES["G2-14"]
    request = _request(case, contract_id, agent_id, expected_output)
    result = _result(agent_id).model_copy(
        update={
            "evidence_status": "sufficient",
            "structured_result": {
                "external_retrieval": {
                    "review_status": "approved",
                    "items": [
                        {
                            "evidence_id": "paper-1",
                            "title": "Edge YOLO pruning and quantization",
                            "published_at": "2026-01-01T00:00:00Z",
                            "canonical_url": "https://doi.org/10.1234/example",
                            "source_ref": "doi:10.1234/example",
                            "doi": "",
                        }
                    ],
                }
            },
        }
    )

    enriched = ScenarioOutputContractService().enrich(result, request)

    contract = enriched.structured_result["scenario_contract"]
    quality = enriched.business_data["research_evidence_quality"]
    assert contract["status"] == "completed_with_gaps"
    assert "research_evidence_quality" in contract["quality_gaps"]
    assert quality["status"] == "partial"
    assert "每条论文证据的 DOI 或 arXiv 标识" in quality["missing"]


def test_research_contract_accepts_complete_paper_provenance() -> None:
    case = _cases_by_id()["G2-14"]
    contract_id, agent_id, expected_output = _CONTRACT_CASES["G2-14"]
    request = _request(case, contract_id, agent_id, expected_output)
    result = _result(agent_id).model_copy(
        update={
            "evidence_status": "sufficient",
            "structured_result": {
                "external_retrieval": {
                    "review_status": "approved",
                    "items": [
                        {
                            "evidence_id": "paper-1",
                            "title": "Edge YOLO pruning and quantization",
                            "published_at": "2026-01-01T00:00:00Z",
                            "canonical_url": "https://doi.org/10.1234/example",
                            "source_ref": "doi:10.1234/example",
                            "doi": "10.1234/example",
                        }
                    ],
                    "approved_count": 1,
                }
            },
        }
    )

    enriched = ScenarioOutputContractService().enrich(result, request)

    contract = enriched.structured_result["scenario_contract"]
    quality = enriched.business_data["research_evidence_quality"]
    assert contract["status"] == "completed"
    assert quality["status"] == "sufficient"
    assert quality["missing"] == []


@pytest.mark.parametrize("scenario_id", ["G2-01", "G2-06", "G2-15"])
def test_research_feedback_cases_block_inconsistent_review_accounting(
    scenario_id: str,
) -> None:
    case = _cases_by_id()[scenario_id]
    contract_id, agent_id, expected_output = _CONTRACT_CASES[scenario_id]
    request = _request(case, contract_id, agent_id, expected_output)
    result = _result(agent_id).model_copy(
        update={
            "evidence_status": "sufficient",
            "structured_result": {
                "external_retrieval": {
                    "review_status": "approved",
                    "approved_count": 0,
                    "items": [
                        {
                            "evidence_id": "paper-1",
                            "title": "A candidate paper",
                            "published_at": "2026-01-01T00:00:00Z",
                            "canonical_url": "https://doi.org/10.1234/example",
                            "source_ref": "doi:10.1234/example",
                            "doi": "10.1234/example",
                        }
                    ],
                }
            },
        }
    )

    enriched = ScenarioOutputContractService().enrich(result, request)

    contract = enriched.structured_result["scenario_contract"]
    assert contract["status"] == "completed_with_gaps"
    assert contract["evidence_review_status"] == "incomplete"
    assert contract["model_synthesis"]["publishable"] is False
    assert "evidence_review" in contract["quality_gaps"]
