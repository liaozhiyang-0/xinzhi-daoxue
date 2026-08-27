from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from app.evaluation.contracts import EvaluationCase  # noqa: E402

SOURCE_ROOT = ROOT / "evaluation" / "cases"
OUTPUT_ROOT = ROOT / "evaluation" / "runtime_stability"
MANIFEST_PATH = OUTPUT_ROOT / "manifest.json"
OUTPUT_PATH = OUTPUT_ROOT / "cases.json"


def _load_source_cases() -> list[tuple[Path, dict[str, Any]]]:
    records: list[tuple[Path, dict[str, Any]]] = []
    seen: set[str] = set()
    for path in sorted([*SOURCE_ROOT.rglob("*.yaml"), *SOURCE_ROOT.rglob("*.json")]):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        values = payload.get("cases") if isinstance(payload, dict) else None
        if not isinstance(values, list):
            continue
        for raw in values:
            if not isinstance(raw, dict) or "case_id" not in raw:
                continue
            case = EvaluationCase.model_validate(raw)
            if case.case_id in seen:
                continue
            seen.add(case.case_id)
            records.append((path, case.model_dump(mode="json")))
    return records


def _is_boundary(case: dict[str, Any]) -> bool:
    tags = {str(item).casefold() for item in case.get("tags", [])}
    return case.get("difficulty") == "boundary" or bool(
        tags.intersection({"boundary", "insufficient", "misroute"})
    )


def _is_multimodal(case: dict[str, Any]) -> bool:
    tags = {str(item).casefold() for item in case.get("tags", [])}
    return (
        bool(case.get("file_refs"))
        or case.get("input_type")
        in {
            "mixed",
            "image",
        }
        or "multimodal" in tags
        or "visual_fixture" in tags
    )


def _is_research(case: dict[str, Any]) -> bool:
    agent = str(case.get("expected_agent", ""))
    tags = {str(item).casefold() for item in case.get("tags", [])}
    return (
        agent.startswith("RESEARCH_")
        and agent != "RESEARCH_03_DATA_ANALYSIS_V1"
        or ("research" in tags and case.get("intent") != "data_analysis")
    )


def _is_multi_turn(case: dict[str, Any]) -> bool:
    options = case.get("task_options") or {}
    structured = case.get("structured_input") or {}
    tags = {str(item).casefold() for item in case.get("tags", [])}
    return bool(
        options.get("_evaluation_follow_up_actions")
        or structured.get("turns")
        or "follow_up_resolution" in tags
        or "multi_turn" in tags
    )


def _is_knowledge(case: dict[str, Any]) -> bool:
    return str(case.get("task_family", "")) in {
        "KNOWLEDGE_QA",
        "SUMMARIZE_KNOWLEDGE",
    } and not _is_research(case)


def _is_general(case: dict[str, Any]) -> bool:
    return str(case.get("expected_agent", "")) == "GENERAL_QUESTION_V1" or (
        str(case.get("task_family", "")) == "GENERAL_QA" and not _is_research(case)
    )


def _is_solver(case: dict[str, Any]) -> bool:
    return (
        str(case.get("expected_agent", "")) == "ACADEMIC_PROBLEM_SOLVER"
        and str(case.get("intent", "")) == "solve_problem"
        and not _is_multimodal(case)
        and not _is_boundary(case)
        and str(case.get("course", "")) in {"CT", "AE", "DE", "SS"}
    )


def _normalize_file_refs(case: dict[str, Any]) -> None:
    refs = case.get("file_refs")
    if not isinstance(refs, list):
        return
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        path = str(ref.get("path", ""))
        if path.startswith("attachments/"):
            ref["path"] = f"expanded_benchmark_v2/{path}"


def _take(
    records: list[tuple[Path, dict[str, Any]]],
    predicate: Any,
    count: int,
    used: set[str],
) -> list[dict[str, Any]]:
    candidates = [
        case
        for _path, case in records
        if case["case_id"] not in used and predicate(case)
    ]
    by_course: dict[str, list[dict[str, Any]]] = {}
    for case in candidates:
        by_course.setdefault(str(case.get("course", "")), []).append(case)
    for course_cases in by_course.values():
        course_cases.sort(
            key=lambda item: (
                str(item.get("difficulty", "")),
                str(item["case_id"]),
            )
        )

    selected: list[dict[str, Any]] = []
    courses = sorted(by_course)
    while len(selected) < count:
        progressed = False
        for course in courses:
            if not by_course[course]:
                continue
            selected.append(by_course[course].pop(0))
            progressed = True
            if len(selected) >= count:
                break
        if not progressed:
            break
    used.update(str(item["case_id"]) for item in selected)
    return [copy.deepcopy(item) for item in selected]


