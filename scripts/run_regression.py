from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.agents import AgentRegistry, TaskRouter  # noqa: E402
from app.contracts import AgentRequestV2  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.observability import TraceStore  # noqa: E402
from app.orchestrator import XZDSupervisor  # noqa: E402


def main() -> int:
    case_root = ROOT / "tests" / "regression" / "cases"
    registry = AgentRegistry()
    settings = Settings(app_env="test", rag_enabled=False, _env_file=None)
    supervisor = XZDSupervisor(
        registry,
        TaskRouter(registry, settings),
        TraceStore(),
    )
    failures: list[dict[str, str]] = []
    count = 0
    for path in sorted(case_root.glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        count += 1
        prepared = supervisor.prepare(
            AgentRequestV2.model_validate(case["input"]),
            session_id="session-regression",
            user_id="user-regression",
            session_context=case.get("session_context", {}),
        )
        actual = {
            "course": str(prepared.state["course"]),
            "intent": str(prepared.state["intent"]),
            "agent": prepared.route.agent_id,
        }
        for key, expected_key in (
            ("course", "expected_course"),
            ("intent", "expected_intent"),
            ("agent", "expected_agent"),
        ):
            expected = case.get(expected_key)
            if expected and actual[key] != expected:
                failures.append(
                    {
                        "case_id": case["case_id"],
                        "field": key,
                        "expected": expected,
                        "actual": actual[key],
                    }
                )
    print(
        json.dumps(
            {"cases": count, "failures": failures},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
