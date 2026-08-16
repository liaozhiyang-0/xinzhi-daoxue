from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.evaluation.contracts import EvaluationCase, EvaluationResult


class EvaluationCache:
    def __init__(self, root: Path, *, fingerprint: str) -> None:
        self.root = root
        self.fingerprint = fingerprint

    def key(self, case: EvaluationCase, *, mode: str) -> str:
        payload = {
            "case": case.model_dump(mode="json"),
            "mode": mode,
            "fingerprint": self.fingerprint,
            "prompt_version": "academic_solver_eval_v1",
            "course_pack_version": "course_registry_v1",
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()

    def load(self, key: str) -> EvaluationResult | None:
        path = self.root / f"{key}.json"
        if not path.is_file():
            return None
        try:
            return EvaluationResult.model_validate_json(
                path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return None

    def save(self, key: str, result: EvaluationResult) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{key}.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def evaluation_fingerprint(project_root: Path) -> str:
    paths = (
        project_root / "config" / "model_routes.yaml",
        project_root / "agent_configs" / "registry.yaml",
        project_root / "apps" / "api" / "app" / "agents" / "router.py",
        project_root / "apps" / "api" / "app" / "contracts" / "solver.py",
        project_root / "apps" / "api" / "app" / "courses" / "registry.py",
        project_root
        / "apps"
        / "api"
        / "app"
        / "orchestrator"
        / "graphs"
        / "academic_solver_graph.py",
        project_root
        / "apps"
        / "api"
        / "app"
        / "services"
        / "academic_solver_service.py",
        project_root
        / "apps"
        / "api"
        / "app"
        / "services"
        / "academic_review.py",
        project_root
        / "apps"
        / "api"
        / "app"
        / "services"
        / "student_verification.py",
        project_root
        / "apps"
        / "api"
        / "app"
        / "services"
        / "solver_runtime_policy.py",
        project_root
        / "apps"
        / "api"
        / "app"
        / "services"
        / "rag_providers.py",
        project_root
        / "apps"
        / "api"
        / "app"
        / "services"
        / "rag_runtime.py",
        project_root
        / "apps"
        / "api"
        / "app"
        / "services"
        / "runtime_task_engine.py",
        project_root
        / "apps"
        / "api"
        / "app"
        / "services"
        / "high_risk_verification.py",
        project_root / "apps" / "api" / "app" / "evaluation" / "runner.py",
        project_root / "apps" / "api" / "app" / "evaluation" / "scorers" / "core.py",
    )
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(project_root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:24]
