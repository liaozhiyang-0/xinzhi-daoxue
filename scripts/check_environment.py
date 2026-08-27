from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.agents import AgentRegistry  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.services.model_registry import ModelRegistry  # noqa: E402


def main() -> int:
    settings = Settings()
    registry = AgentRegistry()
    model_registry = ModelRegistry(settings)
    workflows = []
    for definition in registry.list_agents():
        if definition.agent_id not in {
            "ROUTER_01_FALLBACK_V1",
            "LEARN_01_KNOWLEDGE_QA_V1",
            "ACADEMIC_PROBLEM_SOLVER",
            "TEACH_01_LESSON_PREP_V1",
            "TEACH_02_ASSIGNMENT_REVIEW_V1",
            "RESEARCH_02_ACADEMIC_WRITING_V1",
            "RESEARCH_03_DATA_ANALYSIS_V1",
        }:
            continue
        local_available = registry.is_runtime_available(definition.agent_id, settings)
        workflows.append(
            {
                "agent_id": definition.agent_id,
                "execution_mode": definition.execution_mode,
                "local_ready": local_available,
                "local_handler_available": local_available,
            }
        )
    payload = {
        "environment": settings.app_env,
        "cpu_default": settings.text_embedding_device in {"auto", "cpu"},
        "knowledge_sources": {
            key: value.is_dir() for key, value in settings.knowledge_paths.items()
        },
        "model_apis": {
            "iflytek_spark": {
                "configured": bool(
                    settings.iflytek_spark_enabled
                    and settings.iflytek_spark_api_key.get_secret_value()
                ),
                "model": settings.iflytek_spark_model,
            },
            "dashscope": {
                "configured": bool(
                    settings.dashscope_enabled
                    and settings.dashscope_api_key.get_secret_value()
                ),
                "models": [
                    settings.qwen_text_fast_model,
                    settings.qwen_vision_fast_model,
                    settings.qwen_vision_primary_model,
                    settings.qwen_brief_model,
                ],
            },
            "registry_valid": not model_registry.errors,
            "registry_errors": model_registry.errors,
        },
        "provider_mode": settings.default_agent_provider,
        "workflows": workflows,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
