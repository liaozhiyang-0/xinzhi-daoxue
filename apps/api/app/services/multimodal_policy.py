from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.contracts.agent import AgentRequest, AttachmentRef, Intent
from app.contracts.multimodal import (
    ImageRole,
    MultimodalCapabilityHint,
    RoleSource,
)
from app.observability.architecture_telemetry import architecture_telemetry

IMAGE_ROLES: tuple[ImageRole, ...] = (
    "TEXT_SCREENSHOT",
    "PROBLEM_STATEMENT",
    "CIRCUIT_DIAGRAM",
    "STUDENT_SOLUTION",
    "TABLE",
    "CHART",
    "WAVEFORM",
    "FORMULA",
    "DOCUMENT_PAGE",
    "REFERENCE_IMAGE",
    "GENERAL_IMAGE",
    "UNKNOWN",
)

MULTIMODAL_INTENTS: tuple[str, ...] = (
    "GENERAL_QA",
    "SOLVE_PROBLEM",
    "EXPLAIN_IMAGE",
    "READ_TEXT",
    "CHECK_MY_WORK",
    "COMPARE_IMAGES",
    "SUMMARIZE",
    "TABLE_ANALYSIS",
    "WAVEFORM_ANALYSIS",
    "CIRCUIT_ANALYSIS",
    "CIRCUIT_RENDER",
    "UNKNOWN",
)

_ROLE_MARKERS: dict[ImageRole, tuple[str, ...]] = {
    "TEXT_SCREENSHOT": ("截图", "截屏", "screen shot", "screenshot"),
    "PROBLEM_STATEMENT": ("题目", "题干", "problem", "question"),
    "CIRCUIT_DIAGRAM": ("电路图", "电路原理图", "circuit diagram", "schematic"),
    "STUDENT_SOLUTION": (
        "我的答案",
        "我的解答",
        "学生答案",
        "作答",
        "my answer",
        "my solution",
    ),
    "TABLE": ("表格", "数据表", "table", "spreadsheet"),
    "CHART": ("图表", "柱状图", "折线图", "chart", "plot"),
    "WAVEFORM": ("波形", "频谱", "时域", "频域", "waveform", "spectrum"),
    "FORMULA": ("公式", "方程", "formula", "equation"),
    "DOCUMENT_PAGE": ("文档", "页面", "document", "page"),
    "REFERENCE_IMAGE": ("参考图", "示例图", "reference image", "example image"),
}

_ROLE_CAPABILITIES: dict[ImageRole, str] = {
    "TEXT_SCREENSHOT": "text_reading",
    "PROBLEM_STATEMENT": "solver",
    "CIRCUIT_DIAGRAM": "circuit_analysis",
    "STUDENT_SOLUTION": "student_work_review",
    "TABLE": "table_analysis",
    "CHART": "chart_analysis",
    "WAVEFORM": "waveform_analysis",
    "FORMULA": "formula_understanding",
    "DOCUMENT_PAGE": "document_understanding",
    "REFERENCE_IMAGE": "general_vision",
    "GENERAL_IMAGE": "general_vision",
    "UNKNOWN": "general_vision",
}

_CIRCUIT_TOPOLOGY_MARKERS = (
    "拓扑",
    "节点",
    "支路",
    "网孔",
    "等效电路",
    "节点电压",
    "mesh",
    "topology",
    "node voltage",
    "branch current",
)
_CIRCUIT_RENDER_MARKERS = (
    "画图",
    "重绘",
    "绘制",
    "生成电路图",
    "重新画",
    "等效电路",
    "draw circuit",
    "redraw circuit",
    "render circuit",
)


def enrich_multimodal_request(request: AgentRequest) -> AgentRequest:
    """Attach lightweight image roles and a capability hint to a request.

    This is semantic metadata only.  It never selects an Agent or invokes a
    provider, and it is intentionally idempotent for already-enriched input.
    """

    images = [
        attachment
        for attachment in request.attachments
        if attachment.content_type.startswith("image/")
    ]
    if not images:
        return request

    options = dict(request.options)
    existing_hint = _validated_hint(options.get("multimodal_capability_hint"))
    updated_attachments = _assign_attachment_roles(request, len(images))
    hint = existing_hint or build_multimodal_capability_hint(
        request.model_copy(update={"attachments": updated_attachments})
    )
    changed = updated_attachments != request.attachments or existing_hint is None
    if not changed and existing_hint is not None:
        return request

    _record_image_roles(updated_attachments)
    options["multimodal_capability_hint"] = hint.model_dump(mode="json")
    return request.model_copy(
        update={"attachments": updated_attachments, "options": options}
    )