def _synthetic_case(
    *,
    case_id: str,
    title: str,
    course: str,
    task_family: str,
    intent: str,
    expected_agent: str,
    message: str,
    difficulty: str = "medium",
    input_type: str = "text",
    task_options: dict[str, Any] | None = None,
    file_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "title": title,
        "course": course,
        "task_family": task_family,
        "intent": intent,
        "difficulty": difficulty,
        "input_type": input_type,
        "message": message,
        "file_refs": file_refs or [],
        "structured_input": {},
        "task_options": task_options or {},
        "expected_agent": expected_agent,
        "expected_course_pack": course,
        "expected_statuses": ["success", "partial"],
        "tags": ["runtime_stability", "synthetic", "generated"],
        "source": "runtime_stability_generated_catalog",
        "input_source": "synthetic",
        "provenance": {
            "source_type": "synthetic",
            "source_name": "runtime_stability_generated_catalog",
            "license_or_authorization": "repository-generated synthetic data",
            "publishable": True,
        },
        "official_scoring": False,
        "judge_type": "rule",
    }


def _fill_general(selected: list[dict[str, Any]], target: int) -> None:
    messages = [
        "请用三句话解释二分查找的基本思想。",
        "什么是缓存？请说明它可能带来的一个问题。",
        "请比较同步和异步处理的主要区别。",
        "请解释为什么日志需要包含请求标识。",
        "我的问题不完整：如何提高程序的可靠性？请先说明需要哪些信息。",
        "请用一个生活中的例子解释抽象概念。",
        "为什么测试不能只看平均耗时？",
        "请说明重试和回退分别解决什么问题。",
        "请给出学习复杂概念时的三个步骤。",
        "请解释什么是幂等操作。",
        "请用简短语言解释接口契约。",
        "如果没有足够证据，回答时应该怎么做？",
        "请区分事实、推断和假设。",
        "请解释输入校验为什么属于系统边界。",
        "请说明多轮对话中保持上下文的意义。",
        "请给出一个可复现实验的最小组成部分。",
    ]
    for index, message in enumerate(messages[: max(0, target - len(selected))], 1):
        selected.append(
            _synthetic_case(
                case_id=f"STABILITY_GENERAL_{index:03d}",
                title=f"普通问答稳定性 {index:03d}",
                course="CT",
                task_family="GENERAL_QA",
                intent="general_qa",
                expected_agent="GENERAL_QUESTION_V1",
                message=message,
                difficulty="easy" if index < 9 else "medium",
            )
        )


def _fill_knowledge(selected: list[dict[str, Any]], target: int) -> None:
    topics = {
        "CT": [
            "节点电压法",
            "戴维南定理",
            "基尔霍夫电流定律",
            "一阶电路",
            "相量",
            "功率因数",
        ],
        "AE": [
            "虚短与虚断",
            "负反馈",
            "二极管工作区",
            "BJT静态工作点",
            "MOS管",
            "运放稳定性",
        ],
        "DE": ["组合逻辑", "时序逻辑", "JK触发器", "计数器", "状态机", "竞争冒险"],
        "SS": [
            "卷积",
            "傅里叶变换",
            "采样定理",
            "系统稳定性",
            "拉普拉斯变换",
            "频率响应",
        ],
        "DSP": ["DFT", "数字滤波器", "频谱泄漏", "窗函数", "FFT", "离散采样"],
        "COMM": ["调制", "解调", "噪声", "检测", "信道容量", "编码"],
    }
    number = len(selected) + 1
    for course, names in topics.items():
        for topic in names:
            if len(selected) >= target:
                return
            selected.append(
                _synthetic_case(
                    case_id=f"STABILITY_KNOWLEDGE_{number:03d}",
                    title=f"{course}课程知识稳定性 {topic}",
                    course=course,
                    task_family="KNOWLEDGE_QA",
                    intent="explain_concept",
                    expected_agent="LEARN_01_KNOWLEDGE_QA_V1",
                    message=f"请解释{course}课程中的{topic}，并说明它适用的条件或边界。",
                    difficulty="easy" if topic in names[:2] else "medium",
                )
            )
            number += 1


def _fill_research(selected: list[dict[str, Any]], target: int) -> None:
    messages = [
        "请制作一个科研前沿简报，区分已知结论、证据来源和开放问题。",
        "请比较两类学术方法，并明确比较依据和证据限制。",
        "请解释一篇论文的研究问题、方法、结果和局限。",
        "请整理关于电路可靠性的研究证据，并避免超出资料的结论。",
        "请为一个信号处理主题生成可复核的文献检索范围。",
        "请总结学术资料中的共识与争议，并给出来源标识。",
        "请将研究问题拆成检索问题、证据表和限制说明。",
        "请说明当前资料不足以支持哪些科研结论。",
        "请比较两篇资料的实验条件和结论适用边界。",
        "请输出一份带证据等级和时间说明的研究简报。",
    ]
    for index, message in enumerate(messages[: max(0, target - len(selected))], 1):
        selected.append(
            _synthetic_case(
                case_id=f"STABILITY_RESEARCH_{index:03d}",
                title=f"科研证据稳定性 {index:03d}",
                course="CT" if index % 2 else "SS",
                task_family="GENERAL_QA",
                intent="general_qa",
                expected_agent="RESEARCH_01_ACADEMIC_SEARCH_V1",
                message=message,
                difficulty="hard",
                task_options={
                    "scenario_id": "research_frontier_radar_v1",
                    "user_role": "researcher",
                },
            )
        )


