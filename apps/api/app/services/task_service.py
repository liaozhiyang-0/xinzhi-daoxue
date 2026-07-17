"""Compatibility facade for code that previously imported TaskService."""

from app.services.task_query_service import TaskQueryService as TaskService

__all__ = ["TaskService"]
