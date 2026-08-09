from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from app.services.academic_solver_runtime import AcademicSolverRuntimeService

REPOSITORY_ROOT = Path(__file__).parents[3]
FROZEN_FILE_HASHES = {
    "agent_configs/workflows/solver_ct_v1.yaml": (
        "c201548bdac0f09b47aa9fd3a0b3930121bfec3056a7ce72fef7ea9a72555218"
    ),
    "agent_configs/course_packs/course_ct_v1.yaml": (
        "89f56dbd8dca395f3b8950f8fafb7f175a91ed86eaba3828328e76620ce9bf82"
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_tracked_solver_baseline_files_are_frozen() -> None:
    for relative_path, expected_hash in FROZEN_FILE_HASHES.items():
        path = REPOSITORY_ROOT / relative_path
        assert path.is_file(), f"missing frozen baseline file: {relative_path}"
        assert _sha256(path) == expected_hash, (
            f"frozen baseline changed: {relative_path}; review before migration"
        )


def test_runtime_keeps_solver_baseline_call_mapping() -> None:
    registry_path = REPOSITORY_ROOT / "agent_configs" / "registry.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    solver = registry["agents"]["SOLVER_CT_V1"]

    assert solver["provider"] == {
        "type": "xingchen",
        "flow_env_key": "XINGCHEN_SOLVER_CT_FLOW_ID",
        "timeout_seconds": 300,
        "max_retries": 0,
        "parser_type": "json",
        "output_schema": "solver_ct_v1",
    }
    assert solver["local_handler"] == (
        "app.agents.solver_ct.local_graph.LocalCircuitSolverGraph"
    )
    assert solver["graph_name"] == "academic_problem_solver"
    assert solver["execution_mode"] == "hybrid"

    assert AcademicSolverRuntimeService.agent_id == "ACADEMIC_PROBLEM_SOLVER"
    assert AcademicSolverRuntimeService.execute_handler_id == "academic.solver.execute"
    assert AcademicSolverRuntimeService.verify_handler_id == "academic.solver.verify"
    assert AcademicSolverRuntimeService.use_typed_subagent is False
