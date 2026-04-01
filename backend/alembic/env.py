import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import models and bases
from app.db.base import AppBase, ArticleBase
from app.db.session import APP_ENGINE, ARTICLES_ENGINE
import app.models  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Define metadata for each database
app_metadata = AppBase.metadata
article_metadata = ArticleBase.metadata

# Store the original run_migrations_online function
original_run_migrations_online = None

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.
    
    For dual databases, we need to handle each separately.
    """
    # Get database URLs from environment
    import os
    app_db_url = os.environ.get('APP_DATABASE_URL', 'sqlite:///./app.db')
    articles_db_url = os.environ.get('ARTICLES_DATABASE_URL', 'sqlite:///./articles.db')
    
    # Configure for app database
    context.configure(
        url=app_db_url,
        target_metadata=app_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table='alembic_version_app',
    )
    
    with context.begin_transaction():
        context.run_migrations()
    
    # Configure for articles database
    context.configure(
        url=articles_db_url,
        target_metadata=article_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table='alembic_version_articles',
    )
    
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations_app(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=app_metadata,
        version_table='alembic_version_app',
    )
    
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations_articles(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=article_metadata,
        version_table='alembic_version_articles',
    )
    
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """Run migrations for both databases asynchronously."""
    import os
    
    # Get database URLs from environment
    app_db_url = os.environ.get('APP_DATABASE_URL', 'sqlite:///./app.db')
    articles_db_url = os.environ.get('ARTICLES_DATABASE_URL', 'sqlite:///./articles.db')
    
    # Create engines for both databases
    app_connectable = async_engine_from_config(
        {'sqlalchemy.url': app_db_url},
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    
    articles_connectable = async_engine_from_config(
        {'sqlalchemy.url': articles_db_url},
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    
    # Run migrations for app database
    async with app_connectable.connect() as connection:
        await connection.run_sync(do_run_migrations_app)
    
    # Run migrations for articles database
    async with articles_connectable.connect() as connection:
        await connection.run_sync(do_run_migrations_articles)
    
    await app_connectable.dispose()
    await articles_connectable.dispose()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()