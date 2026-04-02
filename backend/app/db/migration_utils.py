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
    cfg = alembic.config.Config(str(path))
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
    import alembic.command
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    cfg = get_alembic_config()
    script = ScriptDirectory.from_config(cfg)

    async def _run_migrations(engine: AsyncEngine, branch_label: str) -> None:
        async with engine.begin() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            head_rev = script.get_current_head(branch_label)

            if current_rev == head_rev:
                return  # Already up to date

            # Run upgrade programmatically
            cfg.set_main_option("sqlalchemy.url", str(engine.url))
            alembic.command.upgrade(cfg, f"{branch_label}@head")

    await _run_migrations(app_engine, "app")
    await _run_migrations(articles_engine, "articles")


def get_current_revision(engine_url: str) -> Optional[str]:
    """Return the current Alembic revision for the given database URL.

    Args:
        engine_url: SQLAlchemy connection string.

    Returns:
        The revision identifier string, or ``None`` if the database
        has not been stamped.
    """
    import alembic.config
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine, text

    cfg = get_alembic_config()
    cfg.set_main_option("sqlalchemy.url", engine_url)

    engine = create_engine(engine_url)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            return context.get_current_revision()
    finally:
        engine.dispose()


def check_pending_migrations(engine_url: str) -> bool:
    """Check whether there are pending (unapplied) migrations.

    Args:
        engine_url: SQLAlchemy connection string.

    Returns:
        ``True`` if there are migrations that have not yet been applied.
    """
    from alembic.script import ScriptDirectory
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    cfg = get_alembic_config()
    cfg.set_main_option("sqlalchemy.url", engine_url)
    script = ScriptDirectory.from_config(cfg)

    engine = create_engine(engine_url)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            head_rev = script.get_current_head()
            return current_rev != head_rev
    finally:
        engine.dispose()
