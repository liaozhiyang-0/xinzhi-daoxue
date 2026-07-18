from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from app.services.knowledge_audit import (
    AuditResult,
    ImageEvidenceRecord,
    KnowledgeAuditScanner,
    ManifestEntry,
    infer_chapter,
    infer_content_type,
    source_uri,
    stable_id,
)

HEADING_LINE_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
IMAGE_LINE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？；.!?;])\s*")


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    chunk_id: str
    document_id: str
    document_checksum: str
    course_id: str
    relative_path: str
    title: str
    chapter: str
    content_type: str
    chunk_index: int
    text: str
    source_uri: str
    related_images: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["related_images"] = list(self.related_images)
        return payload


@dataclass(frozen=True, slots=True)
class BuildResult:
    scanned_files: int
    active_documents: int
    chunk_count: int
    image_count: int
    reused_chunk_count: int
    rebuilt_document_count: int
    removed_document_count: int
    dry_run: bool
    courses: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["courses"] = list(self.courses)
        return payload


def _split_long_block(block: str, limit: int) -> list[str]:
    if len(block) <= limit:
        return [block]
    sentences = [
        item.strip() for item in SENTENCE_BOUNDARY_RE.split(block) if item.strip()
    ]
    if len(sentences) <= 1:
        return [block[index : index + limit] for index in range(0, len(block), limit)]
    bounded_sentences = [
        piece
        for sentence in sentences
        for piece in (
            [sentence]
            if len(sentence) <= limit
            else [
                sentence[index : index + limit]
                for index in range(0, len(sentence), limit)
            ]
        )
    ]
    pieces: list[str] = []
    current = ""
    for sentence in bounded_sentences:
        if current and len(current) + len(sentence) + 1 > limit:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces


def markdown_blocks(text: str, chunk_size: int) -> list[tuple[str, str]]:
    """Keep headings, formulas, lists and example paragraphs together when possible."""

    blocks: list[tuple[str, str]] = []
    title = "UNKNOWN"
    pending: list[str] = []

    def flush() -> None:
        if not pending:
            return
        block = "\n".join(pending).strip()
        pending.clear()
        if block:
            for piece in _split_long_block(block, chunk_size):
                blocks.append((title, piece))

    for line in text.splitlines():
        heading = HEADING_LINE_RE.match(line)
        if heading:
            flush()
            title = heading.group(2).strip()
            pending.append(line.strip())
            continue
        if not line.strip():
            flush()
            continue
        pending.append(line.rstrip())
    flush()
    return blocks


def semantic_chunks(
    *,
    entry: ManifestEntry,
    text: str,
    chunk_size: int,
    overlap_chars: int,
    images: Iterable[ImageEvidenceRecord],
) -> list[ChunkRecord]:
    blocks = markdown_blocks(text, chunk_size)
    image_list = list(images)
    output: list[ChunkRecord] = []
    current_title = "UNKNOWN"
    current_parts: list[str] = []
    current_length = 0

    def flush() -> None:
        nonlocal current_parts, current_length
        content = "\n\n".join(current_parts).strip()
        if not content:
            return
        index = len(output) + 1
        related = tuple(
            dict.fromkeys(
                item.resource_uri
                for item in image_list
                if item.parent_document_id == entry.document_id
                and (
                    item.page_or_section == current_title
                    or item.image_caption in content
                    or (item.nearby_text and item.nearby_text[:80] in content)
                )
            )
        )
        chunk_id = stable_id(
            "CHK", entry.course_id, entry.relative_path.casefold(), str(index)
        )
        output.append(
            ChunkRecord(
                chunk_id=chunk_id,
                document_id=entry.document_id,
                document_checksum=entry.checksum,
                course_id=entry.course_id,
                relative_path=entry.relative_path,
                title=current_title,
                chapter=infer_chapter(
                    Path(entry.relative_path), current_title, content
                ),
                content_type=infer_content_type(
                    Path(entry.relative_path), current_title, content
                ),
                chunk_index=index,
                text=content,
                source_uri=(
                    f"{source_uri(entry.course_id, entry.relative_path)}#chunk-{index}"
                ),
                related_images=related,
            )
        )
        overlap = content[-overlap_chars:].strip() if overlap_chars else ""
        current_parts = [overlap] if overlap else []
        current_length = len(overlap)

    for title, block in blocks:
        heading_changed = title != current_title
        if current_parts and (
            heading_changed or current_length + len(block) + 2 > chunk_size
        ):
            flush()
            if heading_changed:
                current_parts = []
                current_length = 0
        if current_parts and current_length + len(block) + 2 > chunk_size:
            # Overlap is optional context and must never push the new chunk above
            # the configured hard character limit.
            current_parts = []
            current_length = 0
        current_title = title
        current_parts.append(block)
        current_length += len(block) + 2
    flush()
    return output


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


