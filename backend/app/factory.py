"""
FastAPI application factory module.

Provides the ``create_app`` factory function that constructs and configures
the FastAPI application instance.  This pattern enables:

* Clean separation of app creation from module-level imports
* Easier testing (each test gets a fresh app instance)
* Conditional configuration based on environment
* Proper lifespan management for startup/shutdown events

Usage::

    from app.factory import create_app
    app = create_app()

For development, the ``main.py`` module calls ``create_app()`` and exposes
the ``app`` variable for uvicorn.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db.session import APP_ENGINE, ARTICLES_ENGINE
from app.db.migration_utils import run_migrations_on_startup
from app.models import Base  # noqa: F401 — ensures all models are registered with metadata


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager for startup and shutdown events.

    **Startup sequence:**
    1. Run database migrations on both App and Articles databases
    2. Seed default agent configuration if the table is empty
    3. Start the pipeline scheduler if ``AGENT_ENABLED`` is True

    **Shutdown sequence:**
    1. Stop the pipeline scheduler gracefully
    2. Dispose of all database engine connections

    Args:
        app: The FastAPI application instance.

    Yields:
        None: Control returns to FastAPI after startup; shutdown runs after yield.
    """
    # ---- Startup ----
    print("🚀 Starting Habr Agentic Pipeline backend...")

    # Run migrations on startup
    print("📦 Running database migrations...")
    await run_migrations_on_startup(APP_ENGINE, ARTICLES_ENGINE)
    print("✅ Migrations completed")

    # Seed default agent configuration
    print("🌱 Seeding agent configuration defaults...")
    # TODO: Implement agent config seeding — query agent_configs table,
    # TODO: insert default rows if table is empty (AGENT_ENABLED, AGENT_DRY_RUN, etc.)

    # Start pipeline scheduler if enabled
    if settings.AGENT_ENABLED:
        print("🤖 Starting pipeline scheduler...")
        # TODO: Implement pipeline scheduler startup — create background task
        # TODO: that periodically polls for articles in DISCOVERED status
        # TODO: and launches LangGraph pipeline runs for each
    else:
        print("⏸️  Pipeline scheduler disabled (AGENT_ENABLED=False)")

    print("✅ Backend startup complete")

    yield  # FastAPI runs the application here

    # ---- Shutdown ----
    print("🛑 Shutting down backend...")

    # Stop pipeline scheduler
    if settings.AGENT_ENABLED:
        print("🛑 Stopping pipeline scheduler...")
        # TODO: Implement pipeline scheduler shutdown — signal background task
        # TODO: to stop, wait for in-progress runs to finish or cancel them

    # Close database connections
    print("🔌 Closing database connections...")
    await APP_ENGINE.dispose()
    await ARTICLES_ENGINE.dispose()

    print("✅ Backend shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    This factory function:
    1. Creates the FastAPI app with metadata and lifespan
    2. Configures CORS middleware
    3. Registers all API routers under the /api/v1 prefix
    4. Sets up global error handlers

    Returns:
        FastAPI: A fully configured application instance ready to serve requests.
    """
    app = FastAPI(
        title="Habr Agentic Pipeline API",
        description=(
            "Autonomous Russian → Ukrainian article translation pipeline "
            "with LangGraph orchestration."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.APP_DEBUG else None,
        redoc_url="/redoc" if settings.APP_DEBUG else None,
    )

    # Configure CORS middleware
    _configure_cors(app)

    # Register API routers
    _register_routers(app)

    # Register error handlers
    _register_error_handlers(app)

    # Register utility endpoints
    _register_utility_endpoints(app)

    return app


def _configure_cors(app: FastAPI) -> None:
    """
    Configure CORS middleware for the FastAPI application.

    Sets allowed origins, credentials, methods, and headers based on
    the application settings.

    Args:
        app: The FastAPI application instance to configure.
    """
    # TODO: Review CORS settings for production — consider restricting origins
    # TODO: Add logging for CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _register_routers(app: FastAPI) -> None:
    """
    Register all API routers with the FastAPI application.

    All routers are mounted under the /api/v1 prefix for versioning.

    Args:
        app: The FastAPI application instance to register routers with.
    """
    from app.api.routes import articles_router, pipeline_router, admin_router, settings_router

    # TODO: Consider adding router prefix configuration to settings
    # TODO: Add API versioning strategy (e.g., /api/v2 in the future)
    app.include_router(articles_router, prefix="/api/v1")
    app.include_router(pipeline_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")


def _register_error_handlers(app: FastAPI) -> None:
    """
    Register global error handlers for the FastAPI application.

    Sets up handlers for uncaught exceptions and HTTP validation errors.

    Args:
        app: The FastAPI application instance to register handlers with.
    """
    # TODO: Implement structured logging for all errors
    # TODO: Add request ID tracking for error correlation
    # TODO: Consider adding custom handlers for specific exception types
    # TODO: (e.g., SQLAlchemy errors, LLM API errors, etc.)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        Global exception handler for uncaught errors.

        Args:
            request: The request that caused the exception.
            exc: The exception that was raised.

        Returns:
            JSONResponse: Error response with appropriate status code.
        """
        # TODO: Implement proper error logging with traceback
        # TODO: Add error tracking integration (e.g., Sentry)
        # TODO: Sanitize error messages for production (no stack traces)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if settings.APP_DEBUG else None,
            },
        )


def _register_utility_endpoints(app: FastAPI) -> None:
    """
    Register utility endpoints (health check, root info) with the application.

    Args:
        app: The FastAPI application instance to register endpoints with.
    """

    @app.get("/health")
    async def health_check() -> JSONResponse:
        """
        Health check endpoint for monitoring and load balancers.

        Returns:
            JSONResponse: Status indicating the API is healthy and ready.
        """
        # TODO: Add database connectivity check to health endpoint
        # TODO: Add pipeline status to health check
        # TODO: Consider adding readiness vs liveness probes
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "app_env": settings.APP_ENV,
                "agent_enabled": settings.AGENT_ENABLED,
                "agent_dry_run": settings.AGENT_DRY_RUN,
            },
        )

    @app.get("/")
    async def root() -> JSONResponse:
        """
        Root endpoint providing API information.

        Returns:
            JSONResponse: API metadata and welcome message.
        """
        return JSONResponse(
            status_code=200,
            content={
                "message": "Habr Agentic Pipeline API",
                "version": "0.1.0",
                "docs": "/docs" if settings.APP_DEBUG else None,
            },
        )
