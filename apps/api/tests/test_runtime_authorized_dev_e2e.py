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