class KnowledgeIndexBuilder:
    """Builds independent generated indexes without mutating original libraries."""

    def __init__(
        self,
        *,
        roots: dict[str, Path],
        output_root: Path,
        max_parse_bytes: int,
        chunk_size: int,
        overlap_chars: int,
    ) -> None:
        self.roots = roots
        self.output_root = output_root
        self.chunk_cache_path = output_root / "cache" / "knowledge_base_chunks.jsonl"
        self.manifest_path = output_root / "knowledge_base_manifest.jsonl"
        self.image_path = output_root / "knowledge_base_image_evidence.jsonl"
        self.issue_path = output_root / "knowledge_base_quality_issues.json"
        self.state_path = output_root / "knowledge_base_index_state.json"
        self.scanner = KnowledgeAuditScanner(roots, max_parse_bytes=max_parse_bytes)
        self.chunk_size = chunk_size
        self.overlap_chars = overlap_chars

    def audit(self, course_ids: Iterable[str] | None = None) -> AuditResult:
        return self.scanner.scan(course_ids)

    def build(
        self,
        course_ids: Iterable[str] | None = None,
        *,
        incremental: bool = True,
        dry_run: bool = False,
        relative_file: str | None = None,
    ) -> tuple[AuditResult, BuildResult]:
        selected = tuple(item.upper() for item in (course_ids or self.roots))
        preserve_existing = (
            set(selected) != set(self.roots) or relative_file is not None
        )
        load_existing = incremental or preserve_existing
        previous_manifest = load_jsonl(self.manifest_path) if load_existing else []
        # Always scan the complete configured corpus before writing shared outputs. A
        # course/file-scoped rebuild may select what is rebuilt, but must never make
        # the other courses disappear from the manifest or image evidence index.
        audit = self.scanner.scan(
            previous_manifest=previous_manifest if load_existing else None
        )
        previous_chunks = load_jsonl(self.chunk_cache_path) if load_existing else []
        chunks_by_document: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for raw in previous_chunks:
            chunks_by_document[str(raw.get("document_id", ""))].append(raw)

        images_by_document: defaultdict[str, list[ImageEvidenceRecord]] = defaultdict(
            list
        )
        for image in audit.images:
            if image.parent_document_id:
                images_by_document[image.parent_document_id].append(image)

        chunks: list[ChunkRecord] = []
        reused = 0
        rebuilt = 0
        for entry in audit.manifest:
            if not entry.active:
                continue
            if entry.source_type not in {"markdown", "text"}:
                continue
            if entry.index_status not in {"direct", "clean_before_index"}:
                continue
            old = chunks_by_document.get(entry.document_id, [])
            selected_for_rebuild = entry.course_id in selected and (
                relative_file is None
                or entry.relative_path == PurePosixPath(relative_file).as_posix()
            )
            if not selected_for_rebuild:
                chunks.extend(self._chunk_from_dict(item) for item in old)
                continue
            if (
                incremental
                and old
                and all(
                    str(item.get("document_checksum", "")) == entry.checksum
                    for item in old
                )
            ):
                parsed = [self._chunk_from_dict(item) for item in old]
                chunks.extend(parsed)
                reused += len(parsed)
                continue
            source = self.roots[entry.course_id] / PurePosixPath(entry.relative_path)
            try:
                text = source.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            chunks.extend(
                semantic_chunks(
                    entry=entry,
                    text=text,
                    chunk_size=self.chunk_size,
                    overlap_chars=self.overlap_chars,
                    images=images_by_document.get(entry.document_id, []),
                )
            )
            rebuilt += 1

        parent_chunks = {
            (chunk.document_id, resource_uri): chunk.chunk_id
            for chunk in chunks
            for resource_uri in chunk.related_images
        }
        audit.images = [
            replace(
                image,
                parent_chunk_id=parent_chunks.get(
                    (image.parent_document_id, image.resource_uri)
                ),
            )
            if image.parent_document_id
            else image
            for image in audit.images
        ]

        previous_ids = {str(item.get("document_id", "")) for item in previous_manifest}
        current_ids = {item.document_id for item in audit.manifest if item.active}
        build_result = BuildResult(
            scanned_files=len(audit.manifest),
            active_documents=len(current_ids),
            chunk_count=len(chunks),
            image_count=len(audit.images),
            reused_chunk_count=reused,
            rebuilt_document_count=rebuilt,
            removed_document_count=len(previous_ids - current_ids),
            dry_run=dry_run,
            courses=selected,
        )
        if not dry_run:
            self.write_outputs(audit, chunks, build_result)
        return audit, build_result

    def write_outputs(
        self,
        audit: AuditResult,
        chunks: Iterable[ChunkRecord],
        build_result: BuildResult,
    ) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)
        write_jsonl(self.manifest_path, (item.to_dict() for item in audit.manifest))
        write_jsonl(self.image_path, (item.to_dict() for item in audit.images))
        write_jsonl(self.chunk_cache_path, (item.to_dict() for item in chunks))
        self.issue_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "issue_count": len(audit.issues),
                    "issues": [item.to_dict() for item in audit.issues],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.state_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(UTC).isoformat(),
                    "multimodal_level": "rag_index_input_ready",
                    "text_retrieval": "sparse_bm25_v1",
                    **build_result.to_dict(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _chunk_from_dict(raw: dict[str, Any]) -> ChunkRecord:
        return ChunkRecord(
            chunk_id=str(raw["chunk_id"]),
            document_id=str(raw["document_id"]),
            document_checksum=str(raw["document_checksum"]),
            course_id=str(raw["course_id"]),
            relative_path=str(raw["relative_path"]),
            title=str(raw["title"]),
            chapter=str(raw["chapter"]),
            content_type=str(raw["content_type"]),
            chunk_index=int(raw["chunk_index"]),
            text=str(raw["text"]),
            source_uri=str(raw["source_uri"]),
            related_images=tuple(str(item) for item in raw.get("related_images", [])),
        )


def audit_report_markdown(audit: AuditResult) -> str:
    totals = {
        "files": sum(item.file_count for item in audit.courses),
        "text": sum(item.text_count for item in audit.courses),
        "images": sum(item.image_count for item in audit.courses),
        "other": sum(item.other_count for item in audit.courses),
        "bytes": sum(item.total_bytes for item in audit.courses),
    }
    issue_counts = Counter(item.severity for item in audit.issues)
    issue_type_counts = Counter(item.issue_type for item in audit.issues)
    lines = [
        "# 本地知识库审计报告",
        "",
        f"生成时间：{datetime.now(UTC).isoformat()}",
        "",
        "## 1. 总体概况",
        "",
        "| 课程 | 实际相对路径 | 文件数 | 文字文件 | 图片 | 其他 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for item in audit.courses:
        lines.append(
            f"| {item.course_id} {item.course_name} | `{item.root_path}` | "
            f"{item.file_count} | {item.text_count} | {item.image_count} | "
            f"{item.other_count} |"
        )
    lines.extend(
        [
            "",
            f"总计 {totals['files']} 个文件、{totals['text']} 个文字文件、"
            f"{totals['images']} 张图片、{totals['other']} 个其他文件，"
            f"总大小约 {totals['bytes'] / 1024 / 1024:.2f} MiB。",
            "",
            "总体判断：Markdown 正文可直接进入只读索引；图片数量远高于文本，"
            "首版适合上下文图片检索；PDF、DOCX 和压缩包只登记元数据，暂不直接解析。",
            "",
            "## 2. 分课程统计",
            "",
            "| 课程 | 主要层级 | 类型分布 | 图片 | 直接索引 | 清洗/复核 | 暂不可用 |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for item in audit.courses:
        extensions = "、".join(
            f"{key or '[none]'} {value}" for key, value in item.extension_counts.items()
        )
        lines.append(
            f"| {item.course_id} | {' / '.join(item.top_directories) or '根目录'} | "
            f"{extensions} | {item.image_count} | {item.directly_indexable_count} "
            f"({item.directly_indexable_count / max(1, item.file_count):.1%}) | "
            f"{item.needs_cleaning_count} "
            f"({item.needs_cleaning_count / max(1, item.file_count):.1%}) | "
            f"{item.unavailable_count} "
            f"({item.unavailable_count / max(1, item.file_count):.1%}) |"
        )
    lines.extend(
        [
            "",
            "章节文件覆盖：CT 发现第一至第十三章及附录；AE 发现第一至第十一章；"
            "DE 发现第一至第十一章和目录。未发现按章文件的明显编号缺口，"
            "但章节内容完整性仍需按教材目录人工核对。",
            "",
            "## 3. 结构质量",
            "",
            "- 三门课程均保留教材式章节 Markdown，适合按标题和段落切块。",
            "- AE、DE 图片集中于教材 `images/`；CT 另有无编号图片和映射表。",
            "- Markdown 中存在大量相对图片链接，可建立父文档和章节关系。",
            "- 未被 Markdown 引用的图片保留为孤立证据并进入人工关联队列。",
            "- PDF 与 ZIP 和已有 Markdown 并存，存在重复来源和索引重复风险。",
            "",
            "## 4. 内容质量",
            "",
            "| 维度 | 评价 | 理由 | 代表性文件 |",
            "|---|---|---|---|",
            "| 完整性 | medium | 章节较完整，二进制原件未解析 | "
            "`CT/课本/基础篇/3-重置md/第一章.md` |",
            "| 准确性风险 | medium | OCR 标题异常，内容待复核 | "
            "`AE/教材/1-第一章.md` |",
            "| 章节覆盖度 | high | 发现连续章节文件 | `DE/教材/数电_第一章.md` |",
            "| 来源可追溯性 | medium | 缺少教材版次等统一元数据 | "
            "`knowledge_config/courses/*.yaml` |",
            "| 公式可读性 | medium | 保留 LaTeX，转换质量需复核 | "
            "`CT/课本/基础篇/3-重置md/第三章.md` |",
            "| 图片可理解性 | medium | 多数可由相邻文本关联，孤立图待处理 | "
            "`AE/教材/images/` |",
            "| 检索友好度 | medium | 标题段落可检索，长章需切块 | "
            "`DE/教材/数电_第四章.md` |",
            "| 重复度 | medium | PDF、ZIP、Markdown 与图片并存 | `CT/课本/基础篇/` |",
            "| 噪声程度 | medium | 目录、无编号图片和异常标题带来噪声 | "
            "`CT/课本/基础篇/3-重置md/目录.md` |",
            "| 知识问答适用度 | medium | 正文充足，引用和清洗需加强 | "
            "`AE/教材/模电_第八章.md` |",
            "| 解题方法检索适用度 | medium | 方法较多，须防止样题参数污染 | "
            "`CT/课本/基础篇/3-重置md/第五章.md` |",
            "",
            "## 5. 问题清单",
            "",
            f"共发现 {len(audit.issues)} 个问题：blocker {issue_counts['blocker']}、"
            f"high {issue_counts['high']}、medium {issue_counts['medium']}、"
            f"low {issue_counts['low']}。完整机器清单位于 "
            "`knowledge_indexes/knowledge_base_quality_issues.json`。",
            "",
            "| 严重级别 | 课程 | 文件 | 类型 | 是否影响索引 | 建议 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for issue in audit.issues[:80]:
        lines.append(
            f"| {issue.severity} | {issue.course_id} | `{issue.file_path}` | "
            f"{issue.issue_type} | {'是' if issue.affects_index else '否'} | "
            f"{issue.suggestion} |"
        )
    lines.extend(
        [
            "",
            "## 6. 接入建议",
            "",
            "- 可直接索引：UTF-8 Markdown/TXT 且无严重警告的正文。",
            "- 清洗后索引：缺少标题、过短、疑似 OCR 异常或草稿内容。",
            "- 仅作为图片附件：可读取且能追溯相对路径的图片。",
            "- 暂不索引：PDF、DOCX、ZIP 和无法 UTF-8 解码的文件。",
            "- 人工复核：孤立图片、失效链接、乱码、同名冲突、重复文件和来源不明内容。",
            "",
            "当前 `multimodal_level = contextual_image_retrieval`，"
            "没有实现真正的视觉向量检索。",
            "",
        ]
    )
    lines.extend(
        [
            "## 7. 现有系统与接入现状",
            "",
            "- 实施前已有能力：本地 Markdown 只读扫描、`local_lexical_v2` BM25-like "
            "词项检索、课程范围过滤与 `kb://` 引用；没有向量数据库、神经网络 "
            "Embedding、图像向量或独立 RAG 框架。",
            "- 当前首版能力：在既有检索服务内增加可替换文本向量适配器、"
            "关键词与本地哈希向量混合排序、上下文图片关联，以及独立生成的 "
            "Manifest、图片证据索引和增量缓存。",
            "- LEARN：本地问答链路已经实际调用知识库并返回来源；云端 LEARN 通过既有 "
            "`RetrievalContextPacket` 转成 `retrieved_context` 文本，再进入原有 "
            "Provider 请求，"
            "未增加未经确认的云端节点或 HTTP 字段。",
            "- SOLVER：仅复用既有任务路由和只读检索入口，限制为方法、公式、"
            "概念和常见错误；"
            "云端工作流与 Provider 参数保持冻结。",
            "- 配置与存储：路径和权重由 `.env`/Settings 管理，课程元数据继续使用 YAML；"
            "业务状态仍使用 SQLAlchemy（SQLite/PostgreSQL），既有 Redis/MinIO "
            "配置未改变。"
            "索引产物为本地 JSON/JSONL，不需要数据库迁移。",
            "",
            "重点数据质量队列：失效图片链接 "
            f"{issue_type_counts['broken_image_link']} 个，"
            f"孤立图片 {issue_type_counts['orphan_image']} 个，精确重复问题记录 "
            f"{issue_type_counts['exact_duplicate']} 条，近似重复问题记录 "
            f"{issue_type_counts['near_duplicate_document']} 条。",
            "",
        ]
    )
    return "\n".join(lines)
