from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.agents import AgentDefinition, AgentRegistry  # type: ignore[import-untyped]  # noqa: E402, I001
from app.capabilities import default_capability_registry  # type: ignore[import-untyped]  # noqa: E402
from app.core.config import Settings  # type: ignore[import-untyped]  # noqa: E402
from app.courses import default_course_registry  # type: ignore[import-untyped]  # noqa: E402
from app.services.error_pool import ErrorPoolRegistry  # type: ignore[import-untyped]  # noqa: E402
from app.services.learning_outcome import LearningOutcomeService  # type: ignore[import-untyped]  # noqa: E402
from app.services.skill_registry import SkillRegistry  # type: ignore[import-untyped]  # noqa: E402


def safe_status(value: str, *, required: bool) -> str:
    if value:
        return "configured"
    return "missing" if required else "not_required"


def agent_status(
    agent: AgentDefinition,
    registry: AgentRegistry,
    settings: Settings,
) -> dict[str, object]:
    agent_id = agent.agent_id
    frozen = (
        agent_id == "RESEARCH_03_DATA_ANALYSIS_V1"
        and not settings.data_analysis_enabled
    )
    return {
        "agent_id": agent_id,
        "enabled": agent.enabled,
        "publication_status": agent.publication_status,
        "local_ready": registry.is_runtime_available(agent_id, settings),
        "runtime_available": (
            False if frozen else registry.is_runtime_available(agent_id, settings)
        ),
        "frozen": frozen,
        "unavailable_reason": "data_analysis_frozen" if frozen else "",
    }


def validate(settings: Settings) -> dict[str, object]:
    registry = AgentRegistry()
    course_registry = default_course_registry()
    skill_registry = SkillRegistry(
        course_registry,
        default_capability_registry(),
    )
    error_pool_registry = ErrorPoolRegistry()
    learning_outcome = LearningOutcomeService()
    teaching_courses = ("CT", "AE", "DE")
    error_pool_coverage: dict[str, object] = {}
    course_pack_status: dict[str, object] = {}
    for course_id in teaching_courses:
        skills = skill_registry.list_for_course(course_id)
        templates = error_pool_registry.list_for_course(course_id)
        referenced = {
            signature
            for skill in skills
            for signature in skill.common_error_signatures
        }
        usable_templates = {
            template.error_signature
            for template in templates
            if template.enabled
            and template.teacher_reviewed
            and template.match_mode == "exact_rule"
        }
        covered = referenced.intersection(usable_templates)
        error_pool_coverage[course_id] = {
            "skill_count": len(skills),
            "referenced_error_signature_count": len(referenced),
            "covered_error_signature_count": len(covered),
            "coverage_ratio": len(covered) / len(referenced) if referenced else 1.0,
            "uncovered_error_signatures": sorted(referenced - usable_templates),
            "usable_template_count": len(usable_templates),
        }
        pack = course_registry.get(course_id)
        course_pack_status[course_id] = {
            "implementation_status": pack.implementation_status,
            "supported_problem_type_count": len(pack.supported_problem_types),
            "verification_rule_count": len(pack.verification_rules),
            "legacy_yaml_present": (
                ROOT
                / "agent_configs"
                / "course_packs"
                / f"course_{course_id.lower()}_v1.yaml"
            ).is_file(),
        }
    return {
        "valid": True,
        "app_env": settings.app_env,
        "database": {
            "url": safe_status(settings.active_database_url, required=True),
        },
        "redis": {"url": safe_status(settings.redis_url, required=True)},
        "minio": {
            "endpoint": safe_status(settings.minio_endpoint, required=True),
            "credentials": (
                "configured"
                if settings.minio_access_key and settings.minio_secret_key
                else "missing"
            ),
        },
        "provider": {
            "requested": settings.default_agent_provider,
            "allow_mock_fallback": settings.allow_mock_fallback,
            "publication_status": "local_only",
            "runtime_configuration_required": False,
            "runtime_available": True,
        },
        "agents": [
            agent_status(agent, registry, settings)
            for agent in registry.list_agents()
        ],
        "uploads": {
            "max_size_mb": settings.max_upload_size_mb,
            "local_fallback": settings.local_storage_fallback,
            "local_path": str(settings.local_storage_path),
        },
        "knowledge": {
            "enabled": settings.knowledge_enabled,
            "sources": {
                course_id: "available" if path.is_dir() else "unavailable"
                for course_id, path in settings.knowledge_paths.items()
            },
            "chunk_size_chars": settings.knowledge_chunk_size_chars,
            "chunk_overlap_chars": settings.knowledge_chunk_overlap_chars,
            "default_top_k": settings.knowledge_default_top_k,
        },
        "teaching_foundation": {
            "supported_courses": list(teaching_courses),
            "skills": {
                course_id: len(skill_registry.list_for_course(course_id))
                for course_id in teaching_courses
            },
            "reviewed_error_templates": {
                course_id: len(error_pool_registry.list_for_course(course_id))
                for course_id in teaching_courses
            },
            "error_pool_coverage": error_pool_coverage,
            "course_packs": course_pack_status,
        },
        "teaching_loop_phase3": {
            "mastery_policy_version": str(learning_outcome.config["version"]),
            "calibration_status": learning_outcome.config["calibration_status"],
            "evidence_rules": len(
                learning_outcome.config["evidence_updates"]
            ),
            "active_scheduler": False,
            "feedback_uptake_model_enabled": False,
        },
    }


def main() -> int:
    if os.getenv("APP_ENV") is None:
        os.environ.setdefault("APP_ENV", "development")
    try:
        result = validate(Settings())
    except Exception as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
