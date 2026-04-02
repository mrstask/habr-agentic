"""Initial articles database schema — articles, tags, hubs, images, article_tags,
article_hubs, article_embeddings.

Revision ID: 20260402_0002
Revises: 20260402_0001
Create Date: 2026-04-02 00:00:01
"""

from alembic import op
import sqlalchemy as sa


revision = "20260402_0002"
down_revision = "20260402_0001"
branch_labels = ("articles",)
depends_on = None


def upgrade() -> None:
    """Create all tables belonging to the Articles database (ArticleBase metadata).

    Tables: articles, tags, hubs, images, article_tags, article_hubs, article_embeddings.

    The articles table uses an IntEnum for status:
        DISCOVERED=0, EXTRACTED=1, TRANSLATED=2, PUBLISHED=3, USELESS=4, DRAFT=5
    """
    op.create_table(
        "articles",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("habr_id", sa.String(), unique=True, nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("source_title", sa.String(), nullable=False),
        sa.Column("source_content", sa.Text(), nullable=False),
        sa.Column("target_title", sa.String(), nullable=True),
        sa.Column("target_content", sa.Text(), nullable=True),
        sa.Column("target_excerpt", sa.Text(), nullable=True),
        sa.Column("target_path", sa.String(), nullable=True),
        sa.Column("lead_image", sa.String(), nullable=True),
        sa.Column("image_prompt", sa.String(), nullable=True),
        sa.Column("status", sa.Integer(), default=0, index=True),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("editorial_notes", sa.Text(), nullable=True),
        sa.Column("related_article_ids", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), unique=True, nullable=False),
        sa.Column("target_name", sa.String(), nullable=True),
    )

    op.create_table(
        "hubs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(), unique=True, nullable=False),
        sa.Column("target_name", sa.String(), nullable=True),
    )

    op.create_table(
        "images",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), nullable=False),
        sa.Column("original_url", sa.String(), nullable=False),
        sa.Column("local_path", sa.String(), nullable=True),
        sa.Column("is_lead", sa.Boolean(), default=False),
    )

    op.create_table(
        "article_tags",
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), primary_key=True, nullable=False),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), primary_key=True, nullable=False),
    )

    op.create_table(
        "article_hubs",
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), primary_key=True, nullable=False),
        sa.Column("hub_id", sa.Integer(), sa.ForeignKey("hubs.id"), primary_key=True, nullable=False),
    )

    op.create_table(
        "article_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id"), unique=True, index=True),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    """Drop all Articles database tables in reverse dependency order."""
    op.drop_table("article_embeddings")
    op.drop_table("article_hubs")
    op.drop_table("article_tags")
    op.drop_table("images")
    op.drop_table("hubs")
    op.drop_table("tags")
    op.drop_table("articles")
