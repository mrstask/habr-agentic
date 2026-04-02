"""initial app tables

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'admin_users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )

    op.create_table(
        'sidebar_banners',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('image_url', sa.String(), nullable=False),
        sa.Column('link_url', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
    )

    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), unique=True, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
    )

    op.create_table(
        'seo_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('site_title', sa.String(), nullable=False),
        sa.Column('site_description', sa.Text(), nullable=True),
        sa.Column('og_image', sa.String(), nullable=True),
    )

    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('article_id', sa.Integer(), nullable=True),
        sa.Column('step', sa.String(), nullable=False),
        sa.Column('status', sa.String(), server_default=sa.text("'running'"), nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
    )
    op.create_index('ix_pipeline_runs_article_id', 'pipeline_runs', ['article_id'])

    op.create_table(
        'agent_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(), unique=True, nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('agent_configs')
    op.drop_index('ix_pipeline_runs_article_id', table_name='pipeline_runs')
    op.drop_table('pipeline_runs')
    op.drop_table('seo_settings')
    op.drop_table('categories')
    op.drop_table('sidebar_banners')
    op.drop_table('admin_users')
