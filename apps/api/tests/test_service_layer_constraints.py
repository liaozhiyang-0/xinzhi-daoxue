"""Structural constraints for the service layer (goal 4).

These are source-level contracts, not behavioral tests:

1. ``app/services`` modules form a DAG — no import cycles, so consolidation
   cannot silently introduce one.
2. Only the bootstrap wiring may import the task engine. A service that
   imports ``RuntimeTaskLifecycle`` would create a second entry point into
   task execution.
3. The engine's ``execute`` entry stays behind the coordinator: no module
   outside ``application/tasks`` may call it, preventing new parallel
   execution chains that bypass ``RuntimeTaskEngine``.
"""

from __future__ import annotations

import ast
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
SERVICES_DIR = APP_ROOT / "services"
BOOTSTRAP_DIR = APP_ROOT / "bootstrap"
COORDINATOR = APP_ROOT / "application" / "tasks" / "coordinator.py"

ENGINE_MODULE = "runtime_task_engine"
ENGINE_CLASS = "TaskRuntimeLifecycle"
ENGINE_EXECUTE = "engine.execute"
COORDINATOR_SUBMIT = "coordinator.submit"

ALLOWED_ENGINE_IMPORTERS = {
    # bootstrap wiring facade + the wiring module itself
    "bootstrap/__init__.py",
    "bootstrap/runtime_task_engine.py",
}


def _python_files(root: Path) -> list[Path]:
    return sorted(root.rglob("*.py"))


def _imported_services(path: Path) -> set[str]:
    """Return ``app.services.<name>`` module names imported by ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if len(parts) >= 3 and parts[:2] == ["app", "services"]:
                names.add(parts[2])
    return names


def _relative(path: Path) -> str:
    return path.relative_to(APP_ROOT).as_posix()


def _has_cycle(edges: dict[str, set[str]]) -> list[str] | None:
    """Return one cycle as a node list, or None if the graph is acyclic."""

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        stack.append(node)
        for neighbor in sorted(edges.get(node, ())):
            if color.get(neighbor, WHITE) == GRAY:
                cycle = stack[stack.index(neighbor) :] + [neighbor]
                return cycle
            if color.get(neighbor, WHITE) == BLACK:
                continue
            found = visit(neighbor)
            if found is not None:
                return found
        stack.pop()
        color[node] = BLACK
        return None

    for module in sorted(edges):
        if color.get(module, WHITE) == WHITE:
            found = visit(module)
            if found is not None:
                return found
    return None


def test_service_import_graph_is_acyclic() -> None:
    modules = {
        path.stem: path
        for path in SERVICES_DIR.glob("*.py")
        if path.stem != "__init__"
    }
    edges: dict[str, set[str]] = {}
    for name, path in modules.items():
        edges[name] = {
            dep
            for dep in _imported_services(path)
            if dep in modules and dep != name
        }
    cycle = _has_cycle(edges)
    assert cycle is None, f"service import cycle detected: {' -> '.join(cycle)}"


def test_only_bootstrap_may_import_the_task_engine() -> None:
    offenders: list[str] = []
    for path in _python_files(APP_ROOT):
        rel = _relative(path)
        if rel in ALLOWED_ENGINE_IMPORTERS:
            continue
        source = path.read_text(encoding="utf-8")
        if (
            f"import {ENGINE_MODULE}" in source
            or f"from app.services.{ENGINE_MODULE}" in source
            or f"import {ENGINE_CLASS}" in source
        ):
            offenders.append(rel)
    assert offenders == [], (
        "services must not import the task engine "
        f"(would create parallel execution entry points): {offenders}"
    )


def test_task_engine_is_constructed_only_by_bootstrap() -> None:
    constructors: list[str] = []
    for path in _python_files(APP_ROOT):
        source = path.read_text(encoding="utf-8")
        if f"{ENGINE_CLASS}(" in source:
            constructors.append(_relative(path))
    assert constructors == ["bootstrap/runtime_task_engine.py"], (
        f"TaskRuntimeLifecycle must be constructed only in bootstrap: {constructors}"
    )


def test_engine_execute_is_called_only_from_the_coordinator() -> None:
    offenders: list[str] = []
    for path in _python_files(APP_ROOT):
        rel = _relative(path)
        if rel == "application/tasks/coordinator.py":
            continue
        source = path.read_text(encoding="utf-8")
        if ENGINE_EXECUTE in source:
            offenders.append(rel)
    assert offenders == [], (
        "engine.execute must be reachable only through the coordinator "
        f"(no parallel execution chains): {offenders}"
    )


def test_coordinator_does_not_import_business_services() -> None:
    """The task dispatcher stays infrastructure-only.

    ``TaskExecutionCoordinator`` must not import any ``app.services.*``
    business module: execution enters exclusively through the
    ``TaskExecutionEngine`` protocol (implemented by ``TaskRuntimeLifecycle``),
    so no new parallel execution chain can be attached at the transport layer.
    """
    imported = _imported_services(COORDINATOR)
    assert imported == set(), (
        "coordinator must stay free of business-service imports; execution "
        f"must flow through the engine protocol only: {sorted(imported)}"
    )