def build_multimodal_capability_hint(
    request: AgentRequest,
) -> MultimodalCapabilityHint:
    """Infer explainable multimodal capabilities without fixing execution."""

    text = request.input_text().casefold()
    options = request.options
    explicit_intent = _normalise_intent(options.get("multimodal_intent"))
    intent = explicit_intent or _intent_from_text(text, request.intent)
    roles = [attachment.primary_role for attachment in request.attachments]
    capabilities = {
        "general_vision",
        *(_ROLE_CAPABILITIES[role] for role in roles if role in _ROLE_CAPABILITIES),
    }
    intent_capability = {
        "READ_TEXT": "text_reading",
        "EXPLAIN_IMAGE": "general_vision",
        "CHECK_MY_WORK": "student_work_review",
        "COMPARE_IMAGES": "compare_images",
        "SUMMARIZE": "summarizer",
        "TABLE_ANALYSIS": "table_analysis",
        "WAVEFORM_ANALYSIS": "waveform_analysis",
        "CIRCUIT_ANALYSIS": "circuit_analysis",
        "CIRCUIT_RENDER": "circuit_render",
        "SOLVE_PROBLEM": "solver",
    }.get(intent)
    if intent_capability:
        capabilities.add(intent_capability)

    circuit_ir_requested, trigger_source, reason_codes = _circuit_ir_trigger(
        request, intent, text
    )
    return MultimodalCapabilityHint(
        intent=intent,
        possible_capabilities=sorted(capabilities),
        circuit_ir_requested=circuit_ir_requested,
        trigger_source=trigger_source,
        reason_codes=reason_codes,
    )


def get_multimodal_capability_hint(
    request: AgentRequest,
) -> MultimodalCapabilityHint:
    existing = _validated_hint(request.options.get("multimodal_capability_hint"))
    return existing or build_multimodal_capability_hint(request)


def requires_circuit_ir(request: AgentRequest) -> bool:
    return get_multimodal_capability_hint(request).circuit_ir_requested


def _assign_attachment_roles(
    request: AgentRequest, image_count: int
) -> list[AttachmentRef]:
    explicit = _explicit_role_map(request)
    prompt = request.input_text().casefold()
    conversation = _conversation_text(request).casefold()
    updated: list[AttachmentRef] = []
    for index, attachment in enumerate(request.attachments):
        if not attachment.content_type.startswith("image/"):
            updated.append(attachment)
            continue
        override = (
            explicit.get(index + 1)
            or explicit.get(index)
            or explicit.get(attachment.file_id)
        )
        if override is None and attachment.role_source == "explicit_user":
            updated.append(attachment)
            continue
        inferred_secondary: list[ImageRole] = []
        role: ImageRole | None
        if override is not None:
            role = override[0]
        else:
            role, inferred_secondary = _roles_from_position(
                prompt, index, image_count
            )
        if role is None:
            role, inferred_secondary = _roles_from_position(
                conversation, index, image_count
            )
        if role is None:
            role = _role_from_filename(attachment.filename)
        if role is None and attachment.primary_role != "UNKNOWN":
            updated.append(attachment)
            continue
        if role is None:
            role = "UNKNOWN"
        source: RoleSource = (
            "explicit_user"
            if override is not None or _has_explicit_role_phrase(prompt, index)
            else "conversation"
            if _has_explicit_role_phrase(conversation, index)
            else "multimodal_inference"
            if role != "UNKNOWN"
            else "unknown"
        )
        confidence = (
            1.0
            if source == "explicit_user"
            else 0.75
            if role != "UNKNOWN"
            else 0.0
        )
        secondary_roles = (
            override[1]
            if override is not None
            else list(
                dict.fromkeys(
                    [
                        *attachment.secondary_roles,
                        *inferred_secondary,
                    ]
                )
            )
        )
        updated.append(
            attachment.model_copy(
                update={
                    "primary_role": role,
                    "secondary_roles": secondary_roles,
                    "role_source": source,
                    "role_confidence": confidence,
                }
            )
        )

    return updated


