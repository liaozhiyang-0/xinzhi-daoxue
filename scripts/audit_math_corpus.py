"""Audit course Markdown formulas without changing the source corpus.

The scanner deliberately tokenizes fenced and inline code before looking for
math delimiters.  It is intended for repeatable compatibility reports, not as
a Markdown renderer.  Source roots can live outside the checkout (the real
course material is local-only), while all generated reports are written to the
selected output root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

COURSES: dict[str, str] = {
    "CT": "电路理论",
    "AE": "模电",
    "DE": "数电",
    "SS": "信号与系统版本一",
    "DSP": "数字信号处理",
    "COMM": "通信原理",
}
MATH_DELIMITERS: tuple[tuple[str, str, str], ...] = (
    ("\\[", "\\]", "display"),
    ("\\(", "\\)", "inline"),
    ("$$", "$$", "display_dollar"),
    ("$", "$", "inline_dollar"),
)
ENVIRONMENT_RE = re.compile(r"\\(begin|end)\{([^{}]+)\}")
COMMAND_RE = re.compile(r"(?<!\\)\\([A-Za-z]+)")
ENVIRONMENT_NAMES = frozenset(
    {
        "array",
        "aligned",
        "alignedat",
        "cases",
        "matrix",
        "pmatrix",
        "bmatrix",
        "vmatrix",
        "Vmatrix",
        "smallmatrix",
        "gathered",
        "split",
        "equation",
        "equation*",
    }
)
MEDIUM_ENVIRONMENTS = frozenset(
    {"array", "aligned", "alignedat", "cases", "gathered", "split"}
    | {"matrix", "pmatrix", "bmatrix", "vmatrix", "Vmatrix", "smallmatrix"}
)
MEDIUM_COMMANDS = frozenset({"text", "operatorname", "overset"})
UNSUPPORTED_COMMANDS = frozenset(
    {
        "begin",
        "end",
        "frac",
        "sqrt",
        "sum",
        "prod",
        "int",
        "iint",
        "iiint",
        "lim",
        "infty",
        "partial",
        "nabla",
        "left",
        "right",
        "cdot",
        "times",
        "pm",
        "mp",
        "leq",
        "geq",
        "neq",
        "approx",
        "sim",
        "to",
        "rightarrow",
        "leftarrow",
        "leftrightarrow",
        "Leftrightarrow",
        "in",
        "notin",
        "subset",
        "subseteq",
        "cup",
        "cap",
        "Rightarrow",
        "Leftarrow",
        "implies",
        "iff",
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "varepsilon",
        "theta",
        "lambda",
        "mu",
        "pi",
        "rho",
        "sigma",
        "tau",
        "phi",
        "varphi",
        "omega",
        "Gamma",
        "Delta",
        "Lambda",
        "Sigma",
        "Phi",
        "Omega",
        "mathbb",
        "mathbf",
        "mathrm",
        "mathcal",
        "underline",
        "dot",
        "hat",
        "bar",
        "vec",
        "angle",
        "circ",
        "quad",
        "qquad",
        ",",
        ";",
        ":",
        "!",
        "langle",
        "rangle",
        "text",
        "operatorname",
        "overline",
        "ddot",
        "oint",
        "dfrac",
        "tfrac",
        "ast",
        "le",
        "ge",
        "ne",
        "propto",
        "therefore",
        "because",
        "Pr",
        "det",
        "sin",
        "cos",
        "tan",
        "log",
        "ln",
        "exp",
        "min",
        "max",
        "limits",
        "nolimits",
        "mathop",
        "tag",
        "substack",
        "lbrack",
        "rbrack",
        "cdots",
        "ldots",
        "vdots",
        "ddots",
        "widehat",
        "widetilde",
        "overset",
        "underset",
        "boxed",
        "boldsymbol",
        "prime",
        "equiv",
        "oplus",
        "mid",
        "parallel",
        "perp",
        "triangleq",
        "arctan",
        "arcsin",
        "arccos",
        "sinh",
        "cosh",
        "tanh",
        "cot",
        "sec",
        "csc",
        "lg",
        "arg",
        "eta",
        "nu",
        "xi",
        "Psi",
        "Theta",
    }
)
DANGEROUS_COMMANDS = frozenset(
    {"input", "include", "write18", "openout", "read", "catcode", "def", "newcommand"}
)


@dataclass(slots=True)
class Formula:
    course: str
    file: str
    line: int
    delimiter: str
    body: str
    environments: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    array: bool = False
    matrix: bool = False
    aligned: bool = False
    cases: bool = False
    unsupported_macros: list[str] = field(default_factory=list)
    parse_risk: list[str] = field(default_factory=list)
    risk: str = "LOW"
    formula_hash: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "course": self.course,
            "file": self.file,
            "line": self.line,
            "delimiter": self.delimiter,
            "environment": self.environments[0] if self.environments else None,
            "environments": self.environments,
            "length": len(self.body),
            "commands": self.commands,
            "array": self.array,
            "matrix": self.matrix,
            "aligned": self.aligned,
            "cases": self.cases,
            "unsupported_macro": self.unsupported_macros,
            "parse_risk": self.parse_risk,
            "risk": self.risk,
            "hash": self.formula_hash,
        }


def _is_escaped(text: str, index: int) -> bool:
    slashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        slashes += 1
        cursor -= 1
    return slashes % 2 == 1


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _find_unescaped(text: str, delimiter: str, start: int) -> int:
    index = start
    while True:
        found = text.find(delimiter, index)
        if found < 0:
            return -1
        if not _is_escaped(text, found):
            return found
        index = found + len(delimiter)


def _formula_tokens(
    text: str,
) -> tuple[list[tuple[int, str, str]], list[dict[str, int]]]:
    """Return (start, delimiter, body) tokens and protected-code spans."""

    tokens: list[tuple[int, str, str]] = []
    protected: list[dict[str, int]] = []
    index = 0
    line_start = True
    fence_marker: str | None = None
    while index < len(text):
        if line_start:
            line = text[
                index : text.find("\n", index) if "\n" in text[index:] else len(text)
            ]
            stripped = line.lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                marker = stripped[:3]
                if fence_marker is None:
                    fence_marker = marker
                elif marker == fence_marker:
                    fence_marker = None
                line_end = index + len(line)
                protected.append({"start": index, "end": line_end})
                index = line_end
                line_start = True
                if index < len(text) and text[index] == "\n":
                    index += 1
                continue
        if fence_marker is not None:
            line_end = text.find("\n", index)
            if line_end < 0:
                line_end = len(text)
            protected.append({"start": index, "end": line_end})
            index = line_end
            line_start = True
            if index < len(text) and text[index] == "\n":
                index += 1
            continue
        if text[index] == "`":
            run_end = index + 1
            while run_end < len(text) and text[run_end] == "`":
                run_end += 1
            code_closer = text.find(text[index:run_end], run_end)
            if code_closer >= 0:
                protected.append({"start": index, "end": code_closer + run_end - index})
                index = code_closer + run_end - index
                line_start = False
                continue
        found: tuple[int, str, str] | None = None
        for opener, math_closer, name in MATH_DELIMITERS:
            if text.startswith(opener, index) and not _is_escaped(text, index):
                end = _find_unescaped(text, math_closer, index + len(opener))
                if end >= 0:
                    found = (end, name, text[index + len(opener) : end])
                    break
        if found is not None:
            end, delimiter, body = found
            tokens.append((index, delimiter, body))
            index = end + (2 if delimiter in {"display", "display_dollar"} else 1)
            line_start = False
            continue
        line_start = text[index] == "\n"
        index += 1
    return tokens, protected


def _balanced_braces(text: str) -> bool:
    depth = 0
    for index, char in enumerate(text):
        if _is_escaped(text, index):
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _environment_info(text: str) -> tuple[list[str], list[str]]:
    environments: list[str] = []
    stack: list[str] = []
    risks: list[str] = []
    for action, name in ENVIRONMENT_RE.findall(text):
        if action == "begin":
            environments.append(name)
            stack.append(name)
        elif not stack or stack.pop() != name:
            risks.append(f"mismatched_environment:{name}")
    if stack:
        risks.append(f"unclosed_environment:{stack[-1]}")
    return list(dict.fromkeys(environments)), risks


def _classify(formula: Formula) -> None:
    if not _balanced_braces(formula.body):
        formula.parse_risk.append("malformed_braces")
    if formula.environments and formula.parse_risk:
        formula.parse_risk.append("nested_environment_risk")
    if any(command in DANGEROUS_COMMANDS for command in formula.commands):
        formula.parse_risk.append("dangerous_command")
    formula.parse_risk.extend(_environment_info(formula.body)[1])
    formula.parse_risk = list(dict.fromkeys(formula.parse_risk))
    if formula.unsupported_macros or any(
        item.startswith(("malformed", "mismatched", "unclosed", "dangerous"))
        for item in formula.parse_risk
    ):
        formula.risk = "HIGH"
    elif formula.environments or any(
        command in MEDIUM_COMMANDS for command in formula.commands
    ):
        formula.risk = "MEDIUM"
    else:
        formula.risk = "LOW"


def inspect_formula(
    course: str, relative_file: str, line: int, delimiter: str, body: str
) -> Formula:
    environments, environment_risks = _environment_info(body)
    commands = list(dict.fromkeys(COMMAND_RE.findall(body)))
    unsupported = [
        command
        for command in commands
        if command not in UNSUPPORTED_COMMANDS and command not in ENVIRONMENT_NAMES
    ]
    formula = Formula(
        course=course,
        file=relative_file,
        line=line,
        delimiter=delimiter,
        body=body,
        environments=environments,
        commands=commands,
        array="array" in environments,
        matrix=any(
            name in environments for name in MEDIUM_ENVIRONMENTS if "matrix" in name
        ),
        aligned=any(name.startswith("aligned") for name in environments),
        cases="cases" in environments,
        unsupported_macros=unsupported,
        parse_risk=environment_risks,
        formula_hash=hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
    )
    _classify(formula)
    return formula


def _iter_sources(source_root: Path) -> Iterable[tuple[str, Path]]:
    for course, folder in COURSES.items():
        root = source_root / folder
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            yield course, path


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _report(
    inventory: dict[str, Any], formulas: list[Formula], source_root: Path
) -> str:
    counts = inventory["formula_counts"]
    risk_counts = inventory["risk_counts"]
    lines = [
        "# Math corpus audit",
        "",
        f"- source root: `{source_root}`",
        f"- Markdown files: `{inventory['markdown_count']}`",
        f"- formula instances: `{inventory['formula_count']}`",
        "- protected fenced/inline code spans: "
        f"`{inventory['protected_code_span_count']}`",
        f"- manifest rows observed: `{inventory['manifest_row_count']}`",
        "",
        "## Formula counts",
        "",
        "| delimiter | count |",
        "| --- | ---: |",
    ]
    for key, value in sorted(counts.items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(["", "## Risk counts", "", "| risk | count |", "| --- | ---: |"])
    for key, value in sorted(risk_counts.items()):
        lines.append(f"| `{key}` | {value} |")
    lines.extend(
        [
            "",
            "## Per-course counts",
            "",
            "| course | Markdown | formulas | HIGH | MEDIUM | LOW |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    per_course: dict[str, Counter[str]] = defaultdict(Counter)
    for formula in formulas:
        per_course[formula.course][formula.risk] += 1
        per_course[formula.course]["formulas"] += 1
    for course in COURSES:
        markdown_count = int(inventory["course_markdown_counts"].get(course, 0))
        counts_for_course = per_course[course]
        lines.append(
            f"| `{course}` | {markdown_count} | {counts_for_course['formulas']} | "
            f"{counts_for_course['HIGH']} | {counts_for_course['MEDIUM']} | "
            f"{counts_for_course['LOW']} |"
        )
    lines.extend(
        [
            "",
            "## Method and boundaries",
            "",
            "The scanner tokenizes fenced code and inline backtick code before math. "
            "It only emits paired delimiters and never rewrites course sources. "
            "A HIGH risk item requires review before an actual KaTeX render claim; "
            "the report is structural and does not invent render results.",
            "",
        ]
    )
    return "\n".join(lines)


def audit(source_root: Path, output_root: Path) -> dict[str, Any]:
    formulas: list[Formula] = []
    source_shas: dict[str, str] = {}
    course_markdown_counts: Counter[str] = Counter()
    protected_code_span_count = 0
    for course, path in _iter_sources(source_root):
        raw = path.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        relative = path.relative_to(source_root).as_posix()
        source_shas[relative] = hashlib.sha256(raw).hexdigest()
        course_markdown_counts[course] += 1
        tokens, protected = _formula_tokens(text)
        protected_code_span_count += len(protected)
        for start, delimiter, body in tokens:
            formulas.append(
                inspect_formula(
                    course, relative, _line_number(text, start), delimiter, body
                )
            )

    delimiter_counts = Counter(item.delimiter for item in formulas)
    risk_counts = Counter(item.risk for item in formulas)
    environments = Counter(
        environment for item in formulas for environment in item.environments
    )
    manifest_path = source_root / "knowledge_indexes" / "knowledge_base_manifest.jsonl"
    manifest_row_count = (
        sum(
            1
            for line in manifest_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
        if manifest_path.is_file()
        else 0
    )
    inventory: dict[str, Any] = {
        "schema_version": "math_corpus_inventory.v1",
        "source_root": str(source_root),
        "markdown_count": sum(course_markdown_counts.values()),
        "formula_count": len(formulas),
        "formula_counts": dict(delimiter_counts),
        "risk_counts": dict(risk_counts),
        "environment_counts": dict(environments),
        "protected_code_span_count": protected_code_span_count,
        "manifest_row_count": manifest_row_count,
        "course_markdown_counts": dict(course_markdown_counts),
        "source_sha256": source_shas,
        "protected_code_formula_count": 0,
    }
    _write_json(
        output_root / "evaluation" / "math" / "math_corpus_inventory.json", inventory
    )
    failures = [item.as_dict() for item in formulas if item.risk == "HIGH"]
    _write_jsonl(
        output_root / "evaluation" / "math" / "math_corpus_failures.jsonl", failures
    )
    sampled: list[dict[str, object]] = []
    seen: Counter[tuple[str, str, str]] = Counter()
    for item in formulas:
        environment = item.environments[0] if item.environments else "none"
        key = (item.course, item.risk, environment)
        if seen[key] < 3:
            sampled.append(item.as_dict())
            seen[key] += 1
    _write_jsonl(
        output_root / "evaluation" / "math" / "math_corpus_samples.jsonl", sampled
    )
    report = _report(inventory, formulas, source_root)
    report_path = output_root / "docs" / "math" / "math_corpus_audit.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8", newline="\n")
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    inventory = audit(args.source_root.resolve(), args.output_root.resolve())
    print(
        json.dumps(
            {
                key: inventory[key]
                for key in (
                    "markdown_count",
                    "formula_count",
                    "formula_counts",
                    "risk_counts",
                    "manifest_row_count",
                )
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
