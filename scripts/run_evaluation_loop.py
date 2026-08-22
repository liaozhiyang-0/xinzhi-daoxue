from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.evaluation.contracts import SuiteReport  # noqa: E402
from app.evaluation.loader import EvaluationCaseLoader  # noqa: E402
from app.evaluation.loop import EvaluationLoop, EvaluationRecord  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="分析现有 Evaluation SuiteReport，生成 Phase F evidence loop 摘要"
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "evaluation" / "reports" / "latest.json",
    )
    parser.add_argument("--case-root", type=Path, default=ROOT / "evaluation" / "cases")
    parser.add_argument("--suite-id", default="")
    parser.add_argument("--expected-case-count", type=int, default=336)
    parser.add_argument("--historical-records", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def _load_cases(root: Path) -> list[Any]:
    if not root.is_dir():
        return []
    return EvaluationCaseLoader(root).load_all()


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    if not args.report.is_file():
        raise ValueError(f"evaluation report not found: {args.report}")
    report = SuiteReport.model_validate_json(args.report.read_text(encoding="utf-8"))
    cases = _load_cases(args.case_root)
    records, failures, patterns, summary = EvaluationLoop().analyze(
        report,
        cases,
        suite_id=args.suite_id,
        expected_case_count=args.expected_case_count,
    )
    if args.historical_records:
        historical = json.loads(args.historical_records.read_text(encoding="utf-8"))
        if not isinstance(historical, list):
            raise ValueError("historical records must be a JSON list")
        extra = [EvaluationRecord.model_validate(item) for item in historical]
        records, failures, patterns, summary = EvaluationLoop().analyze_records(
            [*records, *extra], expected_case_count=args.expected_case_count
        )
    return {
        "report_path": str(args.report),
        "case_root": str(args.case_root),
        "records": [item.model_dump(mode="json") for item in records],
        "failures": [item.model_dump(mode="json") for item in failures],
        "patterns": [item.model_dump(mode="json") for item in patterns],
        "summary": summary.model_dump(mode="json"),
        "improvement_proposals": [],
        "promotion_decisions": [],
        "governance_boundary": [
            "no_automatic_code_mutation",
            "no_automatic_prompt_mutation",
            "no_automatic_production_promotion",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = analyze(args)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"evaluation_loop_report={args.output}")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
