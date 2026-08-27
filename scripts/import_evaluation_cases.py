from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.evaluation.contracts import EvaluationCase  # noqa: E402


def _row(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError("evaluation case must be a JSON object")
    return {str(key): item for key, item in value.items()}


def load_rows(path: Path) -> list[dict[str, object]]:
    if path.suffix.casefold() == ".jsonl":
        return [
            _row(json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    if path.suffix.casefold() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return [_row(item) for item in csv.DictReader(handle)]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("cases"), list):
        return [_row(item) for item in payload["cases"]]
    if isinstance(payload, list):
        return [_row(item) for item in payload]
    return [_row(payload)]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import authorized cases into the unified schema"
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--source-type",
        choices=("synthetic", "licensed", "private", "public"),
        required=True,
    )
    parser.add_argument("--authorization", default="")
    args = parser.parse_args()
    cases = []
    for row in load_rows(args.source):
        raw = row.copy()
        provenance = raw.get("provenance")
        if not isinstance(provenance, dict):
            provenance = {}
        raw["provenance"] = {
            **provenance,
            "source_type": args.source_type,
            "license_or_authorization": args.authorization,
            "publishable": args.source_type != "private",
        }
        cases.append(EvaluationCase.model_validate(raw).model_dump(mode="json"))
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(
        yaml.safe_dump({"cases": cases}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"imported={len(cases)} destination={args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
