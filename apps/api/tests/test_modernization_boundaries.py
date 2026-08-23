from __future__ import annotations


def test_moved_task_services_have_one_canonical_owner() -> None:
    from app.application.tasks.progress import TaskProgressReporter
    from app.application.tasks.query import TaskQueryService
    from app.services.task_progress import TaskProgressReporter as LegacyProgress
    from app.services.task_query_service import TaskQueryService as LegacyQuery

    assert LegacyProgress is TaskProgressReporter
    assert LegacyQuery is TaskQueryService


def test_runtime_adapter_compatibility_facade_is_thin() -> None:
    from app.infrastructure.runtime_adapters import (
        build_runtime_handler_registry,
        register_subagent_handlers,
    )
    from app.runtime.adapters import (
        build_runtime_handler_registry as LegacyRegistry,
    )
    from app.runtime.adapters import (
        register_subagent_handlers as LegacySubagents,
    )

    assert LegacyRegistry is build_runtime_handler_registry
    assert LegacySubagents is register_subagent_handlers
