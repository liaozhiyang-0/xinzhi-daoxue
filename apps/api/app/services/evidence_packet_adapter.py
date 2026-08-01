from __future__ import annotations

from app.contracts import EvidencePacketV1, EvidenceSourceV1, RetrievalContextPacket

SUPPORTED_EVIDENCE_COURSES = frozenset({"CT", "AE", "DE"})
MAX_EVIDENCE_EXCERPT_CHARS = 1_200


class EvidencePacketAdapterService:
    """Adapts an existing retrieval packet without performing retrieval."""

    def from_context(
        self,
        packet: RetrievalContextPacket | None,
        *,
        query: str,
        course_id: str,
        applicable_skill_ids: list[str] | None = None,
    ) -> EvidencePacketV1:
        course = course_id.upper()
        if course not in SUPPORTED_EVIDENCE_COURSES:
            return EvidencePacketV1(
                query=query,
                course_id=course,
                retrieval_status="unavailable",
                evidence_sufficiency="unavailable",
                warnings=[f"evidence unavailable for course {course}"],
            )
        if packet is None:
            return EvidencePacketV1(
                query=query,
                course_id=course,
                retrieval_status="not_run",
                evidence_sufficiency="unavailable",
                warnings=["retrieval context unavailable"],
            )
        warnings = list(packet.warnings)
        sources: list[EvidenceSourceV1] = []
        for hit in packet.evidence:
            page = None
            source_version = None
            warnings.append(f"{hit.evidence_id}: page metadata unavailable")
            warnings.append(f"{hit.evidence_id}: source version unavailable")
            sources.append(
                EvidenceSourceV1(
                    source_id=hit.evidence_id,
                    document_id=hit.document_id,
                    chunk_id=hit.chunk_id,
                    course_id=hit.course_id.value,
                    chapter=hit.chapter or None,
                    section=hit.section or None,
                    page=page,
                    title=hit.title or None,
                    content_excerpt=hit.content[:MAX_EVIDENCE_EXCERPT_CHARS],
                    source_ref=hit.source_ref or None,
                    applicable_skill_ids=list(applicable_skill_ids or []),
                    retrieval_score=hit.score,
                    rerank_score=hit.score_components.get("rerank_score"),
                    score_components=hit.score_components,
                    document_checksum=hit.document_checksum or None,
                    source_version=source_version,
                    support_level="potentially_relevant",
                    image_refs=[
                        item.resource_uri for item in hit.related_images
                    ],
                )
            )
        return EvidencePacketV1(
            query=packet.query or query,
            course_id=course,
            retrieval_status=packet.rag_status,
            evidence_sufficiency=packet.evidence_status,
            sources=sources,
            warnings=list(dict.fromkeys(warnings)),
        )
