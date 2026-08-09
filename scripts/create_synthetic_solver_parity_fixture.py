"""Create a provider-free Solver parity suite for CI smoke gating."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.runtime import (  # type: ignore[import-untyped]  # noqa: E402
    AgentRun,
    AgentRunPlan,
    RuntimeNode,
    RuntimeNodeState,
    RuntimeNodeStatus,
    RuntimeRunStatus,
    SolverParityPair,
    SolverParitySuite,
    SolverParityThresholds,
)


def _checkpoints(case_id: str) -> list[dict[str, object]]:
    run = AgentRun(
        run_id=f"run-{case_id}",
        task_id=f"task-{case_id}",
        goal="synthetic solver parity case",
        plan=AgentRunPlan(
            plan_id=f"plan-{case_id}",
            goal="synthetic solver parity case",
            nodes=[
                RuntimeNode(
                    node_id="solver.observe",
                    node_type="verification",
                    handler_id="academic.solver.observe",
                ),
                RuntimeNode(
                    node_id="solver.execute",
                    node_type="provider",
                    handler_id="academic.solver.execute",
                    depends_on=["solver.observe"],
                ),
                RuntimeNode(
                    node_id="solver.verify",
                    node_type="verification",
                    handler_id="academic.solver.verify",
                    depends_on=["solver.execute"],
                ),
            ],
        ),
    )
    initial = run.model_dump(mode="json")
    run.nodes = {
        node_id: RuntimeNodeState(
            node_id=node_id,
            status=RuntimeNodeStatus.SUCCEEDED,
        )
        for node_id in run.nodes
    }
    run.status = RuntimeRunStatus.COMPLETED
    run.state_version = 2
    completed = run.model_dump(mode="json")
    return [
        {"sequence": 1, "state_version": 1, "state_data": initial},
        {"sequence": 2, "state_version": 2, "state_data": completed},
    ]


def _payload() -> dict[str, object]:
    return {
        "status": "completed",
        "provider": "local_graph",
        "result_content": {
            "answer": "synthetic answer; semantic quality not evaluated",
            "metrics": {"latency_ms": 100, "model_calls": 2},
        },
    }


def build_fixture() -> SolverParitySuite:
    required = {
        "academic.solver.observe",
        "academic.solver.execute",
        "academic.solver.verify",
    }
    return SolverParitySuite(
        suite_id="academic_solver_parity_ci_synthetic",
        thresholds=SolverParityThresholds(min_pairs=2),
        pairs=[
            SolverParityPair(
                case_id=case_id,
                legacy_payload=_payload(),
                runtime_payload=_payload(),
                runtime_checkpoints=_checkpoints(case_id),
                required_handler_ids=required,
            )
            for case_id in ("synthetic-text", "synthetic-retrieval")
        ],
    )


def main(output_path: str) -> int:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            build_fixture().model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: python scripts/create_synthetic_solver_parity_fixture.py "
            "OUTPUT.json"
        )
    raise SystemExit(main(sys.argv[1]))
