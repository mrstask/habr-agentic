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


def get_alembic_config(ini_path: Optional[Path] = None) -> "alembic.config.Config":
    """Build and return an ``alembic.config.Config`` instance.

    Args:
        ini_path: Optional override for the alembic.ini location.
                  Defaults to ``ALEMBIC_INI_PATH``.

    Returns:
        A configured ``alembic.config.Config`` ready for command invocation.
    """
    import alembic.config

    path = ini_path or ALEMBIC_INI_PATH
    config = alembic.config.Config(str(path))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_PATH))
    return config


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
    import alembic.command
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    config = get_alembic_config()

    # Run migrations for the App database
    async with app_engine.begin() as conn:
        await conn.run_sync(
            lambda c: alembic.command.upgrade(
                get_alembic_config(), "head", sql=False
            )
        )

    # Run migrations for the Articles database
    async with articles_engine.begin() as conn:
        await conn.run_sync(
            lambda c: alembic.command.upgrade(
                get_alembic_config(), "head", sql=False
            )
        )


def get_current_revision(engine_url: str) -> Optional[str]:
    """Return the current Alembic revision for the given database URL.

    Args:
        engine_url: SQLAlchemy connection string.

    Returns:
        The revision identifier string, or ``None`` if the database
        has not been stamped.
    """
    import alembic.runtime.migration
    from sqlalchemy import create_engine

    engine = create_engine(engine_url)
    with engine.connect() as conn:
        context = alembic.runtime.migration.MigrationContext.configure(conn)
        return context.get_current_revision()


def check_pending_migrations(engine_url: str) -> bool:
    """Check whether there are pending (unapplied) migrations.

    Args:
        engine_url: SQLAlchemy connection string.

    Returns:
        ``True`` if there are migrations that have not yet been applied.
    """
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine
    import alembic.runtime.migration

    config = get_alembic_config()
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()

    engine = create_engine(engine_url)
    with engine.connect() as conn:
        context = alembic.runtime.migration.MigrationContext.configure(conn)
        current = context.get_current_revision()

    return current != head
