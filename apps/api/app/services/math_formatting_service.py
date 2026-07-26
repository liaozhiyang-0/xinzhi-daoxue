from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import Any, TypeGuard

from app.contracts.math_content import (
    MathBlockType,
    MathExpression,
    MathRichContent,
    MathSegmentType,
    RichTextSegment,
)
from app.services.math_symbol_dictionary import (
    ALLOWED_COMMANDS,
    ALLOWED_ENVIRONMENTS,
    DANGEROUS_COMMANDS,
    DEFAULT_PHASOR_STYLE,
    PHASOR_STYLES,
    SYMBOLS,
)

logger = logging.getLogger(__name__)

MATH_OUTPUT_INSTRUCTION = (
    "所有数学表达式必须使用合法 LaTeX：行内公式使用 $...$，独立公式使用 $$...$$；"
    "导数、积分、求和、矩阵和方程组使用标准命令，不输出 dvdt、d2vdt2、int0inf、sqrt3 "
    "等压缩形式；不要在代码块中包裹数学公式。结构化公式字段只保存 LaTeX 正文，"
    "不包含 $$ 分隔符。"
)

_COMMAND_RE = re.compile(r"(?<!\\)\\[A-Za-z]+")
_ENVIRONMENT_RE = re.compile(r"\\(begin|end)\{([^{}]+)\}")
_MATRIX_ENVIRONMENTS = frozenset(
    {"matrix", "pmatrix", "bmatrix", "vmatrix", "Vmatrix", "smallmatrix"}
)
_PROTECTED_TEXT_RE = re.compile(
    r"(?:https?://|www\.|[A-Za-z]:\\|/(?:[^/\s]+/)+|\b\d{4}/\d{1,2}/\d{1,2}\b|"
    r"\b\d{1,3}(?:\.\d{1,3}){3}\b|\bv?\d+\.\d+(?:\.\d+)*\b)",
    re.IGNORECASE,
)
_HIGH_CONFIDENCE_TOKEN_RE = re.compile(
    r"d2[A-Za-z](?:/d|d)[A-Za-z]2|d[A-Za-z](?:/d|d)[A-Za-z]|"
    r"∂[A-Za-z]\s*/\s*∂[A-Za-z]|(?:delf\s*/\s*delx)|"
    r"∫|Σ|√|\bsqrt\s*\(|\bsum\s+[A-Za-z]\s*=|\bprod\s+[A-Za-z]\s*=|"
    r"\blim(?:_|\s+[A-Za-z]\s*->)|\\(?:frac|int|iint|iiint|sum|prod|lim|begin)\b",
    re.IGNORECASE,
)
_INLINE_HIGH_CONFIDENCE_RE = re.compile(
    r"(?:d2[A-Za-z](?:/d|d)[A-Za-z]2|d[A-Za-z](?:/d|d)[A-Za-z]|"
    r"∂[A-Za-z]\s*/\s*∂[A-Za-z]|delf\s*/\s*delx|"
    r"sqrt\([^()\n]+\)|√(?:\([^()\n]+\)|[0-9A-Za-z]+)|"
    r"∫[^，。；;\n]+?d[A-Za-zτ])",
    re.IGNORECASE,
)
_UNICODE_SUPERSCRIPTS = str.maketrans(
    {
        "⁰": "0",
        "¹": "1",
        "²": "2",
        "³": "3",
        "⁴": "4",
        "⁵": "5",
        "⁶": "6",
        "⁷": "7",
        "⁸": "8",
        "⁹": "9",
    }
)


@dataclass(slots=True)
class _ProcessedChunk:
    markdown: str
    plain_text: str
    segments: list[RichTextSegment]
    expressions: list[MathExpression]
    warnings: list[str]


