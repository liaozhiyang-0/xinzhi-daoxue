from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any

from app.contracts import AgentRequest, MaterialExtractionResult

MATERIAL_FIELDS = {
    "topic",
    "student_level",
    "class_duration",
    "lesson_count",
    "teaching_goals",
    "prerequisites",
    "available_resources",
    "special_constraints",
    "assignment_text",
    "student_answer",
    "reference_answer",
    "rubric",
    "maximum_score",
    "teacher_requirements",
    "writing_task",
    "document_type",
    "target_audience",
    "target_venue",
    "source_text",
    "trusted_sources",
    "citation_context",
    "style_requirements",
    "language",
    "research_question",
    "study_design",
    "data_description",
    "variable_definitions",
    "sample_size",
    "missing_data_summary",
    "provided_results",
    "analysis_goal",
    "constraints",
    "software_environment",
    "trusted_context",
}

LABEL_ALIASES = {
    "topic": ("主题", "课题", "教学主题"),
    "student_level": ("学生层次", "学生水平", "授课对象", "年级"),
    "class_duration": ("课时", "时长", "课堂时长"),
    "lesson_count": ("课次数", "课时数", "节数"),
    "assignment_text": ("题目", "作业题目", "作业"),
    "student_answer": ("学生答案", "学生作答", "作答"),
    "reference_answer": ("参考答案", "标准答案"),
    "rubric": ("评分标准", "评分细则", "rubric"),
    "maximum_score": ("满分", "总分"),
    "source_text": ("原文", "论文段落", "待修改文本", "正文"),
    "writing_task": ("写作任务", "修改要求", "写作要求"),
    "research_question": ("研究问题", "研究目的"),
    "data_description": ("数据描述", "数据摘要", "数据"),
    "variable_definitions": ("变量定义", "变量说明"),
    "provided_results": ("结果", "实验结果", "分析结果", "真实结果"),
}

_ALL_LABELS = tuple(alias for aliases in LABEL_ALIASES.values() for alias in aliases)


class RequestMaterialExtractor:
    """Extract explicit material without model calls or semantic rewriting."""

    def extract(self, request: AgentRequest) -> MaterialExtractionResult:
        started = perf_counter()
        raw_text = self._raw_text(request)
        materials: dict[str, Any] = {}
        sources: dict[str, str] = {}
        warnings: list[str] = []

        for field in MATERIAL_FIELDS:
            value = request.canonical_input.get(field, request.options.get(field))
            if not self._empty(value):
                materials[field] = value
                sources[field] = "canonical_input"

        json_payload = self._json_payload(raw_text)
        if json_payload:
            for field in MATERIAL_FIELDS:
                value = json_payload.get(field)
                if field not in materials and not self._empty(value):
                    materials[field] = value
                    sources[field] = "json"

        for field, aliases in LABEL_ALIASES.items():
            if field in materials:
                continue
            value = self._label_value(raw_text, aliases)
            if value:
                materials[field] = value
                sources[field] = "label"

        self._extract_teaching_fields(raw_text, materials, sources)
        self._extract_research_fields(raw_text, materials, sources)

        attachment_types = [item.content_type for item in request.attachments]
        if any(item == "application/pdf" for item in attachment_types):
            warnings.append("PDF仅保存为附件；需粘贴关键文字或数据摘要")
        if any(
            item
            in {
                "text/csv",
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
            for item in attachment_types
        ) and not any(
            key in materials
            for key in ("data_description", "variable_definitions", "provided_results")
        ):
            warnings.append("表格未自动推断数值内容；需提供文本数据摘要")

        explicit_count = sum(
            1
            for source in sources.values()
            if source in {"canonical_input", "json", "label"}
        )
        confidence = min(1.0, 0.25 + explicit_count * 0.12)
        if not materials:
            confidence = 0.0
        latency_ms = (perf_counter() - started) * 1000
        return MaterialExtractionResult(
            raw_text=raw_text,
            materials=materials,
            source_fields=sources,
            confidence=confidence,
            warnings=warnings,
            attachment_types=attachment_types,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _raw_text(request: AgentRequest) -> str:
        for key in ("text", "question", "problem", "query", "prompt"):
            value = request.canonical_input.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _empty(value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    @staticmethod
    def _json_payload(text: str) -> dict[str, Any] | None:
        candidate = text.strip()
        if not candidate.startswith("{") or not candidate.endswith("}"):
            return None
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None

    @staticmethod
    def _label_value(text: str, aliases: tuple[str, ...]) -> str:
        if not text:
            return ""
        alias_pattern = "|".join(re.escape(alias) for alias in aliases)
        all_pattern = "|".join(re.escape(alias) for alias in _ALL_LABELS)
        pattern = re.compile(
            rf"(?ims)^\s*(?:#+\s*)?(?:{alias_pattern})\s*[：:]\s*(.*?)"
            rf"(?=^\s*(?:#+\s*)?(?:{all_pattern})\s*[：:]|\Z)"
        )
        match = pattern.search(text)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_teaching_fields(
        text: str, materials: dict[str, Any], sources: dict[str, str]
    ) -> None:
        duration = re.search(r"(?<!\d)(\d{1,3})\s*分钟", text)
        if duration and "class_duration" not in materials:
            materials["class_duration"] = f"{duration.group(1)}分钟"
            sources["class_duration"] = "pattern"
        lesson_count = re.search(r"(?<!\d)(\d{1,2})\s*(?:节|课时)", text)
        if lesson_count and "lesson_count" not in materials:
            materials["lesson_count"] = lesson_count.group(1)
            sources["lesson_count"] = "pattern"
        level = re.search(
            r"(大[一二三四]|本科(?:生)?|研究生|高职|中职|初中|高中)(?:学生)?", text
        )
        if level and "student_level" not in materials:
            materials["student_level"] = level.group(0)
            sources["student_level"] = "pattern"
        maximum = re.search(r"满分\s*[：:]?\s*(\d+(?:\.\d+)?)\s*分?", text)
        if maximum and "maximum_score" not in materials:
            materials["maximum_score"] = maximum.group(1)
            sources["maximum_score"] = "pattern"

    @staticmethod
    def _extract_research_fields(
        text: str, materials: dict[str, Any], sources: dict[str, str]
    ) -> None:
        if any(
            token in text
            for token in (
                "论文",
                "摘要",
                "润色",
                "改写",
                "审稿",
                "提纲",
                "引言",
                "方法部分",
                "结果部分",
                "Results",
                "结论",
                "引用",
                "学术表达",
            )
        ):
            if "writing_task" not in materials:
                materials["writing_task"] = text[:500]
                sources["writing_task"] = "instruction"
        has_numeric_result = bool(
            re.search(
                r"(?:AUC|p\s*值?|样本量|置信区间|准确率|召回率)\s*[=:为]?\s*\d",
                text,
                re.I,
            )
        )
        if (
            has_numeric_result
            or any(token in text for token in ("结果显示", "实验结果为", "分析结果为"))
        ) and "provided_results" not in materials:
            materials["provided_results"] = text
            sources["provided_results"] = "verbatim_result_context"
