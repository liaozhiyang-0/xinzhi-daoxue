from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402
from app.knowledge_catalog import KNOWLEDGE_COURSE_IDS  # noqa: E402
from app.services.knowledge_index import KnowledgeIndexBuilder  # noqa: E402
from app.services.knowledge_ocr_review import (  # noqa: E402
    build_ocr_decision_template,
    build_ocr_review_queue,
)


def _builder(settings: Settings) -> KnowledgeIndexBuilder:
    return KnowledgeIndexBuilder(
        roots=settings.knowledge_paths,
        output_root=settings.knowledge_index_path,
        max_parse_bytes=settings.knowledge_max_file_size_mb * 1024 * 1024,
        chunk_size=settings.knowledge_chunk_size_chars,
        overlap_chars=settings.knowledge_chunk_overlap_chars,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a read-only draft queue for PDF/OCR teacher review."
    )
    parser.add_argument(
        "--course",
        action="append",
        choices=KNOWLEDGE_COURSE_IDS,
        help="Limit the audit to one or more course IDs; repeat the option.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path. Without it, no file is written.",
    )
    parser.add_argument(
        "--decision-template-course",
        choices=KNOWLEDGE_COURSE_IDS,
        help="Write a pending teacher-decision YAML template for one course.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings()
    selected_courses = args.course or (
        [args.decision_template_course]
        if args.decision_template_course
        else list(KNOWLEDGE_COURSE_IDS)
    )
    audit = _builder(settings).audit(selected_courses)
    payload = build_ocr_review_queue(audit)
    if args.decision_template_course:
        if args.output is None:
            raise SystemExit("--decision-template-course requires --output")
        template = build_ocr_decision_template(
            payload, args.decision_template_course
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            yaml.safe_dump(template, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
            newline="\n",
        )
        print(
            json.dumps(
                {
                    "course_id": args.decision_template_course,
                    "decision_count": len(template["decisions"]),
                    "output": str(args.output),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
        print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
