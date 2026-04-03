"""
API routes package for the Habr Agentic Pipeline backend.

This package contains all FastAPI route modules organized by domain:
- articles: Article CRUD and listing operations
- pipeline: Pipeline run management and control
- admin: Admin user authentication and management
- settings: Application and agent configuration
"""

from app.api.routes.articles import router as articles_router
from app.api.routes.pipeline import router as pipeline_router
from app.api.routes.admin import router as admin_router
from app.api.routes.settings import router as settings_router

__all__ = [
    "articles_router",
    "pipeline_router",
    "admin_router",
    "settings_router",
]
