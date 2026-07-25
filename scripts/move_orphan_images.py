from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ISSUES_PATH = PROJECT_ROOT / "knowledge_indexes" / "knowledge_base_quality_issues.json"
MANIFEST_PATH = PROJECT_ROOT / "knowledge_indexes" / "knowledge_base_manifest.jsonl"
DESTINATION = PROJECT_ROOT / "知识库" / "待复核_孤立图片"
COURSE_ROOTS = {
    "CT": PROJECT_ROOT / "电路理论",
    "AE": PROJECT_ROOT / "模电",
    "DE": PROJECT_ROOT / "数电",
    "SS": PROJECT_ROOT / "信号与系统版本一",
    "DSP": PROJECT_ROOT / "数字信号处理",
    "COMM": PROJECT_ROOT / "通信原理",
}


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def collect_moves() -> list[dict[str, Any]]:
    payload = json.loads(ISSUES_PATH.read_text(encoding="utf-8"))
    manifest = {
        (str(item["course_id"]), str(item["relative_path"])): item
        for item in _load_jsonl(MANIFEST_PATH)
    }
    moves: list[dict[str, Any]] = []
    for issue in payload.get("issues", []):
        if issue.get("issue_type") != "orphan_image":
            continue
        course_id = str(issue["course_id"])
        relative = PurePosixPath(str(issue["file_path"]))
        source_root = COURSE_ROOTS[course_id].resolve()
        source = (source_root / relative).resolve()
        target = (DESTINATION / course_id / relative).resolve()
        if not _is_within(source, source_root):
            raise RuntimeError(f"不安全的源路径: {course_id}/{relative}")
        if not _is_within(target, DESTINATION):
            raise RuntimeError(f"不安全的目标路径: {course_id}/{relative}")
        if not source.is_file():
            raise FileNotFoundError(source)
        if target.exists():
            raise FileExistsError(target)
        metadata = manifest.get((course_id, relative.as_posix()), {})
        moves.append(
            {
                "course_id": course_id,
                "image_id": metadata.get("document_id", ""),
                "checksum": metadata.get("checksum", ""),
                "file_size": source.stat().st_size,
                "original_path": f"{course_id}/{relative.as_posix()}",
                "new_path": (
                    f"知识库/待复核_孤立图片/{course_id}/{relative.as_posix()}"
                ),
                "source": source,
                "target": target,
            }
        )
    if len(moves) != len({str(item["source"]) for item in moves}):
        raise RuntimeError("孤立图片清单包含重复源路径")
    return moves


def execute(moves: list[dict[str, Any]]) -> Path:
    completed: list[dict[str, Any]] = []
    try:
        for item in moves:
            target = item["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item["source"]), str(target))
            completed.append(item)
    except Exception:
        for item in reversed(completed):
            source = item["source"]
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(item["target"]), str(source))
        raise

    output = DESTINATION / "orphan_image_move_manifest.json"
    serializable = [
        {key: value for key, value in item.items() if key not in {"source", "target"}}
        for item in moves
    ]
    output.write_text(
        json.dumps(
            {
                "moved_at": datetime.now(UTC).isoformat(),
                "count": len(serializable),
                "entries": serializable,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="安全迁移审计确认的孤立图片")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="执行迁移；省略时仅验证并输出计划",
    )
    args = parser.parse_args()
    moves = collect_moves()
    summary = {
        "count": len(moves),
        "bytes": sum(int(item["file_size"]) for item in moves),
        "destination": "知识库/待复核_孤立图片",
        "apply": args.apply,
    }
    if args.apply:
        summary["manifest"] = execute(moves).relative_to(PROJECT_ROOT).as_posix()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
