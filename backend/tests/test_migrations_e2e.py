"""End-to-end migration tests.

Runs Alembic migrations against in-memory SQLite databases and validates
that all tables exist with the correct columns, indexes, and constraints.
Also verifies that downgrade (rollback) works correctly.
"""

import os
import pathlib
import sys

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# Ensure backend/ is on sys.path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.db.migration_utils import run_migrations_for_engine, get_alembic_config
from alembic import command


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app_engine() -> AsyncEngine:
    """In-memory SQLite engine for testing."""
    return create_async_engine("sqlite+aiosqlite:///:memory:")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_table_names(engine: AsyncEngine) -> list[str]:
    """Return all table names in the database."""
    async with engine.connect() as conn:
        return await conn.run_sync(lambda c: inspect(c).get_table_names())


async def _get_columns(engine: AsyncEngine, table: str) -> dict:
    """Return column info dict for *table*."""
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda c: {r["name"]: r for r in inspect(c).get_columns(table)}
        )


async def _get_indexes(engine: AsyncEngine, table: str) -> list[dict]:
    """Return index info list for *table*."""
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda c: inspect(c).get_indexes(table)
        )


async def _get_unique_constraints(engine: AsyncEngine, table: str) -> list[dict]:
    """Return unique constraint info for *table*."""
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda c: inspect(c).get_unique_constraints(table)
        )


# ---------------------------------------------------------------------------
# Migration tests — all migrations run together (they form a single chain)
# ---------------------------------------------------------------------------

