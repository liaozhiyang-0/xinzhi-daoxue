"""Run structural math checks and a bounded real KaTeX compatibility sample."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from audit_math_corpus import (  # type: ignore[import-not-found]
    _formula_tokens,
    _iter_sources,
    inspect_formula,
)


def _collect(source_root: Path) -> list[dict[str, object]]:
    formulas: list[dict[str, object]] = []
    for course, path in _iter_sources(source_root):
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(source_root).as_posix()
        tokens, _ = _formula_tokens(text)
        for start, delimiter, body in tokens:
            formula = inspect_formula(
                course,
                relative,
                text.count("\n", 0, start) + 1,
                delimiter,
                body,
            )
            item = formula.as_dict()
            item["body"] = formula.body
            formulas.append(item)
    return formulas


def _select(formulas: list[dict[str, object]]) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    seen_course_risk: Counter[tuple[str, str]] = Counter()
    seen_env: Counter[tuple[str, str]] = Counter()
    for item in formulas:
        risk = str(item["risk"])
        course = str(item["course"])
        environment = str(item["environment"] or "none")
        should_select = risk == "HIGH"
        if environment in {"array", "matrix", "pmatrix", "bmatrix", "aligned", "cases"}:
            should_select = should_select or seen_env[(course, environment)] < 20
        if seen_course_risk[(course, risk)] < 3:
            should_select = True
        length = item.get("length")
        if isinstance(length, (int, float)) and length > 1200:
            should_select = True
        if should_select:
            selected.append(item)
            seen_course_risk[(course, risk)] += 1
            seen_env[(course, environment)] += 1
    return selected


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
        encoding="utf-8",
        newline="\n",
    )


def run(source_root: Path, output_root: Path) -> dict[str, object]:
    formulas = _collect(source_root)
    selected = _select(formulas)
    node = shutil.which("node")
    katex_path = (
        output_root
        / "apps"
        / "api"
        / "app"
        / "static"
        / "debug"
        / "vendor"
        / "katex"
        / "katex.min.js"
    )
    failures: list[dict[str, object]] = []
    runtime_status = "available"
    version = "unknown"
    if not node or not katex_path.is_file():
        runtime_status = "KATEX_RUNTIME_NOT_AVAILABLE"
        version = "unknown"
    else:
        with tempfile.TemporaryDirectory(prefix="xzd-katex-") as temp_dir:
            input_path = Path(temp_dir) / "input.jsonl"
            result_path = Path(temp_dir) / "result.jsonl"
            _write_jsonl(input_path, selected)
            command = [
                node,
                str(output_root / "scripts" / "render_katex_samples.js"),
                str(input_path),
                str(result_path),
            ]
            completed = subprocess.run(
                command,
                cwd=output_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if completed.returncode != 0:
                runtime_status = "KATEX_RUNTIME_FAILED"
                failures = [
                    {
                        "status": "failed",
                        "error": completed.stderr.strip() or "node_render_failed",
                    }
                ]
            elif result_path.is_file():
                by_hash = {str(item["hash"]): item for item in selected}
                for line in result_path.read_text(encoding="utf-8").splitlines():
                    result = json.loads(line)
                    version = str(result.get("version", version))
                    if result.get("status") == "failed":
                        source = by_hash.get(str(result.get("formula_hash")), {})
                        failures.append(
                            {**source, "render_error": result.get("error", "unknown")}
                        )
    failure_path = output_root / "evaluation" / "math" / "katex_render_failures.jsonl"
    _write_jsonl(failure_path, failures)
    risk_counts = Counter(str(item["risk"]) for item in selected)
    report = "\n".join(
        [
            "# KaTeX compatibility report",
            "",
            f"- runtime: `{runtime_status}`",
            f"- version: `{version}`",
            f"- structural corpus formulas: `{len(formulas)}`",
            f"- selected formulas rendered: `{len(selected)}`",
            f"- render failures: `{len(failures)}`",
            f"- selected risk strata: `{dict(sorted(risk_counts.items()))}`",
            "",
            "The source Markdown was read-only. Real rendering used the "
            "repository's existing local KaTeX runtime when present; no npm "
            "package or lockfile was changed. Failures are retained as JSONL "
            "for targeted review and never remove raw LaTeX.",
            "",
        ]
    )
    report_path = output_root / "docs" / "math" / "katex_compatibility_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8", newline="\n")
    return {
        "runtime": runtime_status,
        "version": version,
        "formula_count": len(formulas),
        "selected_count": len(selected),
        "failure_count": len(failures),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(
        json.dumps(
            run(args.source_root.resolve(), args.output_root.resolve()),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
