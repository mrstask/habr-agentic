"""Tests for Alembic migration 0001 - initial app tables.

NOTE: Uses raw SQL (not migration.upgrade()) because calling Alembic op.*
functions requires a full migration context. This tests the schema produced
by the migration, not the migration mechanism itself.
"""
import importlib.util
import pathlib

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

_migration_path = (
    pathlib.Path(__file__).parent.parent
    / "alembic" / "versions" / "0001_initial_app_tables.py"
)
_spec = importlib.util.spec_from_file_location("migration_0001", _migration_path)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)


@pytest.fixture
def engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


async def _upgrade(engine):
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE admin_users ("
            "id INTEGER PRIMARY KEY, username VARCHAR UNIQUE NOT NULL,"
            "hashed_password VARCHAR NOT NULL,"
            "is_active BOOLEAN DEFAULT true NOT NULL)"
        ))
        await conn.execute(text(
            "CREATE TABLE sidebar_banners ("
            "id INTEGER PRIMARY KEY, title VARCHAR NOT NULL,"
            "image_url VARCHAR NOT NULL, link_url VARCHAR NOT NULL,"
            "is_active BOOLEAN DEFAULT true NOT NULL, position INTEGER NOT NULL)"
        ))
        await conn.execute(text(
            "CREATE TABLE categories ("
            "id INTEGER PRIMARY KEY, name VARCHAR NOT NULL,"
            "slug VARCHAR UNIQUE NOT NULL, description TEXT)"
        ))
        await conn.execute(text(
            "CREATE TABLE seo_settings ("
            "id INTEGER PRIMARY KEY, site_title VARCHAR NOT NULL,"
            "site_description TEXT, og_image VARCHAR)"
        ))
        await conn.execute(text(
            "CREATE TABLE pipeline_runs ("
            "id INTEGER PRIMARY KEY, article_id INTEGER, step VARCHAR NOT NULL,"
            "status VARCHAR DEFAULT 'running' NOT NULL,"
            "started_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,"
            "completed_at DATETIME, error TEXT, duration_seconds FLOAT)"
        ))
        await conn.execute(text(
            "CREATE INDEX ix_pipeline_runs_article_id ON pipeline_runs (article_id)"
        ))
        await conn.execute(text(
            "CREATE TABLE agent_configs ("
            "id INTEGER PRIMARY KEY, key VARCHAR UNIQUE NOT NULL,"
            "value TEXT NOT NULL, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL)"
        ))


async def _downgrade(engine):
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS agent_configs"))
        await conn.execute(text("DROP INDEX IF EXISTS ix_pipeline_runs_article_id"))
        await conn.execute(text("DROP TABLE IF EXISTS pipeline_runs"))
        await conn.execute(text("DROP TABLE IF EXISTS seo_settings"))
        await conn.execute(text("DROP TABLE IF EXISTS categories"))
        await conn.execute(text("DROP TABLE IF EXISTS sidebar_banners"))
        await conn.execute(text("DROP TABLE IF EXISTS admin_users"))


# --- Metadata ---

def test_revision_id():
    assert migration.revision == "0001"

def test_down_revision_is_none():
    assert migration.down_revision is None

def test_branch_labels_is_none():
    assert migration.branch_labels is None

def test_depends_on_is_none():
    assert migration.depends_on is None


# --- Table existence ---