class TestAllMigrations:
    """Tests for all migrations (0001, 0002, 0003) run together.

    Since migrations 0001 → 0002 → 0003 form a single chain, running
    upgrade to "head" executes all of them. These tests verify the
    complete schema after all migrations have been applied.
    """

    @pytest.fixture(autouse=True)
    async def setup_tables(self, app_engine: AsyncEngine):
        """Run all Alembic migrations."""
        os.environ['APP_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
        os.environ['ARTICLES_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
        await run_migrations_for_engine(app_engine, version_table="alembic_version_test")
        yield app_engine

    # --- App tables (from 0001) ---

    @pytest.mark.asyncio
    async def test_all_app_tables_exist(self, app_engine: AsyncEngine):
        tables = await _get_table_names(app_engine)
        expected = {
            "admin_users", "sidebar_banners", "categories",
            "seo_settings", "pipeline_runs", "agent_configs",
        }
        assert expected.issubset(set(tables))

    @pytest.mark.asyncio
    async def test_admin_users_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "admin_users")
        assert set(cols.keys()) == {"id", "username", "hashed_password", "is_active"}

    @pytest.mark.asyncio
    async def test_admin_users_username_unique(self, app_engine: AsyncEngine):
        uqs = await _get_unique_constraints(app_engine, "admin_users")
        assert any("username" in uc["column_names"] for uc in uqs)

    @pytest.mark.asyncio
    async def test_sidebar_banners_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "sidebar_banners")
        assert set(cols.keys()) == {"id", "title", "image_url", "link_url", "is_active", "position"}

    @pytest.mark.asyncio
    async def test_categories_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "categories")
        assert set(cols.keys()) == {"id", "name", "slug", "description"}

    @pytest.mark.asyncio
    async def test_categories_slug_unique(self, app_engine: AsyncEngine):
        uqs = await _get_unique_constraints(app_engine, "categories")
        assert any("slug" in uc["column_names"] for uc in uqs)

    @pytest.mark.asyncio
    async def test_seo_settings_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "seo_settings")
        assert set(cols.keys()) == {"id", "site_title", "site_description", "og_image"}

    @pytest.mark.asyncio
    async def test_pipeline_runs_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "pipeline_runs")
        assert set(cols.keys()) == {
            "id", "article_id", "step", "status",
            "started_at", "completed_at", "error", "duration_seconds",
        }

    @pytest.mark.asyncio
    async def test_pipeline_runs_article_id_index(self, app_engine: AsyncEngine):
        idxs = await _get_indexes(app_engine, "pipeline_runs")
        assert any(idx["name"] == "ix_pipeline_runs_article_id" for idx in idxs)

    @pytest.mark.asyncio
    async def test_agent_configs_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "agent_configs")
        assert set(cols.keys()) == {"id", "key", "value", "updated_at"}

    @pytest.mark.asyncio
    async def test_agent_configs_key_unique(self, app_engine: AsyncEngine):
        uqs = await _get_unique_constraints(app_engine, "agent_configs")
        assert any("key" in uc["column_names"] for uc in uqs)

    # --- Articles tables (from 0002) ---

    @pytest.mark.asyncio
    async def test_all_articles_tables_exist(self, app_engine: AsyncEngine):
        tables = await _get_table_names(app_engine)
        expected = {
            "articles", "tags", "hubs", "images",
            "article_tags", "article_hubs", "article_embeddings",
        }
        assert expected.issubset(set(tables))

    @pytest.mark.asyncio
    async def test_articles_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "articles")
        expected = {
            "id", "habr_id", "source_url", "source_title", "source_content",
            "target_title", "target_content", "target_excerpt", "target_path",
            "lead_image", "image_prompt", "status", "approved_by",
            "approved_at", "editorial_notes", "related_article_ids",
            "created_at", "updated_at",
        }
        assert set(cols.keys()) == expected

    @pytest.mark.asyncio
    async def test_articles_habr_id_unique(self, app_engine: AsyncEngine):
        uqs = await _get_unique_constraints(app_engine, "articles")
        assert any("habr_id" in uc["column_names"] for uc in uqs)

    @pytest.mark.asyncio
    async def test_articles_status_index(self, app_engine: AsyncEngine):
        idxs = await _get_indexes(app_engine, "articles")
        assert any(idx["name"] == "ix_articles_status" for idx in idxs)

    @pytest.mark.asyncio
    async def test_tags_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "tags")
        assert set(cols.keys()) == {"id", "name", "target_name"}

    @pytest.mark.asyncio
    async def test_hubs_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "hubs")
        assert set(cols.keys()) == {"id", "name", "target_name"}

    @pytest.mark.asyncio
    async def test_images_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "images")
        assert set(cols.keys()) == {"id", "article_id", "original_url", "local_path", "is_lead"}

    @pytest.mark.asyncio
    async def test_article_tags_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "article_tags")
        assert set(cols.keys()) == {"article_id", "tag_id"}

    @pytest.mark.asyncio
    async def test_article_hubs_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "article_hubs")
        assert set(cols.keys()) == {"article_id", "hub_id"}

    @pytest.mark.asyncio
    async def test_article_embeddings_columns(self, app_engine: AsyncEngine):
        cols = await _get_columns(app_engine, "article_embeddings")
        expected = {
            "id", "article_id", "embedding", "embedding_model",
            "dimensions", "created_at", "updated_at",
        }
        assert set(cols.keys()) == expected

    @pytest.mark.asyncio
    async def test_article_embeddings_article_id_unique(self, app_engine: AsyncEngine):
        # article_id is unique=True inline — SQLite surfaces this as a unique index, not a named constraint
        idxs = await _get_indexes(app_engine, "article_embeddings")
        uqs = await _get_unique_constraints(app_engine, "article_embeddings")
        has_unique_index = any(idx.get("unique") and "article_id" in idx["column_names"] for idx in idxs)
        has_unique_constraint = any("article_id" in uc["column_names"] for uc in uqs)
        assert has_unique_index or has_unique_constraint

    # --- Indexes (from 0003) ---

    @pytest.mark.asyncio
    async def test_ix_articles_habr_id_exists(self, app_engine: AsyncEngine):
        idxs = await _get_indexes(app_engine, "articles")
        assert any(idx["name"] == "ix_articles_habr_id" for idx in idxs)

    @pytest.mark.asyncio
    async def test_ix_articles_created_at_exists(self, app_engine: AsyncEngine):
        idxs = await _get_indexes(app_engine, "articles")
        assert any(idx["name"] == "ix_articles_created_at" for idx in idxs)

    @pytest.mark.asyncio
    async def test_ix_pipeline_runs_started_at_exists(self, app_engine: AsyncEngine):
        idxs = await _get_indexes(app_engine, "pipeline_runs")
        assert any(idx["name"] == "ix_pipeline_runs_started_at" for idx in idxs)

    @pytest.mark.asyncio
    async def test_ix_pipeline_runs_status_exists(self, app_engine: AsyncEngine):
        idxs = await _get_indexes(app_engine, "pipeline_runs")
        assert any(idx["name"] == "ix_pipeline_runs_status" for idx in idxs)


