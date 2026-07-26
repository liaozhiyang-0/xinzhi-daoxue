from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.contracts import RetrievalContextPacket
from app.contracts.knowledge import CitationSupport

EVIDENCE_REF = re.compile(r"\[(S\d+)\]")


@dataclass(frozen=True, slots=True)
class CitationValidationResult:
    valid: bool
    referenced_ids: tuple[str, ...]
    valid_ids: tuple[str, ...]
    invalid_ids: tuple[str, ...]
    missing: bool
    warnings: tuple[str, ...]
    support_status: str = "valid"
    supports: tuple[CitationSupport, ...] = ()


class CitationValidator:
    def validate(
        self,
        answer: str,
        packet: RetrievalContextPacket,
        declared_references: list[str] | tuple[str, ...] = (),
        *,
        manifests: list[dict[str, Any]] | None = None,
        chunks: list[dict[str, Any]] | None = None,
        conclusion_support: dict[str, dict[str, list[str]]] | None = None,
    ) -> CitationValidationResult:
        allowed = {item.evidence_id for item in packet.evidence}
        declared_ids = [
            item.strip().strip("[]")
            for item in declared_references
            if isinstance(item, str) and item.strip()
        ]
        referenced = tuple(
            dict.fromkeys([*EVIDENCE_REF.findall(answer), *declared_ids])
        )
        valid_ids = tuple(item for item in referenced if item in allowed)
        invalid = tuple(item for item in referenced if item not in allowed)
        warnings: list[str] = []
        missing = bool(packet.evidence) and not referenced
        if missing:
            warnings.append("云端回答未引用任何已提供证据")
        if invalid:
            warnings.append("模型引用了未提供的证据编号: " + ", ".join(invalid))
        for item in packet.evidence:
            prefix = f"kb://{packet.course_id}/"
            if not item.source_ref.startswith(prefix):
                warnings.append(f"证据 {item.evidence_id} 来源跨课程或不安全")
        manifest_by_id = {
            str(item.get("document_id", "")): item for item in manifests or []
        }
        chunk_by_id = {str(item.get("chunk_id", "")): item for item in chunks or []}
        evidence_by_id = {item.evidence_id: item for item in packet.evidence}
        supports: list[CitationSupport] = []
        for citation_id in referenced:
            hit = evidence_by_id.get(citation_id)
            supported = (
                (conclusion_support or {}).get(citation_id, {}).get("supported", [])
            )
            unsupported = (
                (conclusion_support or {}).get(citation_id, {}).get("unsupported", [])
            )
            status: Literal[
                "valid",
                "partially_supported",
                "unsupported",
                "stale",
                "invalid_locator",
                "missing_source",
            ] = "valid"
            if hit is None:
                status = "missing_source"
            elif manifests is not None:
                manifest = manifest_by_id.get(hit.document_id)
                if manifest is None:
                    status = "missing_source"
                elif not manifest.get("active", manifest.get("is_active", True)):
                    status = "stale"
                elif hit.document_checksum and hit.document_checksum != str(
                    manifest.get("checksum", manifest.get("content_hash", ""))
                ):
                    status = "stale"
            if status == "valid" and chunks is not None and hit is not None:
                chunk = chunk_by_id.get(hit.chunk_id)
                if chunk is None or not chunk.get("is_active", True):
                    status = "invalid_locator"
            if status == "valid" and unsupported:
                status = "partially_supported" if supported else "unsupported"
            supports.append(
                CitationSupport(
                    citation_id=citation_id,
                    status=status,
                    document_id=hit.document_id if hit else None,
                    document_version=(
                        str(
                            manifest_by_id.get(hit.document_id, {}).get(
                                "document_version"
                            )
                        )
                        if hit and manifest_by_id.get(hit.document_id)
                        else None
                    ),
                    chunk_id=hit.chunk_id if hit else None,
                    supported_conclusions=supported,
                    unsupported_conclusions=unsupported,
                )
            )
        statuses = {item.status for item in supports}
        if not supports and packet.evidence:
            support_status = "unsupported"
        elif statuses <= {"valid"}:
            support_status = "valid"
        elif "valid" in statuses or "partially_supported" in statuses:
            support_status = "partially_supported"
        else:
            support_status = next(iter(statuses), "valid")
        return CitationValidationResult(
            valid=not warnings and support_status == "valid",
            referenced_ids=referenced,
            valid_ids=valid_ids,
            invalid_ids=invalid,
            missing=missing,
            warnings=tuple(warnings),
            support_status=support_status,
            supports=tuple(supports),
        )
