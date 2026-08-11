from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "scripts" / "run_runtime_authorized_dev_e2e.py"
SPEC = importlib.util.spec_from_file_location("runtime_authorized_dev_e2e", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class _ProposalResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self.payload


class _ProposalClient:
    def get(self, _url: str) -> _ProposalResponse:
        return _ProposalResponse(
            [
                {
                    "proposal_id": "old",
                    "run_id": "run-1",
                    "status": "pending",
                    "state_version": 4,
                },
                {
                    "proposal_id": "new",
                    "run_id": "run-1",
                    "status": "pending",
                    "state_version": 7,
                },
                {
                    "proposal_id": "other-run",
                    "run_id": "run-2",
                    "status": "pending",
                    "state_version": 99,
                },
            ]
        )


class _TaskResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return {"id": "task-1"}


class _TaskClient:
    def __init__(self) -> None:
        self.payload: dict[str, object] | None = None

    def post(self, _url: str, *, json: dict[str, object]) -> _TaskResponse:
        self.payload = json
        return _TaskResponse()


def test_e2e_runner_selects_pending_plan_proposal_before_side_effect_approval() -> None:
    proposal = MODULE.pending_plan_proposal(
        _ProposalClient(),
        "http://test/api/v1",
        "task-1",
        "run-1",
    )

    assert proposal is not None
    assert proposal["proposal_id"] == "new"
    assert proposal["state_version"] == 7


def test_result_summary_projects_runtime_control_plane_timing() -> None:
    summary = MODULE.result_summary(
        {
            "status": "completed",
            "agent_id": "ACADEMIC_PROBLEM_SOLVER",
            "result_content": {"metrics": {"latency_ms": 400}},
        },
        {
            "runtime": {
                "status": "completed",
                "observability": {
                    "timing": {
                        "run_elapsed_ms": 350,
                        "completed_node_elapsed_ms": 250,
                        "active_node_wall_ms": 220,
                        "runtime_control_overhead_ms": 130,
                    }
                },
            }
        },
        observed_wait_ms=410,
    )

    assert summary["runtime_timing"] == {
        "run_elapsed_ms": 350,
        "completed_node_elapsed_ms": 250,
        "active_node_wall_ms": 220,
        "runtime_control_overhead_ms": 130,
    }


def test_pair_modes_rotates_pair_order_without_changing_single_mode_runs() -> None:
    assert MODULE.pair_modes("both", "alternate", 0) == ("legacy", "runtime")
    assert MODULE.pair_modes("both", "alternate", 1) == ("runtime", "legacy")
    assert MODULE.pair_modes("both", "runtime-first", 0) == ("runtime", "legacy")
    assert MODULE.pair_modes("legacy", "alternate", 5) == ("legacy",)
    assert MODULE.pair_modes("runtime", "alternate", 5) == ("runtime",)


def test_research03_pair_case_omits_business_candidate_from_legacy_request() -> None:
    case = next(
        item
        for item in MODULE.CASES
        if item.case_id == "research_data_analysis_runtime_handoff"
    )

    legacy_client = _TaskClient()
    MODULE.create_task(
        legacy_client,
        "http://test/api/v1",
        "user-1",
        "session-1",
        case,
        "legacy",
    )
    assert legacy_client.payload is not None
    legacy_options = legacy_client.payload["options"]
    assert isinstance(legacy_options, dict)
    assert "research_analysis_v2" not in legacy_options

    runtime_client = _TaskClient()
    MODULE.create_task(
        runtime_client,
        "http://test/api/v1",
        "user-1",
        "session-1",
        case,
        "runtime",
    )
    assert runtime_client.payload is not None
    runtime_options = runtime_client.payload["options"]
    assert isinstance(runtime_options, dict)
    runtime_request = runtime_options["research_analysis_v2"]
    assert isinstance(runtime_request, dict)
    assert runtime_request["execute"] is True
    assert runtime_request["request"] == case.runtime_request


def test_runtime_failure_diagnostics_distinguish_child_failure_from_proposals() -> None:
    diagnostics = MODULE.runtime_failure_diagnostics(
        {
            "runtime": {
                "nodes": [
                    {
                        "node_id": "lesson.execute",
                        "status": "failed",
                        "error_code": "subagent_child_result_missing",
                    },
                    {
                        "node_id": "lesson.verify",
                        "status": "blocked",
                        "error_code": "dependency_failed",
                    },
                ],
                "events": [],
            },
            "events": [
                {
                    "data": {
                        "data": {
                            "status": "failed",
                            "error_code": "StructuredOutputError",
                        }
                    }
                },
                {
                    "data": {
                        "data": {
                            "stage_id": "runtime_plan_proposal",
                            "reason_codes": ["lesson_prep_execution_failed"],
                        }
                    }
                },
            ],
        }
    )

    assert diagnostics == {
        "failure_codes": [
            "StructuredOutputError",
            "dependency_failed",
            "subagent_child_result_missing",
        ],
        "unresolved_failure_codes": [
            "StructuredOutputError",
            "dependency_failed",
            "subagent_child_result_missing",
        ],
        "recovered_failure_codes": [],
        "failed_node_ids": ["lesson.execute", "lesson.verify"],
        "plan_proposal_count": 1,
        "plan_proposal_reason_codes": ["lesson_prep_execution_failed"],
    }


def test_runtime_failure_diagnostics_redacts_unstable_identifiers() -> None:
    diagnostics = MODULE.runtime_failure_diagnostics(
        {
            "runtime": {
                "nodes": [
                    {
                        "node_id": "node/with-sensitive text",
                        "status": "failed",
                        "error_code": "provider error: raw details",
                    }
                ]
            }
        }
    )

    assert diagnostics == {
        "failure_codes": [],
        "unresolved_failure_codes": [],
        "recovered_failure_codes": [],
        "failed_node_ids": [],
        "plan_proposal_count": 0,
        "plan_proposal_reason_codes": [],
    }


def test_runtime_failure_diagnostics_marks_recovered_child_errors() -> None:
    diagnostics = MODULE.runtime_failure_diagnostics(
        {
            "runtime": {
                "status": "completed",
                "nodes": [
                    {
                        "node_id": "lesson.execute",
                        "status": "succeeded",
                        "error_code": "",
                    }
                ],
            },
            "events": [
                {
                    "data": {
                        "data": {
                            "status": "failed",
                            "error_code": "StructuredOutputError",
                        }
                    }
                }
            ],
        }
    )

    assert diagnostics["failure_codes"] == ["StructuredOutputError"]
    assert diagnostics["unresolved_failure_codes"] == []
    assert diagnostics["recovered_failure_codes"] == ["StructuredOutputError"]