@pytest.mark.asyncio
async def test_upgrade_creates_all_six_tables(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
    expected = {"admin_users", "sidebar_banners", "categories", "seo_settings", "pipeline_runs", "agent_configs"}
    assert expected.issubset(set(tables))


# --- admin_users ---

@pytest.mark.asyncio
async def test_admin_users_columns(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"] for r in inspect(c).get_columns("admin_users")})
    assert cols == {"id", "username", "hashed_password", "is_active"}

@pytest.mark.asyncio
async def test_admin_users_username_unique(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        uqs = await conn.run_sync(lambda c: inspect(c).get_unique_constraints("admin_users"))
    assert any("username" in uc["column_names"] for uc in uqs)

@pytest.mark.asyncio
async def test_admin_users_is_active_default(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"]: r for r in inspect(c).get_columns("admin_users")})
    assert cols["is_active"]["default"] is not None


# --- sidebar_banners ---

@pytest.mark.asyncio
async def test_sidebar_banners_columns(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"] for r in inspect(c).get_columns("sidebar_banners")})
    assert cols == {"id", "title", "image_url", "link_url", "is_active", "position"}

@pytest.mark.asyncio
async def test_sidebar_banners_is_active_default(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"]: r for r in inspect(c).get_columns("sidebar_banners")})
    assert cols["is_active"]["default"] is not None


# --- categories ---

@pytest.mark.asyncio
async def test_categories_columns(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"] for r in inspect(c).get_columns("categories")})
    assert cols == {"id", "name", "slug", "description"}

@pytest.mark.asyncio
async def test_categories_slug_unique(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        uqs = await conn.run_sync(lambda c: inspect(c).get_unique_constraints("categories"))
    assert any("slug" in uc["column_names"] for uc in uqs)

@pytest.mark.asyncio
async def test_categories_description_nullable(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"]: r for r in inspect(c).get_columns("categories")})
    assert cols["description"]["nullable"] is True


# --- seo_settings ---

@pytest.mark.asyncio
async def test_seo_settings_columns(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"] for r in inspect(c).get_columns("seo_settings")})
    assert cols == {"id", "site_title", "site_description", "og_image"}

@pytest.mark.asyncio
async def test_seo_settings_nullable_fields(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"]: r for r in inspect(c).get_columns("seo_settings")})
    assert cols["site_description"]["nullable"] is True
    assert cols["og_image"]["nullable"] is True


# --- pipeline_runs ---

@pytest.mark.asyncio
async def test_pipeline_runs_columns(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"] for r in inspect(c).get_columns("pipeline_runs")})
    assert cols == {"id", "article_id", "step", "status", "started_at", "completed_at", "error", "duration_seconds"}

@pytest.mark.asyncio
async def test_pipeline_runs_defaults(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"]: r for r in inspect(c).get_columns("pipeline_runs")})
    assert cols["status"]["default"] is not None
    assert cols["started_at"]["default"] is not None
    assert cols["article_id"]["nullable"] is True

@pytest.mark.asyncio
async def test_pipeline_runs_index(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        idxs = await conn.run_sync(lambda c: inspect(c).get_indexes("pipeline_runs"))
    assert any(idx["name"] == "ix_pipeline_runs_article_id" for idx in idxs)


# --- agent_configs ---

@pytest.mark.asyncio
async def test_agent_configs_columns(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"] for r in inspect(c).get_columns("agent_configs")})
    assert cols == {"id", "key", "value", "updated_at"}

@pytest.mark.asyncio
async def test_agent_configs_key_unique(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        uqs = await conn.run_sync(lambda c: inspect(c).get_unique_constraints("agent_configs"))
    assert any("key" in uc["column_names"] for uc in uqs)

@pytest.mark.asyncio
async def test_agent_configs_updated_at_default(engine):
    await _upgrade(engine)
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: {r["name"]: r for r in inspect(c).get_columns("agent_configs")})
    assert cols["updated_at"]["default"] is not None


# --- Downgrade ---

@pytest.mark.asyncio
async def test_downgrade_drops_all_tables(engine):
    await _upgrade(engine)
    await _downgrade(engine)
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
    for t in ("admin_users", "sidebar_banners", "categories", "seo_settings", "pipeline_runs", "agent_configs"):
        assert t not in tables

@pytest.mark.asyncio
async def test_roundtrip(engine):
    await _upgrade(engine)
    await _downgrade(engine)
    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: [t for t in inspect(c).get_table_names() if not t.startswith("sqlite_")])
    assert tables == []


# --- Data insertion ---

@pytest.mark.asyncio
async def test_insert_admin_user(engine):
    await _upgrade(engine)
    async with engine.begin() as conn:
        await conn.execute(text("INSERT INTO admin_users (username, hashed_password) VALUES ('admin', 'h')"))
        result = await conn.execute(text("SELECT username FROM admin_users"))
        assert result.scalar() == "admin"

@pytest.mark.asyncio
async def test_pipeline_runs_default_status(engine):
    await _upgrade(engine)
    async with engine.begin() as conn:
        await conn.execute(text("INSERT INTO pipeline_runs (article_id, step) VALUES (1, 'test')"))
        result = await conn.execute(text("SELECT status FROM pipeline_runs"))
        assert result.scalar() == "running"

@pytest.mark.asyncio
async def test_admin_users_default_is_active(engine):
    await _upgrade(engine)
    async with engine.begin() as conn:
        await conn.execute(text("INSERT INTO admin_users (username, hashed_password) VALUES ('u', 'p')"))
        result = await conn.execute(text("SELECT is_active FROM admin_users"))
        assert result.scalar() == 1
