"""
API package for the Habr Agentic Pipeline backend.

This package contains all FastAPI routes and API-related modules.
"""

from app.api.routes import articles_router, pipeline_router, admin_router, settings_router

__all__ = [
    "articles_router",
    "pipeline_router",
    "admin_router",
    "settings_router",
]
