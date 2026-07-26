"""Archived compatibility facade for the retired ``TaskService`` import.

This module is retained only for historical reference.  Active code imports
``TaskQueryService`` directly and ``archive_legacy`` is not on the application
package path.
"""

from app.services.task_query_service import TaskQueryService as TaskService

__all__ = ["TaskService"]
