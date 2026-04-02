"""Initial app database schema — admin_users, sidebar_banners, categories, seo_settings,
pipeline_runs, agent_configs.

Revision ID: 20260402_0001
Revises:
Create Date: 2026-04-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260402_0001"
down_revision = None
branch_labels = ("app",)
depends_on = None


def upgrade() -> None:
    """Create all tables belonging to the App database (AppBase metadata).

    Tables: admin_users, sidebar_banners, categories, seo_settings,
    pipeline_runs, agent_configs.
    """
    # Create admin_users table
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
    )

    # Create sidebar_banners table
    op.create_table(
        "sidebar_banners",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("image_url", sa.String(), nullable=False),
        sa.Column("link_url", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("position", sa.Integer(), nullable=False),
    )

    # Create categories table
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )

    # Create seo_settings table
    op.create_table(
        "seo_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_title", sa.String(), nullable=False),
        sa.Column("site_description", sa.Text(), nullable=True),
        sa.Column("og_image", sa.String(), nullable=True),
    )

    # Create pipeline_runs table
    # NOTE: article_id references articles table in a DIFFERENT database.
    #       For SQLite this FK is cross-db and cannot be enforced; store as plain Integer.
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), index=True),
        sa.Column("step", sa.String(), nullable=False),
        sa.Column("status", sa.String(), default="running"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
    )

    # Create agent_configs table
    op.create_table(
        "agent_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(), unique=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    """Drop all App database tables in reverse dependency order."""
    op.drop_table("agent_configs")
    op.drop_table("pipeline_runs")
    op.drop_table("seo_settings")
    op.drop_table("categories")
    op.drop_table("sidebar_banners")
    op.drop_table("admin_users")
