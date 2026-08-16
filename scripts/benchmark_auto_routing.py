from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import median, quantiles
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = PROJECT_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.agents import AgentRegistry, TaskRouter  # noqa: E402
from app.contracts import AgentRequest  # noqa: E402
from app.core.config import Settings  # noqa: E402


def percentile_95(values: list[float]) -> float:
    return quantiles(values, n=20)[18]


def main() -> int:
    cases: list[dict[str, Any]] = json.loads(
        (PROJECT_ROOT / "evaluation" / "automatic_routing" / "cases.json").read_text(
            encoding="utf-8"
        )
    )
    settings = Settings(
        app_env="test",
        _env_file=None,
    )
    router = TaskRouter(AgentRegistry(), settings)
    route_ms: list[float] = []
    material_ms: list[float] = []
    selected = 0
    unresolved = 0
    for _ in range(20):
        for case in cases:
            request = AgentRequest(
                session_id="benchmark-session",
                user_id="benchmark-user",
                scene="dispatch",
                course_id=str(case.get("course_hint", "AUTO")),
                intent="unknown",
                canonical_input={"text": case["user_input"]},
                options=dict(case.get("session_context", {})),
            )
            started = perf_counter()
            decision = router.route(request)
            route_ms.append((perf_counter() - started) * 1000)
            material_ms.append(float(decision.material_extraction.get("latency_ms", 0)))
            if decision.route_status.value == "selected":
                selected += 1
            else:
                unresolved += 1
    print(
        json.dumps(
            {
                "runs": len(route_ms),
                "route_p50_ms": round(median(route_ms), 3),
                "route_p95_ms": round(percentile_95(route_ms), 3),
                "material_p50_ms": round(median(material_ms), 3),
                "material_p95_ms": round(percentile_95(material_ms), 3),
                "selected": selected,
                "unresolved": unresolved,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