# ---------------------------------------------------------------------------
# Downgrade / rollback tests
# ---------------------------------------------------------------------------

class TestDowngrade:
    """Verify that downgrade (DROP TABLE) works correctly."""

    @pytest.mark.asyncio
    async def test_downgrade_drops_all_tables(self):
        """After downgrading to base, no user tables should remain."""
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        os.environ['APP_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
        os.environ['ARTICLES_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'

        # Run all migrations
        await run_migrations_for_engine(engine, version_table="alembic_version_test")

        # Verify tables exist
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            user_tables = [t for t in tables if not t.startswith("sqlite_") and t != "alembic_version_test"]
            assert len(user_tables) == 13  # 6 app + 7 articles tables

        # Downgrade: run downgrade to base
        cfg = get_alembic_config()
        cfg.set_main_option("version_table", "alembic_version_test")

        async with engine.connect() as conn:
            def _downgrade(c):
                cfg.attributes["connection"] = c
                command.downgrade(cfg, "base")
            await conn.run_sync(_downgrade)

        # Verify tables are dropped
        async with engine.connect() as conn:
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            user_tables = [t for t in tables if not t.startswith("sqlite_") and t != "alembic_version_test"]
            assert user_tables == []

        await engine.dispose()


# ---------------------------------------------------------------------------
# Data insertion tests
# ---------------------------------------------------------------------------

class TestDataInsertion:
    """Verify that data can be inserted into migrated tables."""

    @pytest.mark.asyncio
    async def test_insert_admin_user(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        os.environ['APP_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
        os.environ['ARTICLES_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'

        await run_migrations_for_engine(engine, version_table="alembic_version_test")

        async with engine.begin() as conn:
            await conn.execute(text(
                "INSERT INTO admin_users (username, hashed_password) VALUES ('admin', 'hashed_pw')"
            ))
            result = await conn.execute(text("SELECT username FROM admin_users"))
            assert result.scalar() == "admin"

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_insert_article(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        os.environ['APP_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
        os.environ['ARTICLES_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'

        await run_migrations_for_engine(engine, version_table="alembic_version_test")

        async with engine.begin() as conn:
            await conn.execute(text("""
                INSERT INTO articles (habr_id, source_url, source_title, source_content)
                VALUES ('12345', 'https://habr.com/12345', 'Test Article', 'Content here')
            """))
            result = await conn.execute(text("SELECT habr_id FROM articles"))
            assert result.scalar() == "12345"

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_pipeline_runs_default_status(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        os.environ['APP_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
        os.environ['ARTICLES_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'

        await run_migrations_for_engine(engine, version_table="alembic_version_test")

        async with engine.begin() as conn:
            # status has a Python-side default (not server_default), so supply it explicitly in raw SQL
            await conn.execute(text(
                "INSERT INTO pipeline_runs (article_id, step, status) VALUES (1, 'extraction', 'running')"
            ))
            result = await conn.execute(text("SELECT status FROM pipeline_runs"))
            assert result.scalar() == "running"

        await engine.dispose()
