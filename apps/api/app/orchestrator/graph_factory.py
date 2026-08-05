from __future__ import annotations

from typing import Any

from app.capabilities import CapabilityRegistry
from app.courses import CourseRegistry
from app.orchestrator.graphs import AcademicProblemSolverGraph
from app.tools import ToolRegistry


class GraphFactory:
    """Creates graphs from shared dependencies; graphs never open resources."""

    def __init__(
        self,
        *,
        courses: CourseRegistry,
        capabilities: CapabilityRegistry,
        tools: ToolRegistry,
        model_service: Any = None,
        rag_service: Any = None,
        checkpointer: Any = None,
    ) -> None:
        self.courses = courses
        self.capabilities = capabilities
        self.tools = tools
        self.model_service = model_service
        self.rag_service = rag_service
        self.checkpointer = checkpointer

    def create(self, graph_name: str) -> Any:
        if graph_name == AcademicProblemSolverGraph.graph_name:
            return AcademicProblemSolverGraph(
                self.courses,
                self.capabilities,
                self.tools,
                checkpointer=self.checkpointer,
            )
        raise KeyError(f"未注册任务图: {graph_name}")

    def available_graphs(self) -> list[str]:
        return [AcademicProblemSolverGraph.graph_name]