def _explicit_role_map(
    request: AgentRequest,
) -> dict[int | str, tuple[ImageRole, list[ImageRole]]]:
    raw = request.options.get("attachment_roles")
    if not isinstance(raw, Mapping):
        return {}
    result: dict[int | str, tuple[ImageRole, list[ImageRole]]] = {}
    for key, value in raw.items():
        payload = value if isinstance(value, Mapping) else {"primary_role": value}
        role = _normalise_role(payload.get("primary_role"))
        if role is not None:
            secondary = [
                candidate
                for item in payload.get("secondary_roles", [])
                if (candidate := _normalise_role(item)) is not None
            ]
            result[_normalise_attachment_key(key)] = (role, secondary)
    return result


def _normalise_attachment_key(value: Any) -> int | str:
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text) if text.isdigit() else text


def _role_from_position(text: str, index: int, image_count: int) -> ImageRole | None:
    primary, _ = _roles_from_position(text, index, image_count)
    return primary


def _roles_from_position(
    text: str, index: int, image_count: int
) -> tuple[ImageRole | None, list[ImageRole]]:
    scoped_text = _position_scope(text, index, image_count)
    matches: list[ImageRole] = []
    for role, markers in _ROLE_MARKERS.items():
        if any(marker in scoped_text for marker in markers):
            matches.append(role)
    if not matches:
        return None, []
    priority = (
        "PROBLEM_STATEMENT",
        "STUDENT_SOLUTION",
        "CIRCUIT_DIAGRAM",
        "TABLE",
        "CHART",
        "WAVEFORM",
        "FORMULA",
        "DOCUMENT_PAGE",
        "REFERENCE_IMAGE",
        "TEXT_SCREENSHOT",
    )
    primary = next((role for role in priority if role in matches), matches[0])
    return primary, [role for role in matches if role != primary]


def _position_scope(text: str, index: int, image_count: int) -> str:
    if image_count == 1:
        return text
    start_candidates = [
        text.find(pattern)
        for pattern in _ordinal_patterns(index)
        if len(pattern) > 1 and text.find(pattern) >= 0
    ]
    if not start_candidates:
        return ""
    start = min(start_candidates)
    following: list[int] = []
    for next_index in range(index + 1, image_count):
        following.extend(
            text.find(pattern)
            for pattern in _ordinal_patterns(next_index)
            if len(pattern) > 1 and text.find(pattern) > start
        )
    end = min(following) if following else len(text)
    return text[start:end]


def _has_explicit_role_phrase(text: str, index: int) -> bool:
    return _role_from_position(text, index, index + 1) is not None


def _ordinal_patterns(index: int) -> tuple[str, ...]:
    chinese = ("一", "二", "三", "四", "五", "六", "七", "八", "九", "十")
    number = index + 1
    values = [
        str(number),
        f"图{number}",
        f"image {number}",
        f"第{number}张",
        f"第{number}幅",
    ]
    if number <= len(chinese):
        values.extend(
            (
                chinese[number - 1],
                f"图{chinese[number - 1]}",
                f"第{chinese[number - 1]}张",
            )
        )
    return tuple(values)


def _role_from_filename(filename: str) -> ImageRole | None:
    text = filename.casefold()
    for role, markers in _ROLE_MARKERS.items():
        if any(marker in text for marker in markers):
            return role
    return None


def _conversation_text(request: AgentRequest) -> str:
    for key in ("conversation_summary", "conversation_text", "prior_context"):
        value = request.options.get(key)
        if isinstance(value, str):
            return value
    return ""


