from __future__ import annotations

import re

_IMAGE_LINK_RE = re.compile(
    r"!\[([^\]]*)\]\((?:<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\)"
)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_OCR_MARKER_RE = re.compile(r"^\s*[①②③④⑤⑥⑦⑧⑨⑩]\s*")


def _is_orphan_formula_line(line: str) -> bool:
    value = line.strip()
    if not value:
        return True
    if re.fullmatch(r"(?:-{2,3}|[}\]]|\\(?:\]|\)|right|end\{[^}]+\}))+", value):
        return True
    if _CJK_RE.search(value):
        return False
    return (
        value.count("}") > value.count("{")
        or value.count("]") > value.count("[")
        or ("\\right" in value and "\\left" not in value)
        or ("\\]" in value and "\\[" not in value)
    )


def _trim_incomplete_latex_tail(value: str) -> str:
    """Avoid exposing a partial LaTeX command at an excerpt boundary."""

    return re.sub(r"\\[A-Za-z]*$", "", value).rstrip()


def clean_evidence_excerpt(value: str, *, max_chars: int | None = None) -> str:
    """Make a bounded retrieval excerpt readable without inventing math."""

    raw = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw:
        return ""
    raw = _IMAGE_LINK_RE.sub(lambda match: match.group(1).strip(), raw)
    lines: list[str] = []
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line or line in {"--", "---", r"\]", r"\)"}:
            continue
        delimiter = line.find("---")
        if delimiter >= 0:
            after_delimiter = line[delimiter + 3 :].strip()
            if _OCR_MARKER_RE.match(after_delimiter):
                line = after_delimiter
            else:
                line = f"{line[:delimiter]} {after_delimiter}".strip()
        match = _CJK_RE.search(line)
        if match and re.search(r"\\(?:right|\]|\))|\}\s*$", line[: match.start()]):
            line = line[match.start() :]
        line = re.sub(r"^\s*(?:(?:\\\]|\\\)|\\right\b)\s*)+", "", line)
        line = re.sub(r"^\s*---+\s*|\s+---+\s*", " ", line)
        line = re.sub(r"\\(?:\]|\))", "", line)
        line = re.sub(r"^\s*--+\s*", "", line)
        line = _OCR_MARKER_RE.sub("", line)
        if line and not _is_orphan_formula_line(line):
            lines.append(line)
    cleaned = "\n".join(lines).strip()
    if not cleaned:
        return "资料片段的公式未完整落在检索片段内，请打开原文查看。"
    if max_chars is not None and len(cleaned) > max_chars:
        boundaries = [
            cleaned.rfind(mark, 0, max_chars)
            for mark in ("。", "！", "？", ". ", "；")
        ]
        boundary = max(boundaries)
        cutoff = boundary + 1 if boundary >= max_chars // 2 else max_chars
        cleaned = _trim_incomplete_latex_tail(cleaned[:cutoff].rstrip()) + "…"
    return cleaned


def display_evidence_excerpt(value: str, *, max_chars: int | None = None) -> str:
    """Return a bounded evidence fragment without rewriting source content.

    Retrieval cleanup is useful for anchor matching and prompt context, but it
    must not be used for the user-visible evidence card: removing delimiters,
    image links, or orphaned formula lines can silently change the source.
    The browser decides whether the bounded fragment can be rendered as math;
    otherwise it displays this exact source text.
    """

    raw = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    # A formula-bearing fragment is not safe to cut at an arbitrary character
    # boundary: doing so can drop a denominator, delimiter, or special symbol.
    # Evidence cards must preserve the exact source; the card itself can scroll
    # or wrap, while the full source remains available in the document viewer.
    contains_formula = bool(
        re.search(r"(?:\\[A-Za-z]+|\\\[|\\\(|\\\]|\\\)|\$\$?|\^|_)", raw)
    )
    if max_chars is None or len(raw) <= max_chars or contains_formula:
        return raw
    return raw[:max_chars].rstrip() + "…"
