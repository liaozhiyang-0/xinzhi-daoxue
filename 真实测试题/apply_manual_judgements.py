from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from analyze_evaluation_report import (
    DEFAULT_CASES,
    DEFAULT_CONFIG,
    build_output,
    load_cases,
    load_json,
    write_outputs,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_REPORTS = ROOT / "统一格式" / "evaluation_reports"
DEFAULT_REVIEWS = ROOT / "manual_judgements.json"


def latest_report() -> Path:
    candidates = sorted(
        DEFAULT_REPORTS.glob("*/raw/latest.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise ValueError("没有找到全量测试检查点")
    return candidates[0]


def answer_sha256(answer: str) -> str:
    return hashlib.sha256(answer.encode("utf-8")).hexdigest()


def apply_reviews(
    report: dict[str, Any], reviews: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    results = report.get("results")
    if not isinstance(results, list):
        raise ValueError("报告缺少results数组")
    result_by_id = {
        str(item.get("case_id")): item for item in results if isinstance(item, dict)
    }
    for result in result_by_id.values():
        actual = result.get("actual")
        if isinstance(actual, dict) and not str(actual.get("answer") or "").strip():
            actual.pop("answer_evaluation", None)
    applied: list[dict[str, Any]] = []
    for review in reviews:
        case_id = str(review.get("case_id"))
        matched_result = result_by_id.get(case_id)
        if matched_result is None:
            continue
        actual = matched_result.get("actual")
        if not isinstance(actual, dict):
            continue
        answer = str(actual.get("answer") or "")
        expected_hash = str(review.get("answer_sha256"))
        actual_hash = answer_sha256(answer)
        if actual_hash != expected_hash:
            raise ValueError(f"{case_id}: 答案哈希不一致，拒绝套用旧判定")
        judgement = {
            "passed": review.get("passed") is True,
            "score": float(review.get("score", 0)),
            "judge": "hybrid",
            "reference_used": True,
            "reason": str(review.get("reason") or "人工简判"),
            "verdict": str(review.get("verdict") or "unjudgeable"),
            "review_method": "hash_bound_simple_review",
            "reviewed_at": review.get("reviewed_at"),
            "cached": True,
        }
        actual["answer_evaluation"] = judgement
        applied.append(
            {
                "case_id": case_id,
                "verdict": judgement["verdict"],
                "score": judgement["score"],
                "reason": judgement["reason"],
            }
        )
    return applied


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将内容哈希绑定的简易复核应用到已有检查点，不调用模型"
    )
    parser.add_argument("--report", type=Path)
    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEWS)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = args.report.resolve() if args.report else latest_report()
    report = load_json(report_path)
    if not isinstance(report, dict):
        raise ValueError("报告顶层必须是对象")
    review_payload = load_json(args.reviews.resolve())
    reviews = (
        review_payload.get("reviews") if isinstance(review_payload, dict) else None
    )
    if not isinstance(reviews, list):
        raise ValueError("复核文件顶层必须包含reviews数组")
    applied = apply_reviews(
        report, [item for item in reviews if isinstance(item, dict)]
    )

    output_report = report_path.with_name("latest_enriched.json")
    output_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    all_cases = load_cases(args.cases.resolve())
    result_ids = {
        str(item.get("case_id")) for item in report["results"] if isinstance(item, dict)
    }
    selected_cases = [case for case in all_cases if str(case["case_id"]) in result_ids]
    config = load_json(args.config.resolve())
    summary, rows, visualization = build_output(
        selected_cases,
        report["results"],
        config,
        report,
    )
    metrics_root = report_path.parents[1] / "metrics_existing_review"
    write_outputs(metrics_root, summary, rows, visualization)
    review_summary = {
        "schema_version": "1.0",
        "source_report": str(report_path),
        "enriched_report": str(output_report),
        "applied_count": len(applied),
        "applied": applied,
        "metrics": str(metrics_root / "metrics_summary.json"),
    }
    (metrics_root / "simple_review_summary.json").write_text(
        json.dumps(review_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(review_summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
