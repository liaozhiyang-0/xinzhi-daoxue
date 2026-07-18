from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.core.config import Settings  # noqa: E402
from app.services.knowledge_base import KnowledgeBaseService  # noqa: E402
from app.services.knowledge_index import (  # noqa: E402
    KnowledgeIndexBuilder,
    audit_report_markdown,
    load_jsonl,
)
from app.services.rag_index import MultimodalRAGIndexer  # noqa: E402
from app.services.rag_retrieval import RAGRetrievalService  # noqa: E402
from app.services.rag_runtime import (  # noqa: E402
    create_image_embedding_provider,
    create_reranker_provider,
    create_text_embedding_provider,
    create_vector_store,
)

COURSE_CHOICES = ("CT", "AE", "DE")


def builder_from_settings(settings: Settings) -> KnowledgeIndexBuilder:
    return KnowledgeIndexBuilder(
        roots=settings.knowledge_paths,
        output_root=settings.knowledge_index_path,
        max_parse_bytes=settings.knowledge_max_file_size_mb * 1024 * 1024,
        chunk_size=settings.knowledge_chunk_size_chars,
        overlap_chars=settings.knowledge_chunk_overlap_chars,
    )


def selected_courses(values: list[str] | None) -> list[str]:
    return values or list(COURSE_CHOICES)


def rag_components(
    settings: Settings,
) -> tuple[RAGRetrievalService, MultimodalRAGIndexer]:
    lexical = KnowledgeBaseService(settings)
    text = create_text_embedding_provider(settings)
    image = create_image_embedding_provider(settings)
    reranker = create_reranker_provider(settings)
    store = create_vector_store(settings)
    retrieval = RAGRetrievalService(settings, lexical, text, image, reranker, store)
    indexer = MultimodalRAGIndexer(settings, text, image, store)
    return retrieval, indexer


