"""
FastAPI application entry point for the Habr Agentic Pipeline backend.

This module is the uvicorn entry point.  It imports the application factory
and creates the app instance.  All configuration, middleware, router
registration, and lifespan management are delegated to ``app.factory``.

Usage::

    uvicorn app.main:app --reload --port 8000

Or via the convenience script::

    ./run.sh
"""

from app.factory import create_app

app = create_app()