def _intent_from_text(text: str, request_intent: Intent) -> str:
    if not text:
        return "UNKNOWN"
    if any(marker in text for marker in _CIRCUIT_RENDER_MARKERS) or (
        "电路图" in text
        and any(marker in text for marker in ("生成", "绘制", "画", "重绘"))
    ):
        return "CIRCUIT_RENDER"
    if any(
        marker in text
        for marker in (
            "检查我的答案",
            "批改",
            "我的解答",
            "检查",
            "check my work",
            "review",
            "verify my answer",
        )
    ):
        return "CHECK_MY_WORK"
    if any(marker in text for marker in ("比较", "对比", "compare")):
        return "COMPARE_IMAGES"
    if any(marker in text for marker in ("表格", "数据表", "table")):
        return "TABLE_ANALYSIS"
    if any(
        marker in text
        for marker in ("波形", "频谱", "时域", "频域", "waveform", "spectrum")
    ):
        return "WAVEFORM_ANALYSIS"
    if any(
        marker in text
        for marker in ("提取文字", "识别文字", "读出", "ocr", "read text")
    ):
        return "READ_TEXT"
    if any(marker in text for marker in ("总结", "概括", "摘要", "summarize")):
        return "SUMMARIZE"
    if any(
        marker in text
        for marker in ("解释图片", "图中是什么意思", "explain this image")
    ):
        return "EXPLAIN_IMAGE"
    if any(
        marker in text
        for marker in ("帮我看看", "看一下这张图", "看看这张图片", "look at this image")
    ):
        return "EXPLAIN_IMAGE"
    if any(marker in text for marker in ("电路", "circuit")) and any(
        marker in text for marker in ("分析", "计算", "求解", "analy", "solve")
    ):
        return "CIRCUIT_ANALYSIS"
    if any(
        marker in text
        for marker in (
            "拓扑",
            "节点",
            "支路",
            "网孔",
            "等效电路",
            "node voltage",
            "topology",
        )
    ):
        return "CIRCUIT_ANALYSIS"
    if request_intent == Intent.GENERAL_QA:
        return "GENERAL_QA"
    if request_intent == Intent.CHECK_USER_SOLUTION:
        return "CHECK_MY_WORK"
    if request_intent == Intent.SUMMARIZE_KNOWLEDGE:
        return "SUMMARIZE"
    if request_intent == Intent.EXPLAIN_CONCEPT:
        return "EXPLAIN_IMAGE"
    if request_intent == Intent.UNKNOWN:
        return "UNKNOWN"
    return "SOLVE_PROBLEM"


def _circuit_ir_trigger(
    request: AgentRequest, intent: str, text: str
) -> tuple[bool, str, list[str]]:
    options = request.options
    if intent == "CIRCUIT_RENDER":
        return True, "explicit_user", ["explicit_circuit_render"]
    if intent == "CIRCUIT_ANALYSIS" and (
        any(marker in text for marker in _CIRCUIT_TOPOLOGY_MARKERS)
        or any(marker in text for marker in ("电路", "circuit"))
    ):
        return True, "user_prompt", ["topology_level_circuit_analysis"]
    if options.get("requires_topology") is True or options.get(
        "solver_requires_topology"
    ) is True:
        return True, "planner_hint", ["solver_requires_topology"]
    if options.get("plan_pattern") == "SOLVE_VERIFY_RENDER" or options.get(
        "_planner_plan_pattern"
    ) == "SOLVE_VERIFY_RENDER":
        return True, "plan_pattern", ["solve_verify_render"]
    if any(marker in text for marker in _CIRCUIT_TOPOLOGY_MARKERS):
        return True, "topology_signal", ["topology_terms_require_structured_ir"]
    return False, "not_required", ["general_multimodal_understanding"]


def _normalise_intent(value: Any) -> str | None:
    candidate = str(value).strip().upper() if value not in (None, "") else ""
    return candidate if candidate in MULTIMODAL_INTENTS else None


def _normalise_role(value: Any) -> ImageRole | None:
    candidate = str(value).strip().upper() if value not in (None, "") else ""
    return candidate if candidate in IMAGE_ROLES else None


def _validated_hint(value: Any) -> MultimodalCapabilityHint | None:
    if isinstance(value, MultimodalCapabilityHint):
        return value
    if isinstance(value, Mapping):
        try:
            return MultimodalCapabilityHint.model_validate(value)
        except ValueError:
            return None
    return None


def _record_image_roles(attachments: list[AttachmentRef]) -> None:
    images = [item for item in attachments if item.content_type.startswith("image/")]
    if not images:
        return
    architecture_telemetry.increment("multimodal_task_count")
    for attachment in images:
        role_name = attachment.primary_role.casefold()
        architecture_telemetry.increment(f"image_role_count_{_snake(role_name)}")
        if attachment.primary_role == "UNKNOWN":
            architecture_telemetry.increment("unknown_image_role_count")


def _snake(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_")


__all__ = [
    "build_multimodal_capability_hint",
    "enrich_multimodal_request",
    "get_multimodal_capability_hint",
    "requires_circuit_ir",
]
