"""The immutable production execution surface.

The manifest is policy, not another Runtime.  It records which already-built
components may participate in the active chain and provides the final
fail-closed checks used by task preparation, plan execution and recovery.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ExecutionSurfaceError(RuntimeError):
    """A task or plan attempted to cross the active execution surface."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


class LegacyExecutionForbidden(ExecutionSurfaceError):
    """Raised when a quarantined executable is reached from production."""

    def __init__(self, component: str, *, caller: str = "") -> None:
        self.component = component
        self.caller = caller
        super().__init__(
            "LEGACY_EXECUTION_FORBIDDEN",
            f"quarantined execution target is forbidden: {component}"
            + (f" caller={caller}" if caller else ""),
        )


def _digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def resolve_build_id(
    *,
    explicit: str | None = None,
    project_root: Path | None = None,
) -> str:
    """Resolve a restart-stable build identity without reading secrets."""

    configured = explicit or os.getenv("XZD_BUILD_ID") or os.getenv("GIT_SHA")
    if configured and configured.strip():
        return configured.strip()
    root = project_root or Path(__file__).resolve().parents[4]
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        if not sha:
            return "local-dev"
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout.strip()
        return f"{sha}-dirty" if dirty else sha
    except (OSError, subprocess.SubprocessError):
        return "local-dev"