def command_audit(args: argparse.Namespace, settings: Settings) -> int:
    audit = builder_from_settings(settings).audit(selected_courses(args.course))
    print(
        json.dumps(
            {
                "mode": "audit_read_only",
                "files": len(audit.manifest),
                "images": len(audit.images),
                "issues": len(audit.issues),
                "courses": [item.to_dict() for item in audit.courses],
                "writes_performed": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_build(args: argparse.Namespace, settings: Settings) -> int:
    builder = builder_from_settings(settings)
    audit, result = builder.build(
        selected_courses(args.course),
        incremental=not args.full,
        dry_run=args.dry_run,
        relative_file=args.file,
    )
    if not args.dry_run:
        report_path = ROOT / "docs" / "reviews" / "knowledge_base_audit_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            audit_report_markdown(audit), encoding="utf-8", newline="\n"
        )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if args.rag:
        _rag_build(args, settings, force_vectors=args.force_vectors)
    return 0


def _rag_build(
    args: argparse.Namespace,
    settings: Settings,
    *,
    force_vectors: bool,
) -> None:
    retrieval, indexer = rag_components(settings)
    courses = selected_courses(args.course)
    scoped = courses[0] if len(courses) == 1 else None
    include_text = bool(args.text or not args.images)
    include_images = bool(args.images or not args.text)
    try:
        result = indexer.build(
            course_id=scoped,
            include_text=include_text,
            include_images=include_images,
            incremental=not args.full,
            force_vectors=force_vectors,
            relative_file=args.file,
            relative_image=args.image,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
        if args.delete_stale_points and not args.dry_run:
            chunks = load_jsonl(indexer.chunk_path)
            images = load_jsonl(indexer.image_path)
            deleted = indexer.vector_store.prune(
                text_ids={str(item["chunk_id"]) for item in chunks},
                image_ids={str(item["image_id"]) for item in images},
            )
        else:
            deleted = {}
        print(
            json.dumps(
                {"rag_build": result.to_dict(), "stale_points": deleted},
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        retrieval.close()


def command_rebuild(args: argparse.Namespace, settings: Settings) -> int:
    args.full = True
    args.rag = True
    args.force_vectors = True
    return command_build(args, settings)


def command_query(args: argparse.Namespace, settings: Settings) -> int:
    service, _ = rag_components(settings)
    try:
        result = service.search(
            query_text=args.text or "",
            query_image=Path(args.image_query) if args.image_query else None,
            course_id=args.course,
            top_k=args.top_k,
        )
    finally:
        service.close()
    print(
        json.dumps(
            {
                "query": result.query,
                "course_id": args.course,
                "retrieval_mode": result.retrieval_mode,
                "confidence": result.confidence,
                "warnings": result.warnings,
                "rag_status": result.rag_status,
                "embedding_status": result.embedding_status,
                "vector_store_status": result.vector_store_status,
                "reranker_status": result.reranker_status,
                "retrieval_trace_id": result.retrieval_trace_id,
                "index_version": result.index_version,
                "hits": [
                    {
                        "document_id": hit.document_id,
                        "chunk_id": hit.chunk_id,
                        "title": hit.title,
                        "chapter": hit.chapter,
                        "content_type": hit.content_type,
                        "source_uri": hit.source_ref,
                        "score": hit.score,
                        "related_images": [
                            image.model_dump(mode="json")
                            for image in hit.related_images
                        ],
                    }
                    for hit in result.hits
                ],
                "image_hits": [
                    image.model_dump(mode="json") for image in result.image_hits
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_stats(_args: argparse.Namespace, settings: Settings) -> int:
    service, _ = rag_components(settings)
    try:
        print(json.dumps(service.health(), ensure_ascii=False, indent=2))
    finally:
        service.close()
    return 0


def command_health(args: argparse.Namespace, settings: Settings) -> int:
    service, _ = rag_components(settings)
    try:
        if args.load_models:
            service.text_provider.load()
            if settings.image_embedding_enabled:
                service.image_provider.load()
            if settings.reranker_enabled:
                service.reranker.load()
        payload = service.health()
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["rag_status"] == "ready" else 2
    finally:
        service.close()


def command_validate(_args: argparse.Namespace, settings: Settings) -> int:
    builder = builder_from_settings(settings)
    manifest = load_jsonl(builder.manifest_path)
    issues: list[str] = []
    seen_ids: set[str] = set()
    required = {
        "document_id",
        "course_id",
        "relative_path",
        "checksum",
        "parse_status",
        "index_status",
    }
    for line_number, item in enumerate(manifest, start=1):
        missing = required - item.keys()
        if missing:
            issues.append(f"line {line_number}: missing {sorted(missing)}")
        document_id = str(item.get("document_id", ""))
        if document_id in seen_ids:
            issues.append(f"line {line_number}: duplicate document_id")
        seen_ids.add(document_id)
        relative = PurePosixPath(str(item.get("relative_path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            issues.append(f"line {line_number}: unsafe relative_path")
        source_path = str(item.get("source_path", ""))
        if Path(source_path).is_absolute():
            issues.append(f"line {line_number}: absolute source_path exposed")
    payload: dict[str, Any] = {
        "valid": bool(manifest) and not issues,
        "manifest_rows": len(manifest),
        "issues": issues,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["valid"] else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="芯智导学本地知识库审计与索引工具")
    subparsers = root.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="只读扫描，不写入文件")
    audit.add_argument("--course", action="append", choices=COURSE_CHOICES)

    build = subparsers.add_parser("build", help="构建 Manifest、图片和文本索引")
    build.add_argument("--course", action="append", choices=COURSE_CHOICES)
    build.add_argument("--file", help="仅重建课程内的一个 POSIX 相对路径")
    build.add_argument("--full", action="store_true", help="忽略旧缓存并完全重建")
    build.add_argument("--dry-run", action="store_true", help="扫描和规划但不写入")
    build.add_argument("--rag", action="store_true", help="同时构建真实向量索引")
    build.add_argument("--text", action="store_true", help="只构建文本向量")
    build.add_argument("--images", action="store_true", help="只构建图片向量")
    build.add_argument("--image", help="仅重建课程内的一张图片相对路径")
    build.add_argument("--force-vectors", action="store_true", help="强制重建模型向量")
    build.add_argument("--batch-size", type=int, help="覆盖文本 Embedding 批大小")
    build.add_argument(
        "--delete-stale-points", action="store_true", help="清理已失效 Qdrant point"
    )

    rebuild = subparsers.add_parser("rebuild", help="全量重建元数据与真实向量")
    rebuild.add_argument("--course", action="append", choices=COURSE_CHOICES)
    rebuild.add_argument("--file")
    rebuild.add_argument("--image")
    rebuild.add_argument("--text", action="store_true")
    rebuild.add_argument("--images", action="store_true")
    rebuild.add_argument("--batch-size", type=int)
    rebuild.add_argument("--dry-run", action="store_true")
    rebuild.add_argument("--delete-stale-points", action="store_true")

    query = subparsers.add_parser("query", help="查询现有本地混合索引")
    query.add_argument("--course", required=True, choices=COURSE_CHOICES)
    query.add_argument("--text")
    query.add_argument("--image-query", help="用户查询图片路径")
    query.add_argument("--top-k", type=int, default=3)

    subparsers.add_parser("validate", help="验证已生成的 Manifest")
    subparsers.add_parser("stats", help="查看模型、Qdrant 和索引统计")
    health = subparsers.add_parser("health", help="检查完整 RAG 健康状态")
    health.add_argument("--load-models", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    settings = Settings()
    commands = {
        "audit": command_audit,
        "build": command_build,
        "rebuild": command_rebuild,
        "query": command_query,
        "validate": command_validate,
        "stats": command_stats,
        "health": command_health,
    }
    return commands[args.command](args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
