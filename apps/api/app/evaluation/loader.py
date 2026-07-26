from __future__ import annotations

from pathlib import Path

import yaml

from app.evaluation.contracts import EvaluationCase


class EvaluationCaseLoader:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load_all(self) -> list[EvaluationCase]:
        paths = sorted([*self.root.rglob("*.yaml"), *self.root.rglob("*.json")])
        if not paths:
            raise ValueError(f"未找到评测案例: {self.root}")
        cases: list[EvaluationCase] = []
        seen: set[str] = set()
        for path in paths:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            values = payload.get("cases") if isinstance(payload, dict) else None
            if isinstance(payload, dict) and "case_id" in payload:
                values = [payload]
            if not isinstance(values, list):
                raise ValueError(f"{path}: 顶层必须包含cases列表")
            for raw in values:
                case = EvaluationCase.model_validate(raw)
                if self.root.name == "cases" and "not_official" in case.tags:
                    continue
                if case.case_id in seen:
                    raise ValueError(f"重复case_id: {case.case_id}")
                seen.add(case.case_id)
                cases.append(case)
        return cases

    @staticmethod
    def filter(
        cases: list[EvaluationCase],
        *,
        course: str | None = None,
        tags: set[str] | None = None,
        case_id: str | None = None,
        max_cases: int | None = None,
    ) -> list[EvaluationCase]:
        selected = cases
        if course:
            selected = [item for item in selected if item.course == course.upper()]
        if tags:
            selected = [item for item in selected if tags.intersection(item.tags)]
        if case_id:
            selected = [item for item in selected if item.case_id == case_id]
        if max_cases is not None:
            selected = selected[:max_cases]
        return selected
