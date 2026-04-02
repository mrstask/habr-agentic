"""Add performance indexes to articles and pipeline_runs tables.

Revision ID: 20260402_0003
Revises: 20260402_0002
Create Date: 2026-04-02 00:00:02
"""

from alembic import op
import sqlalchemy as sa


revision = "20260402_0003"
down_revision = "20260402_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add indexes for common query patterns.

    - articles.habr_id — lookups by external Habr identifier
    - articles.created_at — ordering by discovery time
    - pipeline_runs.started_at — ordering runs chronologically
    - pipeline_runs.status — filtering by run status
    """
    op.create_index("ix_articles_habr_id", "articles", ["habr_id"])
    op.create_index("ix_articles_created_at", "articles", ["created_at"])
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"])
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"])


def downgrade() -> None:
    """Drop performance indexes."""
    op.drop_index("ix_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_started_at", table_name="pipeline_runs")
    op.drop_index("ix_articles_created_at", table_name="articles")
    op.drop_index("ix_articles_habr_id", table_name="articles")
