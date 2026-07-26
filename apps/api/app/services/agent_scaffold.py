from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.agents import AgentRegistry

AGENT_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]+_V[0-9]+$")


@dataclass(frozen=True, slots=True)
class AgentScaffoldSpec:
    agent_id: str
    display_name: str
    version: str = "1.0"
    user_roles: tuple[str, ...] = ("student",)
    courses: tuple[str, ...] = ("CT", "AE", "DE")
    intents: tuple[str, ...] = ("general_qa",)
    input_modes: tuple[str, ...] = ("text",)
    required_inputs: tuple[str, ...] = ("question", "course_id")
    optional_inputs: tuple[str, ...] = ("request_id",)
    output_fields: tuple[str, ...] = ("result",)
    parser_type: str = "json"
    retrieval_policy: str = "no_rag"
    fallback_type: str = "planned_response"
    mock_profile: str = "generic_planned_v1"
    flow_env_key: str = ""


class AgentScaffoldService:
    def build(self, spec: AgentScaffoldSpec) -> dict[str, str]:
        self._validate_spec(spec)
        flow_env = (
            spec.flow_env_key or f"XINGCHEN_{spec.agent_id.removesuffix('_V1')}_FLOW_ID"
        )
        retrieval_enabled = spec.retrieval_policy != "no_rag"
        input_mapping: dict[str, dict[str, Any]] = {}
        for source in (*spec.required_inputs, *spec.optional_inputs):
            input_mapping[source] = {
                "source": source,
                "transform": "string",
                "max_length": 12000 if "context" in source else 4000,
            }
        output_mapping = {
            field: {"target": f"business_data.{field}", "parser": "identity"}
            for field in spec.output_fields
        }
        definition = {
            spec.agent_id: {
                "display_name": spec.display_name,
                "version": spec.version,
                "schema_version": "1",
                "scene": "learning",
                "provider": {
                    "type": "xingchen",
                    "flow_env_key": flow_env,
                    "timeout_seconds": 45,
                    "max_retries": 0,
                    "parser_type": spec.parser_type,
                    "output_schema": f"{spec.agent_id.casefold()}_v1",
                },
                "enabled": False,
                "publication_status": "planned",
                "mode": "provider",
                "course_ids": list(spec.courses),
                "supports": list(spec.input_modes),
                "capabilities": {
                    "user_roles": list(spec.user_roles),
                    "courses": list(spec.courses),
                    "intents": list(spec.intents),
                    "input_modes": list(spec.input_modes),
                    "supports_session_context": "conversation_summary"
                    in spec.optional_inputs,
                    "supports_images": any(
                        "image" in mode for mode in spec.input_modes
                    ),
                },
                "input_contract": {
                    "required": list(spec.required_inputs),
                    "optional": list(spec.optional_inputs),
                },
                "input_mapping": input_mapping,
                "output_mapping": output_mapping,
                "retrieval_policy": {
                    "enabled": retrieval_enabled,
                    "policy_name": f"{spec.agent_id.casefold()}_policy",
                    "mode": spec.retrieval_policy,
                    "course_required": retrieval_enabled,
                    "text_top_k": 3 if retrieval_enabled else 0,
                    "image_top_k": 0,
                    "reranker": "off",
                    "context_max_chars": 6000,
                },
                "fallback": {
                    "type": "planned",
                    "handler": spec.fallback_type,
                    "trigger_on": [
                        "cloud_timeout",
                        "cloud_http_error",
                        "cloud_parse_error",
                        "not_configured",
                    ],
                },
                "development": {
                    "mock_enabled": True,
                    "mock_profile": spec.mock_profile,
                    "mock_latency_ms": 25,
                },
            }
        }
        AgentRegistry._load_agents(definition)
        contract_cases = [
            {
                "case_id": f"{spec.agent_id}_NORMAL",
                "agent_id": spec.agent_id,
                "input": {"question": "正常契约输入", "course_id": spec.courses[0]},
                "expected_status": "success",
                "required_business_fields": list(spec.output_fields),
                "forbidden_strings": ["Authorization", "XINGCHEN_API_KEY"],
                "manual_review_required": True,
            },
            {
                "case_id": f"{spec.agent_id}_MISSING",
                "agent_id": spec.agent_id,
                "input": {},
                "expected_status": "validation_error",
                "required_business_fields": [],
                "forbidden_strings": [],
                "manual_review_required": False,
            },
            {
                "case_id": f"{spec.agent_id}_BOUNDARY",
                "agent_id": spec.agent_id,
                "input": {"question": "边界或降级输入", "course_id": spec.courses[0]},
                "expected_status": "success",
                "required_business_fields": [],
                "forbidden_strings": [],
                "manual_review_required": True,
            },
        ]
        return {
            "agent_definition.yaml": yaml.safe_dump(
                definition, allow_unicode=True, sort_keys=False
            ),
            ".env.example": f"{flow_env}=\n",
            "mock_profile.yaml": yaml.safe_dump(
                {
                    spec.mock_profile: {
                        "status": "success",
                        "answer_text": "开发态Mock结果，不代表正式云端能力。",
                        "business_data": {field: None for field in spec.output_fields},
                    }
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            "contract_cases.json": json.dumps(
                contract_cases, ensure_ascii=False, indent=2
            ),
            "test_contract_template.py": (
                "def test_generated_agent_contract_template():\n"
                "    # 将生成的fixture合并到统一参数化契约测试。\n"
                "    assert True\n"
            ),
            "test_real_cloud_template.py": (
                "import os\nimport pytest\n\n"
                "pytestmark = pytest.mark.skipif(\n"
                "    os.getenv('RUN_REAL_XINGCHEN_TESTS') != '1',\n"
                "    reason='explicit real cloud opt-in required',\n"
                ")\n"
            ),
            "debug_request.json": json.dumps(
                {
                    "question": "Debug示例输入",
                    "course_id": spec.courses[0],
                    "intent": spec.intents[0],
                    "allow_mock": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
            "integration_checklist.md": (
                "# 接入检查清单\n\n"
                "- [ ] 合并AgentDefinition到唯一registry.yaml\n"
                "- [ ] 合并Mock profile并运行契约fixture\n"
                "- [ ] 在本机.env填写Flow ID\n"
                "- [ ] 使用脱敏Cloud sample比较结构\n"
                "- [ ] 显式运行真实云端测试\n"
                "- [ ] 确认后再设置enabled=true和published\n"
            ),
        }

    def write(
        self,
        spec: AgentScaffoldSpec,
        output_root: Path,
        *,
        force: bool = False,
    ) -> list[Path]:
        files = self.build(spec)
        target = output_root / spec.agent_id
        existing = [target / name for name in files if (target / name).exists()]
        if existing and not force:
            raise FileExistsError(f"脚手架文件已存在: {existing[0]}")
        target.mkdir(parents=True, exist_ok=True)
        written = []
        for name, content in files.items():
            path = target / name
            path.write_text(content, encoding="utf-8")
            written.append(path)
        return written

    @staticmethod
    def _validate_spec(spec: AgentScaffoldSpec) -> None:
        if not AGENT_ID_RE.fullmatch(spec.agent_id):
            raise ValueError("agent_id必须为大写下划线格式并以_V数字结尾")
        if not spec.display_name.strip():
            raise ValueError("display_name不能为空")
        if not spec.required_inputs:
            raise ValueError("至少需要一个required input")
