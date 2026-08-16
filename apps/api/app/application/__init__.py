"""Application-layer use cases.

This package owns orchestration across domain and infrastructure boundaries.
It must not contain Agent-specific routing, retrieval, or provider logic.
"""
from app.application.container import ApplicationContainer

__all__ = ["ApplicationContainer"]
