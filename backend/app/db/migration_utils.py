"""Utility helpers for running Alembic migrations programmatically.

Provides functions that the application can call at startup or from CLI
to ensure the database schema is up-to-date without shelling out to the
``alembic`` command.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine


# Path to the alembic.ini file relative to the backend directory
ALEMBIC_INI_PATH: Path = Path(__file__).resolve().parents[2] / "alembic.ini"

# Path to the alembic scripts directory
ALEMBIC_SCRIPT_PATH: Path = Path(__file__).resolve().parents[2] / "alembic"


def get_alembic_config(ini_path: Optional[Path] = None) -> "alembic.config.Config":  # noqa: F821
    """Build and return an ``alembic.config.Config`` instance.

    Args:
        ini_path: Optional override for the alembic.ini location.
                  Defaults to ``ALEMBIC_INI_PATH``.

    Returns:
        A configured ``alembic.config.Config`` ready for command invocation.
    """
    from alembic.config import Config

    path = ini_path or ALEMBIC_INI_PATH
    cfg = Config(str(path))
    cfg.set_main_option("script_location", str(ALEMBIC_SCRIPT_PATH))
    return cfg


async def run_migrations_on_startup(
    app_engine: AsyncEngine,
    articles_engine: AsyncEngine,
) -> None:
    """Run pending Alembic migrations for both databases at application startup.

    This is intended to be called from the FastAPI ``lifespan`` handler so that
    schema changes are applied automatically when the server boots.

    Args:
        app_engine: The async engine connected to the App database.
        articles_engine: The async engine connected to the Articles database.
    """
    from alembic import command

    cfg = get_alembic_config()

    # Run migrations for the App database
    async with app_engine.connect() as conn:
        await conn.run_sync(
            lambda c: command.upgrade(cfg, "head")
        )

    # Run migrations for the Articles database
    async with articles_engine.connect() as conn:
        await conn.run_sync(
            lambda c: command.upgrade(cfg, "head")
        )


def get_current_revision(engine_url: str) -> Optional[str]:
    """Return the current Alembic revision for the given database URL.

    Args:
        engine_url: SQLAlchemy connection string.

    Returns:
        The revision identifier string, or ``None`` if the database
        has not been stamped.
    """
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    engine = create_engine(engine_url)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        return ctx.get_current_revision()


def check_pending_migrations(engine_url: str) -> bool:
    """Check whether there are pending (unapplied) migrations.

    Args:
        engine_url: SQLAlchemy connection string.

    Returns:
        ``True`` if there are migrations that have not yet been applied.
    """
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine

    cfg = get_alembic_config()
    script = ScriptDirectory.from_config(cfg)
    engine = create_engine(engine_url)

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        current = ctx.get_current_revision()
        head = script.get_current_head()

    if head is None:
        return False
    if current is None:
        return True
    return current != head


def _upgrade_sync(conn, cfg, target: str) -> None:
    """Synchronous helper: run alembic upgrade to *target* on an existing connection."""
    from alembic import command
    cfg.attributes["connection"] = conn
    command.upgrade(cfg, target)


async def run_migrations_for_engine(
    engine: AsyncEngine,
    version_table: str = "alembic_version",
    target: str = "20260402_0003",
) -> None:
    """Run pending Alembic migrations for a specific engine.

    Args:
        engine: The async engine to run migrations against.
        version_table: The name of the alembic version table.
        target: Alembic revision target (default: the latest dated migration chain head).
    """
    cfg = get_alembic_config()
    cfg.set_main_option("version_table", version_table)

    async with engine.connect() as conn:
        await conn.run_sync(_upgrade_sync, cfg, target)


async def run_migrations_for_url(
    database_url: str,
    version_table: str = "alembic_version",
) -> None:
    """Run pending Alembic migrations for a specific database URL.

    This is useful for testing when you need to run migrations
    against a specific database URL (e.g., in-memory SQLite).

    Args:
        database_url: SQLAlchemy connection string.
        version_table: The name of the alembic version table.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url)
    try:
        await run_migrations_for_engine(engine, version_table)
    finally:
        await engine.dispose()
