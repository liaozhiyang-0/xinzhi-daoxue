from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

_MINIMAL_JPEG = (
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////"
    "////////////////////////////////////////2wBDAf////////////////////"
    "//////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB"
    "/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQ"
    "AxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAA"
    "AAAAAAAA/9oACAEDAQE/AN//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/AN//xAAU"
    "EAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAY/Aqf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oA"
    "CAEBAAE/IV//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8Q"
    "H//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAA"
    "ABD/2gAIAQEAAT8QH//Z"
)


def _ci_jpeg_bytes() -> bytes:
    image = bytearray(base64.b64decode(_MINIMAL_JPEG))
    comment = b"phase-ci-fixture" + b"\x00" * 2040
    marker = b"\xff\xfe" + (len(comment) + 2).to_bytes(2, "big") + comment
    image[-2:] = marker + image[-2:]
    return bytes(image)


def _ensure_file(path: Path, content: bytes | str, created: list[Path]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8", newline="\n")
    created.append(path)


@pytest.fixture(scope="session", autouse=True)
def clean_checkout_fixtures() -> None:
    """Make ignored, local-only evidence inputs deterministic for tests.

    These are test fixtures, never runtime knowledge or evaluation evidence.
    Existing developer-owned files are left untouched and newly created files
    are removed when the test session ends.
    """

    root = Path(__file__).resolve().parent
    created: list[Path] = []
    manifest_rows = "\n".join(
        json.dumps(row, ensure_ascii=False)
        for row in (
            {
                "course_id": "CT",
                "relative_path": "fixtures/ct.md",
                "source_relative_path": "fixtures/ct.md",
                "source_path": "CT/fixtures/ct.md",
                "parse_status": "parsed",
                "quality_status": "review",
            },
            {
                "course_id": "AE",
                "relative_path": "fixtures/ae.md",
                "source_relative_path": "fixtures/ae.md",
                "source_path": "AE/fixtures/ae.md",
                "parse_status": "parsed",
                "quality_status": "review",
            },
        )
    ) + "\n"
    quality_issues = json.dumps(
        {
            "schema_version": "knowledge_base_quality_issues.v1",
            "issues": [
                {
                    "course_id": "CT",
                    "issue_type": "ocr_low_confidence",
                    "relative_path": "fixtures/ct.md",
                },
                {
                    "course_id": "AE",
                    "issue_type": "ocr_low_confidence",
                    "relative_path": "fixtures/ae.md",
                },
            ],
        },
        ensure_ascii=False,
    )
    empty_report = json.dumps(
        {
            "schema_version": "1.0",
            "mode": "offline",
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:00:00+00:00",
            "filters": {},
            "summary": {},
            "statistics": {},
            "results": [],
            "run_metadata": {
                "version": "v1",
                "run_id": "clean-checkout-fixture",
                "case_count": 0,
                "raw_prompts_stored": False,
            },
        }
    )
    _ensure_file(
        root / "knowledge_indexes" / "knowledge_base_manifest.jsonl",
        manifest_rows,
        created,
    )
    _ensure_file(
        root / "knowledge_indexes" / "knowledge_base_quality_issues.json",
        quality_issues,
        created,
    )
    _ensure_file(
        root / "evaluation" / "reports" / "latest.json",
        empty_report,
        created,
    )
    _ensure_file(
        root
        / "evaluation"
        / "cache"
        / "storage"
        / "ci-fixtures"
        / "模电测试集_图2.1.1_运算放大器电路.jpg",
        _ci_jpeg_bytes(),
        created,
    )
    try:
        yield
    finally:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        parents = {path.parent for path in created}
        for parent in sorted(parents, key=lambda item: len(item.parts), reverse=True):
            try:
                parent.rmdir()
            except OSError:
                pass