@dataclass(frozen=True, slots=True)
class ProductionExecutionManifest:
    active_ingress: str
    active_planner: str
    active_runtime_engine: str
    active_plan_version: str
    planner_version: str
    active_handler_ids: tuple[str, ...]
    active_handler_prefixes: tuple[str, ...]
    active_capabilities: tuple[str, ...]
    active_tool_ids: tuple[str, ...]
    active_provider_modes: tuple[str, ...]
    runtime_generation: str
    build_id: str
    forbidden_runtime_ids: tuple[str, ...]
    forbidden_router_ids: tuple[str, ...]
    forbidden_handler_ids: tuple[str, ...]
    forbidden_workflow_ids: tuple[str, ...]

    # Several current business runtimes own a per-run handler registry.  They
    # are still part of the one production surface, but their descriptors are
    # not present in the composition-root registry.  Keep this list explicit
    # so the final gate recognizes all existing active capabilities without
    # admitting arbitrary or historical namespaces.
    _ACTIVE_RUNTIME_HANDLER_PREFIXES = (
        "academic.solver.",
        "academic.writing.",
        "assignment.review.",
        "general.model_fallback.",
        "general.question.",
        "knowledge.qa.",
        "learning.progress.",
        "lesson.prep.",
        "research.analysis.",
        "research.external.",
        "teaching.feedback.",
    )

    @classmethod
    def build(
        cls,
        *,
        planner_version: str,
        capability_bindings: Iterable[Any],
        tool_registry: Any,
        runtime_handler_registry: Any,
        business_services: Iterable[Any],
        provider_mode: str,
        runtime_generation: str = "runtime-v3",
        canonical_plan_version: str = "canonical-v1",
        build_id: str | None = None,
        project_root: Path | None = None,
    ) -> ProductionExecutionManifest:
        active_handlers: set[str] = set()
        handler_prefixes: set[str] = {
            "subagent.",
            *cls._ACTIVE_RUNTIME_HANDLER_PREFIXES,
        }
        forbidden_handlers = {"provider.default", "agent.internal"}

        for descriptor in runtime_handler_registry.descriptors():
            handler_id = str(descriptor.handler_id).strip()
            if handler_id and handler_id not in forbidden_handlers:
                active_handlers.add(handler_id)

        active_capabilities: set[str] = set()
        for binding in capability_bindings:
            capability_id = str(getattr(binding, "capability_id", "")).strip()
            handler_id = str(getattr(binding, "handler_id", "")).strip()
            if capability_id:
                active_capabilities.add(capability_id)
            if handler_id:
                active_handlers.add(handler_id)

        active_tools: set[str] = set()
        for definition in tool_registry.list_tools():
            tool_id = str(definition.tool_id).strip()
            if tool_id and definition.enabled:
                active_tools.add(tool_id)
                active_handlers.add(f"tool.{tool_id}")

        for service in business_services:
            for attribute in dir(service):
                if not attribute.endswith("_handler_id"):
                    continue
                value = getattr(service, attribute, "")
                if isinstance(value, str) and value.strip():
                    active_handlers.add(value.strip())
            prefix = getattr(service, "tool_handler_prefix", "")
            if isinstance(prefix, str) and prefix.strip():
                handler_prefixes.add(prefix.strip() + ".")

        manifest = cls(
            active_ingress="unified-http-v1",
            active_planner="PlannerService",
            active_runtime_engine="TaskExecutionCoordinator.RuntimeTaskEngine",
            active_plan_version=canonical_plan_version,
            planner_version=planner_version,
            active_handler_ids=tuple(sorted(active_handlers)),
            active_handler_prefixes=tuple(sorted(handler_prefixes)),
            active_capabilities=tuple(sorted(active_capabilities)),
            active_tool_ids=tuple(sorted(active_tools)),
            active_provider_modes=tuple(
                sorted(
                    {
                        str(provider_mode).strip(),
                        "local_agent",
                        "external_retrieval",
                    }
                    - {""}
                )
            ),
            runtime_generation=runtime_generation,
            build_id=resolve_build_id(explicit=build_id, project_root=project_root),
            forbidden_runtime_ids=("legacy-runtime", "legacy_runtime", "old-runtime"),
            forbidden_router_ids=(
                "overall_router",
                "fallback_router",
                "legacy_router",
            ),
            forbidden_handler_ids=tuple(sorted(forbidden_handlers)),
            forbidden_workflow_ids=(
                "legacy-workflow",
                "legacy_workflow",
                "old-workflow",
            ),
        )
        manifest.validate_bootstrap()
        return manifest

    @property
    def active_handler_hash(self) -> str:
        return _digest(
            {
                "ids": self.active_handler_ids,
                "prefixes": self.active_handler_prefixes,
            }
        )

    @property
    def active_capability_hash(self) -> str:
        return _digest(self.active_capabilities)

    @property
    def active_tool_hash(self) -> str:
        return _digest(self.active_tool_ids)

    @property
    def development_compatibility_enabled(self) -> bool:
        """Allow the pre-freeze test harness to exercise Mock-only paths.

        Production configuration rejects the Mock provider, so this marker
        cannot enable the compatibility path in a production deployment.
        Keeping the decision on the manifest makes the exception explicit at
        each boundary instead of weakening the production surface globally.
        """

        return "mock" in self.active_provider_modes

    @property
    def fingerprint(self) -> str:
        return _digest(self.identity_payload())

    def identity_payload(self) -> dict[str, Any]:
        return {
            "build_id": self.build_id,
            "runtime_generation": self.runtime_generation,
            "planner_version": self.planner_version,
            "active_plan_version": self.active_plan_version,
            "active_handler_hash": self.active_handler_hash,
            "active_capability_hash": self.active_capability_hash,
            "active_tool_hash": self.active_tool_hash,
            "active_ingress": self.active_ingress,
            "active_planner": self.active_planner,
            "active_runtime_engine": self.active_runtime_engine,
        }

    def envelope(self) -> dict[str, str]:
        return {
            "runtime_generation": self.runtime_generation,
            "build_id": self.build_id,
            "planner_version": self.planner_version,
            "canonical_plan_version": self.active_plan_version,
            "handler_binding_version": self.active_handler_hash,
            "capability_binding_version": self.active_capability_hash,
            "startup_fingerprint": self.fingerprint,
        }

    def validate_bootstrap(self) -> None:
        if self.active_planner != "PlannerService":
            raise ExecutionSurfaceError("ACTIVE_PLANNER_OWNER_INVALID")
        if not self.active_runtime_engine:
            raise ExecutionSurfaceError("ACTIVE_RUNTIME_OWNER_MISSING")
        if not self.runtime_generation.strip():
            raise ExecutionSurfaceError("RUNTIME_GENERATION_MISSING")
        if not self.active_plan_version.strip():
            raise ExecutionSurfaceError("CANONICAL_PLAN_VERSION_MISSING")
        if not self.active_handler_ids:
            raise ExecutionSurfaceError("ACTIVE_HANDLER_ALLOWLIST_EMPTY")
        forbidden = set(self.active_handler_ids).intersection(
            self.forbidden_handler_ids
        )
        if forbidden:
            raise LegacyExecutionForbidden(
                ",".join(sorted(forbidden)),
                caller="manifest",
            )

    def handler_allowed(self, handler_id: str) -> bool:
        candidate = str(handler_id).strip()
        if not candidate:
            return False
        if candidate in self.forbidden_handler_ids:
            return False
        if any(candidate.startswith(prefix) for prefix in self.forbidden_runtime_ids):
            return False
        return candidate in self.active_handler_ids or any(
            candidate.startswith(prefix) for prefix in self.active_handler_prefixes
        )

    def validate_handler(self, handler_id: str, *, caller: str = "") -> None:
        candidate = str(handler_id).strip()
        if candidate in self.forbidden_handler_ids or any(
            candidate.startswith(prefix) for prefix in self.forbidden_runtime_ids
        ):
            raise LegacyExecutionForbidden(candidate, caller=caller)
        if not self.handler_allowed(candidate):
            raise ExecutionSurfaceError(
                "EXECUTION_TARGET_NOT_ACTIVE",
                f"handler is not active: {candidate}",
            )

    def validate_runtime_plan(self, plan: Any, *, caller: str = "") -> None:
        plan_id = str(getattr(plan, "plan_id", ""))
        if any(plan_id.startswith(prefix) for prefix in self.forbidden_runtime_ids):
            raise LegacyExecutionForbidden(plan_id, caller=caller)
        version = str(getattr(plan, "version", ""))
        if version.startswith("compat-") or version.startswith("legacy-"):
            raise LegacyExecutionForbidden(version, caller=caller)
        for node in getattr(plan, "nodes", ()):
            self.validate_handler(getattr(node, "handler_id", ""), caller=caller)

    def validate_canonical_plan(self, plan: Any, *, caller: str = "") -> None:
        version = str(getattr(plan, "version", ""))
        if version != self.active_plan_version:
            raise ExecutionSurfaceError(
                "CANONICAL_PLAN_VERSION_NOT_ACTIVE",
                f"canonical plan version is not active: {version}",
            )
        for binding in getattr(plan, "capability_bindings", ()):
            handler_id = str(getattr(binding, "handler_id", ""))
            self.validate_handler(handler_id, caller=caller)

    def validate_task_envelope(
        self,
        input_content: Mapping[str, Any],
        *,
        allow_missing: bool = False,
    ) -> None:
        options = input_content.get("options", {})
        surface = (
            options.get("_execution_surface")
            if isinstance(options, Mapping)
            else None
        )
        if not isinstance(surface, Mapping):
            if allow_missing:
                return
            raise ExecutionSurfaceError(
                "EXECUTION_SURFACE_METADATA_MISSING",
                "task has no production execution-surface metadata",
            )
        expected = self.envelope()
        for key in (
            "runtime_generation",
            "planner_version",
            "canonical_plan_version",
        ):
            if str(surface.get(key, "")) != expected[key]:
                raise ExecutionSurfaceError(
                    "EXECUTION_SURFACE_NOT_CURRENT",
                    f"task {key} does not match the active manifest",
                )

    def task_metadata(self) -> dict[str, str]:
        return dict(self.envelope())