def _fill_multi_turn(selected: list[dict[str, Any]], target: int) -> None:
    # A valid multi-turn evidence point needs an actual session progression,
    # not several sentences packed into one canonical input.  Keep the
    # teaching actions deterministic and end with the explicit disclosure
    # transition so every generated case exercises at least five turns.
    for case in selected:
        options = case.setdefault("task_options", {})
        existing = options.get(
            "_evaluation_follow_up_actions"
        )
        if isinstance(existing, list):
            options["_evaluation_follow_up_actions"] = [
                "request_more_hint",
                "request_more_hint",
                "request_more_hint",
                "switch_to_direct_answer",
            ]
        elif (
            case.get("case_id") == "RUNTIME_COURSE_SWITCH_001"
            and isinstance((case.get("structured_input") or {}).get("turns"), list)
        ):
            options.update(
                {
                    "teaching_mode": "guided_learning",
                    "_evaluation_follow_up_actions": [
                        "request_more_hint",
                        "request_more_hint",
                        "request_more_hint",
                        "switch_to_direct_answer",
                    ],
                }
            )
    for index in range(len(selected) + 1, target + 1):
        selected.append(
            _synthetic_case(
                case_id=f"STABILITY_MULTI_TURN_{index:03d}",
                title=f"多轮对话稳定性 {index:03d}",
                course="CT",
                task_family="ACADEMIC_SOLVING",
                intent="solve_problem",
                expected_agent="ACADEMIC_PROBLEM_SOLVER",
                message="已知电阻为5欧姆、电压为10伏，请先说明求电流需要的步骤。",
                difficulty="medium",
                task_options={
                    "teaching_mode": "guided_learning",
                    "_evaluation_follow_up_actions": [
                        "request_more_hint",
                        "request_more_hint",
                        "request_more_hint",
                        "switch_to_direct_answer",
                    ],
                },
            )
        )


def _build() -> dict[str, Any]:
    config = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    records = _load_source_cases()
    used: set[str] = set()
    categories: dict[str, list[dict[str, Any]]] = {}
    predicates = {
        "multimodal": _is_multimodal,
        "research": _is_research,
        "multi_turn": _is_multi_turn,
        "boundary": _is_boundary,
        "general": _is_general,
        "knowledge": _is_knowledge,
        "solver": _is_solver,
    }
    for category, target in config["categories"].items():
        # Knowledge coverage is deliberately generated below: it must include
        # all six course packs, independent of source-file ordering.
        categories[category] = (
            []
            if category == "knowledge"
            else _take(records, predicates[category], int(target), used)
        )

    _fill_general(categories["general"], int(config["categories"]["general"]))
    _fill_knowledge(categories["knowledge"], int(config["categories"]["knowledge"]))
    _fill_research(categories["research"], int(config["categories"]["research"]))
    _fill_multi_turn(categories["multi_turn"], int(config["categories"]["multi_turn"]))

    flat: list[dict[str, Any]] = []
    case_categories: dict[str, str] = {}
    for category in config["categories"]:
        values = categories[category]
        target = int(config["categories"][category])
        if len(values) < target:
            raise ValueError(f"{category}: only selected {len(values)} of {target}")
        for case in values[:target]:
            _normalize_file_refs(case)
            validated = EvaluationCase.model_validate(case).model_dump(mode="json")
            flat.append(validated)
            case_categories[validated["case_id"]] = category

    if len(flat) != int(config["target_total"]):
        raise ValueError(f"expected {config['target_total']} cases, got {len(flat)}")
    encoded_sources = b"".join(
        path.relative_to(ROOT).as_posix().encode("utf-8")
        + b"\0"
        + path.read_bytes()
        + b"\0"
        for path, _case in records
    )
    return {
        "schema_version": "runtime_stability.v1",
        "source_catalog_sha256": hashlib.sha256(encoded_sources).hexdigest(),
        "case_count": len(flat),
        "categories": config["categories"],
        "case_categories": case_categories,
        "cases": flat,
    }


def main() -> None:
    payload = _build()
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"generated {OUTPUT_PATH}")
    print(f"case_count={payload['case_count']}")
    print(f"source_catalog_sha256={payload['source_catalog_sha256']}")


if __name__ == "__main__":
    main()
