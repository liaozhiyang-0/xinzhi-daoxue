"""Generate the deterministic, provider-free T5 benchmark catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import struct
import zlib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "evaluation" / "cases" / "expanded_benchmark_v2"

COURSE_SPECS: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    (
        "CT",
        120,
        (
            "kcl_kvl",
            "node_voltage",
            "mesh_current",
            "superposition",
            "thevenin_norton",
            "first_order",
            "second_order",
            "sinusoidal_steady_state",
            "power",
            "controlled_source",
            "mutual_inductance",
            "two_port",
            "frequency_response",
        ),
    ),
    (
        "AE",
        100,
        (
            "diode_circuit",
            "bjt_bias",
            "mos_bias",
            "small_signal_amplifier",
            "dc_bias",
            "bjt_small_signal",
            "mos_small_signal",
            "feedback",
            "frequency_response",
            "op_amp",
            "waveform_circuit",
            "power_amplifier",
            "waveform_generation",
            "comparator",
            "regulated_power_supply",
        ),
    ),
    (
        "DE",
        100,
        (
            "number_encoding",
            "logic_simplification",
            "combinational_logic",
            "sequential_logic",
            "flip_flop",
            "counter",
            "state_machine",
            "verilog_analysis",
        ),
    ),
    (
        "SS",
        80,
        (
            "continuous_signal",
            "discrete_signal",
            "system_properties",
            "convolution",
            "fourier_transform",
            "laplace_transform",
            "z_transform",
            "frequency_domain",
        ),
    ),
    (
        "DSP",
        60,
        (
            "dft_fft",
            "digital_filter",
            "spectrum_analysis",
            "sampling",
        ),
    ),
    (
        "COMM",
        40,
        (
            "modulation",
            "noise",
            "detection",
            "coding",
        ),
    ),
)

DIFFICULTIES = ("easy", "medium", "hard", "boundary")
DIFFICULTY_COUNTS = {"easy": 100, "medium": 175, "hard": 150, "boundary": 75}


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _write_diagram(path: Path, index: int) -> None:
    """Write a small deterministic circuit/block diagram using only stdlib."""

    width, height = 320, 180
    pixels = bytearray([255] * width * height * 3)

    def pixel(x: int, y: int, color: tuple[int, int, int] = (25, 45, 75)) -> None:
        if 0 <= x < width and 0 <= y < height:
            offset = (y * width + x) * 3
            pixels[offset : offset + 3] = bytes(color)

    def line(x1: int, y1: int, x2: int, y2: int) -> None:
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        sx, sy = (1 if x1 < x2 else -1), (1 if y1 < y2 else -1)
        error = dx - dy
        while True:
            pixel(x1, y1)
            if x1 == x2 and y1 == y2:
                break
            twice = 2 * error
            if twice > -dy:
                error -= dy
                x1 += sx
            if twice < dx:
                error += dx
                y1 += sy

    def rectangle(x1: int, y1: int, x2: int, y2: int) -> None:
        line(x1, y1, x2, y1)
        line(x2, y1, x2, y2)
        line(x2, y2, x1, y2)
        line(x1, y2, x1, y1)

    shift = (index % 4) * 8
    line(20, 90, 70, 90)
    rectangle(70, 55 + shift // 2, 130, 125 + shift // 2)
    line(130, 90 + shift // 2, 190, 90 + shift // 2)
    line(190, 90 + shift // 2, 240, 45)
    line(190, 90 + shift // 2, 240, 135)
    line(240, 45, 290, 45)
    line(240, 135, 290, 135)
    line(290, 45, 290, 135)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = b"".join(
        b"\x00" + bytes(pixels[row * width * 3 : (row + 1) * width * 3])
        for row in range(height)
    )
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw, level=9))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def _difficulty_sequence(total: int) -> list[str]:
    values = [item for item, count in DIFFICULTY_COUNTS.items() for _ in range(count)]
    if len(values) != total:
        raise ValueError(f"difficulty counts sum to {len(values)}, expected {total}")
    random.Random(20260823).shuffle(values)
    return values


def _base_case(
    *,
    case_id: str,
    course: str,
    problem_type: str,
    difficulty: str,
    message: str,
    structured_input: dict[str, Any],
    expected_statuses: list[str],
    expected_paths: list[str],
    tags: list[str],
    visual_index: int | None,
    output_root: Path,
    reference_values: dict[str, int | float | str] | None = None,
    expected_tools: list[str] | None = None,
) -> dict[str, Any]:
    input_type = "mixed" if visual_index is not None else "text"
    file_refs: list[dict[str, str]] = []
    if visual_index is not None:
        relative = f"attachments/diagram_{visual_index % 8:02d}.png"
        file_refs = [{"path": relative}]
    case: dict[str, Any] = {
        "case_id": case_id,
        "title": f"T5 {course} {problem_type} {case_id[-3:]}",
        "course": course,
        "task_family": "ACADEMIC_SOLVING",
        "intent": "solve_problem",
        "problem_type": problem_type,
        "difficulty": difficulty,
        "input_type": input_type,
        "message": message,
        "file_refs": file_refs,
        "structured_input": structured_input,
        "expected_agent": "ACADEMIC_PROBLEM_SOLVER",
        "expected_course_pack": course,
        "expected_execution_paths": expected_paths,
        "expected_statuses": expected_statuses,
        "tags": ["expanded_v2", "synthetic", *tags],
        "source": "t5_expanded_benchmark_v2_template",
        "input_source": "synthetic",
        "notes": (
            "Deterministic generated case; no real student data or "
            "paid provider evidence."
        ),
        "provenance": {
            "source_type": "synthetic",
            "source_name": "t5_expanded_benchmark_v2_template",
            "license_or_authorization": "repository-generated synthetic data",
            "publishable": True,
        },
    }
    if reference_values:
        case["reference_values"] = reference_values
        case["numeric_tolerance"] = 0.000001
    if expected_tools:
        case["expected_tools"] = expected_tools
    if visual_index is not None:
        case["tags"].extend(("visual_fixture", "not_official"))
    return case


def _numeric_case(
    *,
    course: str,
    index: int,
    problem_type: str,
    difficulty: str,
    global_index: int,
    output_root: Path,
    visual_index: int | None,
) -> dict[str, Any]:
    coefficient = 2 + (index % 7)
    value = 2 + (index % 11)
    rhs = coefficient * value
    problem_text = (
        f"在{course}的{problem_type}题中，根据题目条件列出方程并求x。"
        f"图示或文字条件给出 {coefficient}*x={rhs}。"
    )
    visual_boundary = visual_index is not None
    expected_tool = None
    if visual_index is None:
        if course in {"CT", "AE", "SS"}:
            expected_tool = "linear_equation_solver"
        elif course == "DE" and problem_type == "number_encoding":
            expected_tool = "sympy_solver"
    reference_key = (
        "value" if course == "DE" and problem_type == "number_encoding" else "x"
    )
    return _base_case(
        case_id=f"T5_{course}_{global_index:03d}",
        course=course,
        problem_type=problem_type,
        difficulty=difficulty,
        message=problem_text,
        structured_input={
            "problem_type": problem_type,
            "equations_given": [f"{coefficient}*x={rhs}"],
            "target_quantities": [{"name": "x"}],
            "extraction_confidence": 0.96,
            "can_continue": True,
        },
        expected_statuses=["success", "partial"] if visual_boundary else ["success"],
        expected_paths=[] if visual_boundary else ["FAST", "STANDARD"],
        tags=[
            "numeric",
            "coverage",
            problem_type,
            *(["visual_boundary"] if visual_boundary else []),
        ],
        visual_index=visual_index,
        output_root=output_root,
        reference_values=(None if visual_boundary else {reference_key: value}),
        expected_tools=[expected_tool] if expected_tool else None,
    )


def _boundary_case(
    *,
    course: str,
    index: int,
    problem_type: str,
    difficulty: str,
    global_index: int,
    output_root: Path,
    visual_index: int | None,
) -> dict[str, Any]:
    return _base_case(
        case_id=f"T5_{course}_{global_index:03d}",
        course=course,
        problem_type=problem_type,
        difficulty=difficulty,
        message=f"{course} {problem_type}题缺少决定性参数，请先判断是否能够继续。",
        structured_input={
            "problem_type": problem_type,
            "critical_missing_info": [{"field": "关键参数"}],
            "extraction_confidence": 0.9,
            "can_continue": False,
        },
        expected_statuses=["partial"],
        expected_paths=["CONDITIONAL"],
        tags=["boundary", "insufficient", "coverage", problem_type],
        visual_index=visual_index,
        output_root=output_root,
    )


def _unsupported_course_case(
    *,
    course: str,
    index: int,
    problem_type: str,
    difficulty: str,
    global_index: int,
    output_root: Path,
    visual_index: int | None,
) -> dict[str, Any]:
    return _base_case(
        case_id=f"T5_{course}_{global_index:03d}",
        course=course,
        problem_type=problem_type,
        difficulty=difficulty,
        message=f"请分析{course}课程中的{problem_type}问题，并明确当前课程包的能力边界。",
        structured_input={
            "problem_type": problem_type,
            "extraction_confidence": 0.95,
            "can_continue": True,
        },
        expected_statuses=["partial"],
        expected_paths=["CONDITIONAL"],
        tags=["skeleton_course", "safe_fallback", "coverage", problem_type],
        visual_index=visual_index,
        output_root=output_root,
    )


def build_cases(output_root: Path) -> list[dict[str, Any]]:
    total = sum(count for _, count, _ in COURSE_SPECS)
    difficulties = _difficulty_sequence(total)
    cases: list[dict[str, Any]] = []
    global_index = 0
    visual_index = 0
    for course, count, problem_types in COURSE_SPECS:
        for index in range(count):
            difficulty = difficulties[global_index]
            visual = global_index % 20 == 0
            current_visual = visual_index if visual else None
            if visual:
                visual_index += 1
            problem_type = problem_types[index % len(problem_types)]
            if difficulty == "boundary":
                case = _boundary_case(
                    course=course,
                    index=index,
                    problem_type=problem_type,
                    difficulty=difficulty,
                    global_index=global_index,
                    output_root=output_root,
                    visual_index=current_visual,
                )
            elif course in {"DSP", "COMM"}:
                case = _unsupported_course_case(
                    course=course,
                    index=index,
                    problem_type=problem_type,
                    difficulty=difficulty,
                    global_index=global_index,
                    output_root=output_root,
                    visual_index=current_visual,
                )
            elif (
                course == "DE"
                and problem_type
                in {
                    "logic_simplification",
                    "combinational_logic",
                    "sequential_logic",
                }
                and index % 7 == 0
            ):
                disabled_tool = (
                    "boolean_simplifier"
                    if problem_type == "logic_simplification"
                    else "truth_table_generator"
                )
                case = _base_case(
                    case_id=f"T5_{course}_{global_index:03d}",
                    course=course,
                    problem_type=problem_type,
                    difficulty=difficulty,
                    message=f"分析数字电子中的{problem_type}问题，并保留工具能力边界。",
                    structured_input={
                        "problem_type": problem_type,
                        "extraction_confidence": 0.95,
                        "can_continue": True,
                    },
                    expected_statuses=["partial"],
                    expected_paths=["FAST", "STANDARD"],
                    tags=["disabled_tool_boundary", "coverage", problem_type],
                    visual_index=current_visual,
                    output_root=output_root,
                    expected_tools=[disabled_tool],
                )
            else:
                case = _numeric_case(
                    course=course,
                    index=index,
                    problem_type=problem_type,
                    difficulty=difficulty,
                    global_index=global_index,
                    output_root=output_root,
                    visual_index=current_visual,
                )
            if global_index % 2 == 0:
                case["tags"].append("t5_representative_execution")
            if course == "DE" and problem_type == "number_encoding":
                case["tags"].append("t5_number_encoding_replay")
            cases.append(case)
            global_index += 1

    for index in range(8):
        _write_diagram(output_root / "attachments" / f"diagram_{index:02d}.png", index)
    return cases


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_root = args.output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    cases = build_cases(output_root)
    payload = {"cases": cases}
    catalog_path = output_root / "expanded.yaml"
    catalog_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    digest = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    summary = {
        "benchmark_id": "BENCHMARK_T5_EXPANDED_V2",
        "case_count": len(cases),
        "catalog_sha256": digest,
        "seed": 20260823,
        "course_counts": {
            course: sum(1 for case in cases if case["course"] == course)
            for course, _, _ in COURSE_SPECS
        },
        "difficulty_counts": {
            difficulty: sum(1 for case in cases if case["difficulty"] == difficulty)
            for difficulty in DIFFICULTIES
        },
        "input_type_counts": {
            input_type: sum(1 for case in cases if case["input_type"] == input_type)
            for input_type in ("text", "mixed")
        },
        "representative_execution_count": sum(
            "t5_representative_execution" in case["tags"] for case in cases
        ),
        "attachment_count": sum(len(case["file_refs"]) for case in cases),
        "generator": "scripts/generate_expanded_benchmark_v2.py",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"catalog={catalog_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
