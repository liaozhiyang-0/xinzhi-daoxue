from __future__ import annotations

import re
from dataclasses import dataclass

from app.contracts import RetrievalContextPacket

EVIDENCE_REF = re.compile(r"\[(S\d+)\]")


@dataclass(frozen=True, slots=True)
class CitationValidationResult:
    valid: bool
    referenced_ids: tuple[str, ...]
    valid_ids: tuple[str, ...]
    invalid_ids: tuple[str, ...]
    missing: bool
    warnings: tuple[str, ...]


class CitationValidator:
    def validate(
        self,
        answer: str,
        packet: RetrievalContextPacket,
        declared_references: list[str] | tuple[str, ...] = (),
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
        return CitationValidationResult(
            valid=not warnings,
            referenced_ids=referenced,
            valid_ids=valid_ids,
            invalid_ids=invalid,
            missing=missing,
            warnings=tuple(warnings),
        )