class MathFormattingService:
    """Deterministic LaTeX normalization and Markdown segmentation boundary."""

    def __init__(self, *, phasor_style: str = DEFAULT_PHASOR_STYLE) -> None:
        if phasor_style not in PHASOR_STYLES:
            raise ValueError(f"unsupported phasor style: {phasor_style}")
        self.phasor_style = phasor_style

    def normalize_latex(
        self,
        latex: str,
        *,
        block_type: MathBlockType | None = None,
    ) -> MathExpression:
        source = str(latex).strip()
        body, inferred_type = self._strip_math_delimiters(source)
        normalized, repair_warnings = self._normalize_math_text(body)
        resolved_type = self._classify_block_type(
            normalized, block_type or inferred_type
        )
        validation_warnings = self.validate_latex(normalized)
        warnings = list(dict.fromkeys([*repair_warnings, *validation_warnings]))
        invalid = any(
            item.startswith(
                (
                    "dangerous_command",
                    "unbalanced_",
                    "mismatched_",
                    "unclosed_",
                    "empty_formula",
                )
            )
            for item in warnings
        )
        expression_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
        return MathExpression(
            expression_id=f"math_{expression_hash}",
            latex=normalized,
            block_type=resolved_type,
            source_text=source or None,
            normalized=normalized != body,
            validation_status="invalid"
            if invalid
            else "warning"
            if warnings
            else "valid",
            variables=self._variables(normalized),
            warnings=warnings,
            metadata={"expression_hash": expression_hash},
        )

    def normalize_equation_list(self, equations: list[str]) -> list[MathExpression]:
        return [
            self.normalize_latex(item, block_type=MathBlockType.DISPLAY)
            for item in equations
        ]

    def matrix_to_latex(
        self,
        rows: Sequence[Sequence[object]],
        *,
        environment: str = "bmatrix",
    ) -> MathExpression:
        if environment not in _MATRIX_ENVIRONMENTS:
            raise ValueError(f"unsupported matrix environment: {environment}")
        if not rows or not all(rows):
            return self.normalize_latex("", block_type=MathBlockType.MATRIX)
        widths = {len(row) for row in rows}
        body = "\\\\\n".join(
            " & ".join(self.normalize_latex(str(cell)).latex for cell in row)
            for row in rows
        )
        expression = self.normalize_latex(
            f"\\begin{{{environment}}}\n{body}\n\\end{{{environment}}}",
            block_type=MathBlockType.MATRIX,
        )
        if len(widths) != 1:
            expression.warnings.append("matrix_column_count_mismatch")
            expression.validation_status = "warning"
        return expression

    def process_markdown(self, markdown: str) -> MathRichContent:
        started = perf_counter()
        source = str(markdown or "").replace("\r\n", "\n").replace("\r", "\n")
        chunks: list[_ProcessedChunk] = []
        lines = source.splitlines(keepends=True)
        index = 0
        in_fence = False
        fence_buffer: list[str] = []
        while index < len(lines):
            line = lines[index]
            stripped = line.lstrip()
            if in_fence:
                fence_buffer.append(line)
                if stripped.startswith("```") or stripped.startswith("~~~"):
                    chunks.append(
                        self._protected_chunk(
                            "".join(fence_buffer), MathSegmentType.CODE
                        )
                    )
                    fence_buffer = []
                    in_fence = False
                index += 1
                continue
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = True
                fence_buffer = [line]
                index += 1
                continue
            block = self._consume_display_block(lines, index)
            if block is not None:
                consumed, raw_body, trailing_newline = block
                expression = self.normalize_latex(
                    raw_body, block_type=MathBlockType.DISPLAY
                )
                delimiter = f"$$\n{expression.latex}\n$$"
                if trailing_newline:
                    delimiter += "\n"
                chunks.append(self._math_chunk(delimiter, expression, display=True))
                index += consumed
                continue
            if self._is_markdown_table_line(line):
                chunks.append(self._protected_chunk(line, MathSegmentType.TABLE))
                index += 1
                continue
            chunks.append(self._process_inline_line(line))
            index += 1
        if fence_buffer:
            chunk = self._protected_chunk("".join(fence_buffer), MathSegmentType.CODE)
            chunk.warnings.append("unclosed_code_fence")
            chunks.append(chunk)

        result = MathRichContent(
            plain_text="".join(item.plain_text for item in chunks),
            markdown="".join(item.markdown for item in chunks),
            segments=[segment for item in chunks for segment in item.segments],
            math_expressions=[
                expression for item in chunks for expression in item.expressions
            ],
            warnings=list(
                dict.fromkeys(warning for item in chunks for warning in item.warnings)
            ),
        )
        elapsed = (perf_counter() - started) * 1000
        if elapsed > 50:
            logger.warning(
                "math formatting exceeded target",
                extra={
                    "elapsed_ms": round(elapsed, 2),
                    "expression_count": len(result.math_expressions),
                    "failure_types": sorted(result.warnings),
                    "content_hash": hashlib.sha256(source.encode("utf-8")).hexdigest()[
                        :16
                    ],
                },
            )
        return result

    def build_from_structured_result(
        self, structured_result: Mapping[str, Any]
    ) -> MathRichContent:
        answer = self._answer_markdown(structured_result)
        content = self.process_markdown(answer)
        structured_expressions: list[MathExpression] = []
        for candidate in self._structured_formula_candidates(structured_result):
            if self._is_matrix(candidate):
                structured_expressions.append(self.matrix_to_latex(candidate))
            elif isinstance(candidate, str) and candidate.strip():
                structured_expressions.append(
                    self.normalize_latex(candidate, block_type=MathBlockType.DISPLAY)
                )
        seen = {item.latex for item in content.math_expressions}
        for expression in structured_expressions:
            if expression.latex not in seen:
                content.math_expressions.append(expression)
                seen.add(expression.latex)
            content.warnings.extend(expression.warnings)
        content.warnings = list(dict.fromkeys(content.warnings))
        return content

    def validate_latex(self, latex: str) -> list[str]:
        text = str(latex)
        warnings: list[str] = []
        if not text.strip():
            return ["empty_formula"]
        if "$$" in text:
            warnings.append("nested_math_delimiter")
        depth = 0
        for index, char in enumerate(text):
            if index and text[index - 1] == "\\":
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth < 0:
                    warnings.append("unbalanced_braces")
                    break
        if depth != 0 and "unbalanced_braces" not in warnings:
            warnings.append("unbalanced_braces")

        stack: list[str] = []
        for action, environment in _ENVIRONMENT_RE.findall(text):
            if environment not in ALLOWED_ENVIRONMENTS:
                warnings.append(f"unsupported_environment:{environment}")
            if action == "begin":
                stack.append(environment)
            elif not stack or stack.pop() != environment:
                warnings.append(f"mismatched_environment:{environment}")
        if stack:
            warnings.append(f"unclosed_environment:{stack[-1]}")

        for command in _COMMAND_RE.findall(text):
            name = command[1:]
            if name in DANGEROUS_COMMANDS:
                warnings.append(f"dangerous_command:{name}")
            elif command not in ALLOWED_COMMANDS and name not in ALLOWED_ENVIRONMENTS:
                warnings.append(f"unsupported_command:{name}")
        warnings.extend(self._matrix_warnings(text))
        return list(dict.fromkeys(warnings))

    @staticmethod
    def debug_summary(content: MathRichContent) -> dict[str, Any]:
        invalid = [
            {
                "expression_hash": item.metadata.get("expression_hash", ""),
                "warnings": item.warnings,
            }
            for item in content.math_expressions
            if item.validation_status == "invalid"
        ]
        return {
            "math_expression_count": len(content.math_expressions),
            "normalized_expression_count": sum(
                item.normalized for item in content.math_expressions
            ),
            "math_warnings": content.warnings,
            "latex_validation_failures": invalid,
        }

    def _normalize_math_text(self, source: str) -> tuple[str, list[str]]:
        text = source.strip()
        warnings: list[str] = []
        if not text:
            return text, warnings

        text = self._normalize_unicode_powers(text)
        text = re.sub(
            r"(?<![A-Za-z])d2([A-Za-z])(?:\s*/\s*d|d)([A-Za-z])2(?![A-Za-z0-9])",
            r"\\frac{d^2\1}{d\2^2}",
            text,
        )
        text = re.sub(
            r"(?<![A-Za-z])d([A-Za-z])(?:\s*/\s*d|d)([A-Za-z])(?![A-Za-z0-9])",
            r"\\frac{d\1}{d\2}",
            text,
        )
        text = re.sub(
            r"(?:∂|partial\s+|del)([A-Za-z])\s*/?\s*(?:∂|partial\s+|del)([A-Za-z])",
            r"\\frac{\\partial \1}{\\partial \2}",
            text,
            flags=re.IGNORECASE,
        )
        text = self._normalize_integrals(text)
        text = re.sub(
            r"(?:Σ|\bsum)\s*([A-Za-z])\s*=\s*([^\s^]+)\s*(?:\^|to\s+)([^\s]+)",
            r"\\sum_{\1=\2}^{\3}",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"(?:Π|\bprod)\s*([A-Za-z])\s*=\s*([^\s^]+)\s*(?:\^|to\s+)([^\s]+)",
            r"\\prod_{\1=\2}^{\3}",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\blim(?:_\{)?\s*([A-Za-z])\s*(?:->|to)\s*(?:∞|infinity)(?:\})?",
            r"\\lim_{\1\\to\\infty}",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"sqrt\(([^()]+)\)", r"\\sqrt{\1}", text, flags=re.IGNORECASE)
        text = re.sub(r"√\(([^()]+)\)", r"\\sqrt{\1}", text)
        text = re.sub(r"√([0-9A-Za-z])", r"\\sqrt{\1}", text)
        text = re.sub(r"(?<!\\)e\^?-([A-Za-z0-9]+)", r"e^{-\1}", text)
        text = re.sub(
            r"(\d+(?:\.\d+)?)\s*∠\s*(-?\d+(?:\.\d+)?)\s*°", r"\1\\angle \2^\\circ", text
        )
        text = re.sub(
            r"\bphasor\s+([A-Za-z][A-Za-z0-9_]*)",
            lambda match: PHASOR_STYLES[self.phasor_style].format(
                symbol=match.group(1)
            ),
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\b([sv])1,2\b", r"\1_{1,2}", text)
        text = re.sub(r"\b([xyv])(\d+)(?=\s*\()", r"\1^\2", text)
        text = re.sub(r"(?<![A-Za-z\\])([xy])(\d+)(?=$|[\s+\-*/=,)])", r"\1^\2", text)
        text = re.sub(r"(?<![A-Za-z\\])([viR])(\d+)(?=$|[\s+\-*/=,)])", r"\1_\2", text)
        text = self._replace_symbol_words(text)

        if re.search(
            r"\b(?:alpha|beta|gamma|delta|theta|lambda|mu|omega|phi|pi|tau)\d+\b", text
        ):
            warnings.append("ambiguous_greek_suffix_preserved")
        text = self._normalize_simple_fractions(text)
        return text.strip(), warnings

    def _normalize_integrals(self, text: str) -> str:
        def bounded(match: re.Match[str]) -> str:
            integrand = match.group(1).strip()
            variable = match.group(2)
            return rf"\int_0^\infty {integrand}\,d{variable}"

        text = re.sub(
            r"∫\s*0\s*(?:∞|infinity)\s*(.+?)\s*d([A-Za-zτ])(?=$|[\s,.;，。；])",
            bounded,
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\bint_?0\^?(?:infty|infinity)\s*(.+?)\s*d([A-Za-zτ])(?=$|[\s,.;，。；])",
            bounded,
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"∫\s*(.+?)\s*d([A-Za-zτ])(?=$|[\s,.;，。；])",
            lambda match: rf"\int {match.group(1).strip()}\,d{match.group(2)}",
            text,
        )
        return text

    @staticmethod
    def _normalize_unicode_powers(text: str) -> str:
        pattern = re.compile(r"([A-Za-z0-9})])([⁰¹²³⁴⁵⁶⁷⁸⁹]+)")
        return pattern.sub(
            lambda match: (
                f"{match.group(1)}^{match.group(2).translate(_UNICODE_SUPERSCRIPTS)}"
            ),
            text,
        )

    @staticmethod
    def _normalize_simple_fractions(text: str) -> str:
        if "\\frac" in text:
            return text
        whole = re.fullmatch(r"\(([^()]+)\)/([A-Za-z][A-Za-z0-9_]*)", text)
        if whole:
            numerator = re.sub(r"\b([viR])(\d+)\b", r"\1_\2", whole.group(1))
            return rf"\frac{{{numerator}}}{{{whole.group(2)}}}"
        whole = re.fullmatch(r"([^/\s]+)/\(([^()]+)\)", text)
        if whole:
            return rf"\frac{{{whole.group(1)}}}{{{whole.group(2)}}}"
        return re.sub(
            r"(?<![\w/])([A-Za-z0-9]+)\s*/\s*([A-Za-z0-9]+)(?![/\w])",
            r"\\frac{\1}{\2}",
            text,
        )

    @staticmethod
    def _replace_symbol_words(text: str) -> str:
        for source, target in sorted(
            SYMBOLS.items(), key=lambda item: len(item[0]), reverse=True
        ):
            def substitute(_match: re.Match[str], value: str = target) -> str:
                return value

            text = re.sub(
                rf"(?<![A-Za-z\\]){re.escape(source)}(?![A-Za-z0-9])",
                substitute,
                text,
            )
        return text

    def _process_inline_line(self, line: str) -> _ProcessedChunk:
        chunks: list[_ProcessedChunk] = []
        index = 0
        plain_start = 0
        while index < len(line):
            marker = self._next_inline_marker(line, index)
            if marker is None:
                chunks.append(self._process_plain_text(line[plain_start:]))
                break
            marker_index, opener, closer, segment_type = marker
            if marker_index > plain_start:
                chunks.append(self._process_plain_text(line[plain_start:marker_index]))
            end = self._find_unescaped(line, closer, marker_index + len(opener))
            if end < 0:
                chunks.append(self._process_plain_text(line[marker_index:]))
                break
            raw = line[marker_index + len(opener) : end]
            if segment_type in {MathSegmentType.CODE, MathSegmentType.HTML}:
                chunks.append(
                    self._protected_chunk(
                        line[marker_index : end + len(closer)], segment_type
                    )
                )
            elif opener == "$" and self._looks_like_currency_span(raw):
                chunks.append(
                    self._protected_chunk(
                        line[marker_index : end + len(closer)],
                        MathSegmentType.TEXT,
                    )
                )
            else:
                display = segment_type is MathSegmentType.DISPLAY_MATH
                expression = self.normalize_latex(
                    raw,
                    block_type=MathBlockType.DISPLAY
                    if display
                    else MathBlockType.INLINE,
                )
                rendered = (
                    f"$$\n{expression.latex}\n$$"
                    if display
                    else f"${expression.latex}$"
                )
                chunks.append(self._math_chunk(rendered, expression, display=display))
            index = end + len(closer)
            plain_start = index
        if not chunks:
            return self._process_plain_text(line)
        return self._combine_chunks(chunks)

    def _process_plain_text(self, text: str) -> _ProcessedChunk:
        if not text or _PROTECTED_TEXT_RE.search(text) or self._looks_like_json(text):
            return self._protected_chunk(text, MathSegmentType.TEXT)
        stripped = text.strip()
        if (
            stripped
            and _HIGH_CONFIDENCE_TOKEN_RE.search(stripped)
            and self._looks_like_formula(stripped)
        ):
            expression = self.normalize_latex(stripped, block_type=MathBlockType.INLINE)
            if expression.validation_status != "invalid":
                leading = text[: len(text) - len(text.lstrip())]
                trailing = text[len(text.rstrip()) :]
                math = self._math_chunk(
                    f"${expression.latex}$", expression, display=False
                )
                return self._combine_chunks(
                    [
                        self._protected_chunk(leading, MathSegmentType.TEXT),
                        math,
                        self._protected_chunk(trailing, MathSegmentType.TEXT),
                    ]
                )
        matches = list(_INLINE_HIGH_CONFIDENCE_RE.finditer(text))
        if not matches:
            warnings = (
                ["ambiguous_math_pattern_preserved"]
                if re.search(r"\b(?:alpha|beta|omega)\d+\b", text)
                else []
            )
            chunk = self._protected_chunk(text, MathSegmentType.TEXT)
            chunk.warnings.extend(warnings)
            return chunk
        chunks: list[_ProcessedChunk] = []
        cursor = 0
        for match in matches:
            chunks.append(
                self._protected_chunk(
                    text[cursor : match.start()], MathSegmentType.TEXT
                )
            )
            expression = self.normalize_latex(
                match.group(0), block_type=MathBlockType.INLINE
            )
            chunks.append(
                self._math_chunk(f"${expression.latex}$", expression, display=False)
            )
            cursor = match.end()
        chunks.append(self._protected_chunk(text[cursor:], MathSegmentType.TEXT))
        return self._combine_chunks(chunks)

    @staticmethod
    def _next_inline_marker(
        text: str, start: int
    ) -> tuple[int, str, str, MathSegmentType] | None:
        candidates: list[tuple[int, str, str, MathSegmentType]] = []
        for opener, closer, kind in (
            ("`", "`", MathSegmentType.CODE),
            ("\\(", "\\)", MathSegmentType.INLINE_MATH),
            ("$$", "$$", MathSegmentType.DISPLAY_MATH),
            ("$", "$", MathSegmentType.INLINE_MATH),
            ("<", ">", MathSegmentType.HTML),
        ):
            found = MathFormattingService._find_unescaped(text, opener, start)
            if found >= 0 and (opener != "$" or not text.startswith("$$", found)):
                candidates.append((found, opener, closer, kind))
        return min(candidates, key=lambda item: item[0]) if candidates else None

    @staticmethod
    def _looks_like_currency_span(source: str) -> bool:
        text = source.strip()
        if re.fullmatch(r"\d+(?:\.\d{1,2})?", text):
            return True
        return bool(
            re.match(r"\d", text)
            and re.search(r"[A-Za-z一-鿿]", text)
            and not re.search(r"[=+\-*/^_\\]", text)
        )

    @staticmethod
    def _find_unescaped(text: str, delimiter: str, start: int) -> int:
        index = start
        while True:
            found = text.find(delimiter, index)
            if found < 0:
                return -1
            slashes = 0
            cursor = found - 1
            while cursor >= 0 and text[cursor] == "\\":
                slashes += 1
                cursor -= 1
            if slashes % 2 == 0:
                return found
            index = found + len(delimiter)

    def _consume_display_block(
        self, lines: list[str], start: int
    ) -> tuple[int, str, bool] | None:
        stripped = lines[start].strip()
        opener = (
            "$$"
            if stripped.startswith("$$")
            else "\\["
            if stripped.startswith("\\[")
            else ""
        )
        if not opener:
            return None
        closer = "$$" if opener == "$$" else "\\]"
        first = stripped[len(opener) :]
        if closer in first:
            return 1, first.split(closer, 1)[0], lines[start].endswith("\n")
        body = [first] if first else []
        index = start + 1
        while index < len(lines):
            current = lines[index]
            if closer in current:
                before = current.split(closer, 1)[0]
                if before:
                    body.append(before.rstrip("\n"))
                return index - start + 1, "\n".join(body), current.endswith("\n")
            body.append(current.rstrip("\n"))
            index += 1
        return None

    @staticmethod
    def _strip_math_delimiters(source: str) -> tuple[str, MathBlockType | None]:
        pairs = (
            ("$$", "$$", MathBlockType.DISPLAY),
            ("\\[", "\\]", MathBlockType.DISPLAY),
            ("$", "$", MathBlockType.INLINE),
            ("\\(", "\\)", MathBlockType.INLINE),
        )
        for opener, closer, block_type in pairs:
            if (
                source.startswith(opener)
                and source.endswith(closer)
                and len(source) >= len(opener) + len(closer)
            ):
                return source[len(opener) : -len(closer)].strip(), block_type
        return source, None

    @staticmethod
    def _classify_block_type(
        latex: str, inferred: MathBlockType | None
    ) -> MathBlockType:
        if re.search(
            r"\\begin\{(?:matrix|pmatrix|bmatrix|vmatrix|Vmatrix|smallmatrix)\}", latex
        ):
            return MathBlockType.MATRIX
        if "\\begin{cases}" in latex:
            return MathBlockType.CASES
        if re.search(r"\\begin\{aligned(?:at)?\}", latex):
            return MathBlockType.ALIGNED
        return inferred or MathBlockType.INLINE

    @staticmethod
    def _variables(latex: str) -> list[str]:
        without_commands = _COMMAND_RE.sub("", latex)
        return list(
            dict.fromkeys(
                re.findall(r"(?<![A-Za-z])[A-Za-z](?![A-Za-z])", without_commands)
            )
        )[:32]

    @staticmethod
    def _matrix_warnings(latex: str) -> list[str]:
        warnings: list[str] = []
        for environment in _MATRIX_ENVIRONMENTS:
            pattern = re.compile(
                rf"\\begin\{{{environment}\}}(.*?)\\end\{{{environment}\}}", re.DOTALL
            )
            for match in pattern.finditer(latex):
                rows = [
                    row.strip()
                    for row in re.split(r"\\\\", match.group(1))
                    if row.strip()
                ]
                widths = {row.count("&") + 1 for row in rows}
                if len(widths) > 1:
                    warnings.append("matrix_column_count_mismatch")
        return warnings

    @staticmethod
    def _looks_like_formula(text: str) -> bool:
        if _PROTECTED_TEXT_RE.search(text) or re.search(r"[一-鿿]", text):
            return False
        return bool(_HIGH_CONFIDENCE_TOKEN_RE.search(text)) and len(text) <= 2000

    @staticmethod
    def _looks_like_json(text: str) -> bool:
        stripped = text.strip()
        return (stripped.startswith("{") and ":" in stripped) or (
            stripped.startswith("[") and '"' in stripped
        )

    @staticmethod
    def _is_markdown_table_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped or "|" not in stripped:
            return False
        return stripped.startswith("|") or bool(re.fullmatch(r"[:|\-\s]+", stripped))

    @staticmethod
    def _answer_markdown(structured_result: Mapping[str, Any]) -> str:
        for key in ("answer_text", "answer", "final_answer"):
            value = structured_result.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return ""

    def _structured_formula_candidates(
        self, result: Mapping[str, Any]
    ) -> Iterable[object]:
        yield from self._iter_formula_value(result.get("key_equations"))
        for item in self._as_mapping_items(result.get("intermediate_results")):
            for key in ("equation", "formula", "value", "matrix"):
                yield from self._iter_formula_value(item.get(key))
        for item in self._as_mapping_items(result.get("solution_steps")):
            for key in ("equations", "equation", "formula", "matrix"):
                yield from self._iter_formula_value(item.get(key))
        final = result.get("final_answer")
        if isinstance(final, Mapping):
            for key in ("equation", "formula", "value", "matrix"):
                yield from self._iter_formula_value(final.get(key))

    @staticmethod
    def _iter_formula_value(value: object) -> Iterable[object]:
        if isinstance(value, str):
            yield value
        elif MathFormattingService._is_matrix(value):
            yield value
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for item in value:
                if isinstance(item, str) or MathFormattingService._is_matrix(item):
                    yield item

    @staticmethod
    def _as_mapping_items(value: object) -> list[Mapping[str, Any]]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return []
        return [item for item in value if isinstance(item, Mapping)]

    @staticmethod
    def _is_matrix(value: object) -> TypeGuard[Sequence[Sequence[object]]]:
        return bool(
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes))
            and value
            and all(
                isinstance(row, Sequence) and not isinstance(row, (str, bytes))
                for row in value
            )
        )

    @staticmethod
    def _protected_chunk(text: str, segment_type: MathSegmentType) -> _ProcessedChunk:
        return _ProcessedChunk(
            markdown=text,
            plain_text=text,
            segments=[RichTextSegment(segment_type=segment_type, text=text)]
            if text
            else [],
            expressions=[],
            warnings=[],
        )

    @staticmethod
    def _math_chunk(
        markdown: str, expression: MathExpression, *, display: bool
    ) -> _ProcessedChunk:
        return _ProcessedChunk(
            markdown=markdown,
            plain_text=expression.latex,
            segments=[
                RichTextSegment(
                    segment_type=MathSegmentType.DISPLAY_MATH
                    if display
                    else MathSegmentType.INLINE_MATH,
                    math=expression,
                )
            ],
            expressions=[expression],
            warnings=list(expression.warnings),
        )

    @staticmethod
    def _combine_chunks(chunks: Sequence[_ProcessedChunk]) -> _ProcessedChunk:
        return _ProcessedChunk(
            markdown="".join(item.markdown for item in chunks),
            plain_text="".join(item.plain_text for item in chunks),
            segments=[segment for item in chunks for segment in item.segments],
            expressions=[
                expression for item in chunks for expression in item.expressions
            ],
            warnings=[warning for item in chunks for warning in item.warnings],
        )
