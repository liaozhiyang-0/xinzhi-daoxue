from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.config import Settings  # noqa: E402
from app.services.knowledge_base import KnowledgeBaseService  # noqa: E402

EVAL_ROOT = Path(__file__).resolve().parents[1]
COURSE_DIRS = {
    "CT": "电路理论",
    "AE": "模电",
    "DE": "数电",
    "SS": "信号与系统版本一",
    "DSP": "数字信号处理",
    "COMM": "通信原理",
}


def discover_path(course_id: str, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    name = COURSE_DIRS[course_id]
    candidates = [REPO_ROOT / name, REPO_ROOT.parent / "xinzhi-daoxue" / name]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    raise FileNotFoundError(
        f"未找到 {course_id} 教材目录；请使用 --{course_id.lower()}-path"
    )


def load_cases() -> list[dict[str, Any]]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((EVAL_ROOT / "cases").glob("*/*.json"))
    ]


def portable_corpus_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        pass
    try:
        relative = path.relative_to(REPO_ROOT.parent).as_posix()
        return f"../{relative}"
    except ValueError:
        return f"external/{path.name}"


def percentile_95(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(0.95 * len(ordered)) - 1)
    return float(ordered[index])


def percentile_50(values: list[int]) -> float:
    if not values:
        return 0.0
    return float(sorted(values)[len(values) // 2])


def source_rank(case: dict[str, Any], hits: list[Any]) -> int | None:
    expected = {
        source["document_path"]
        for source in case["expected_sources"]
        if source["required"]
    }
    for index, hit in enumerate(hits, start=1):
        if hit.document_path in expected:
            return index
    return None


def run(args: argparse.Namespace) -> dict[str, Any]:
    paths = {
        course: discover_path(course, getattr(args, f"{course.lower()}_path"))
        for course in COURSE_DIRS
    }
    settings = Settings(
        knowledge_ct_path=paths["CT"],
        knowledge_ae_path=paths["AE"],
        knowledge_de_path=paths["DE"],
        knowledge_ss_path=paths["SS"],
        knowledge_dsp_path=paths["DSP"],
        knowledge_comm_path=paths["COMM"],
        _env_file=None,
    )
    service = KnowledgeBaseService(settings)
    refresh_started = perf_counter()
    statuses = service.refresh()
    refresh_latency_ms = max(0, round((perf_counter() - refresh_started) * 1000))
    cases = load_cases()
    rows: list[dict[str, Any]] = []
    latencies: list[int] = []
    for case in cases:
        started = perf_counter()
        if args.mode == "baseline_lexical_v1":
            hits = service.search_baseline(case["query"], [case["course_id"]], 5)
        else:
            result = service.search_result(case["query"], [case["course_id"]], 5)
            hits = result.hits
        latency_ms = max(0, round((perf_counter() - started) * 1000))
        latencies.append(latency_ms)
        rank = source_rank(case, hits)
        forbidden = set(case["forbidden_courses"])
        rows.append(
            {
                "case_id": case["case_id"],
                "course_id": case["course_id"],
                "query": case["query"],
                "review_status": case["review_status"],
                "relevant_rank": rank,
                "latency_ms": latency_ms,
                "wrong_course": bool(hits and str(hits[0].course_id) in forbidden),
                "hits": [
                    {
                        "rank": index,
                        "course_id": str(hit.course_id),
                        "document_path": hit.document_path,
                        "chapter": getattr(hit, "chapter", hit.title),
                        "title": hit.title,
                        "score": hit.score,
                        "source_ref": hit.source_ref,
                    }
                    for index, hit in enumerate(hits, start=1)
                ],
            }
        )
    count = len(rows) or 1
    metrics = {
        f"Recall@{k}": sum(
            row["relevant_rank"] is not None and row["relevant_rank"] <= k
            for row in rows
        )
        / count
        for k in (1, 3, 5)
    }
    metrics.update(
        {
            "MRR": sum(
                1 / row["relevant_rank"] if row["relevant_rank"] else 0 for row in rows
            )
            / count,
            "nDCG@5": sum(
                1 / math.log2(row["relevant_rank"] + 1) if row["relevant_rank"] else 0
                for row in rows
            )
            / count,
            "zero_hit_rate": sum(not row["hits"] for row in rows) / count,
            "wrong_course_rate": sum(row["wrong_course"] for row in rows) / count,
            "mean_latency_ms": statistics.fmean(latencies) if latencies else 0.0,
            "p50_latency_ms": percentile_50(latencies),
            "p95_latency_ms": percentile_95(latencies),
            "index_refresh_latency_ms": refresh_latency_ms,
        }
    )
    return {
        "run_id": args.mode,
        "retrieval_mode": args.mode,
        "generated_at": datetime.now(UTC).isoformat(),
        "case_status": "draft",
        "case_count": len(rows),
        "corpus": {
            status.course_id.value: {
                "path": portable_corpus_path(paths[status.course_id.value]),
                "document_count": status.document_count,
                "chunk_count": status.chunk_count,
            }
            for status in statuses
        },
        "metrics": {key: round(value, 6) for key, value in metrics.items()},
        "cases": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the local lexical retrieval draft benchmark"
    )
    parser.add_argument(
        "--mode",
        choices=["baseline_lexical_v1", "local_lexical_v2"],
        default="local_lexical_v2",
    )
    parser.add_argument("--ct-path")
    parser.add_argument("--ae-path")
    parser.add_argument("--de-path")
    parser.add_argument("--ss-path")
    parser.add_argument("--dsp-path")
    parser.add_argument("--comm-path")
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run(args)
    output = (
        Path(args.output)
        if args.output
        else EVAL_ROOT / "results" / f"{args.mode}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload["metrics"], ensure_ascii=False, indent=2))
    print(f"saved {payload['case_count']} draft cases to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
