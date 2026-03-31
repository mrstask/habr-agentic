import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.article import Article, Tag, Hub, Image
from app.db.base import ArticleBase
from datetime import datetime
def test_article_table_creation():
    assert hasattr(Article, '__tablename__') and Article.__tablename__ == 'articles'

def test_article_column_types():
    columns = [c.name for c in Article.__table__.columns]
    assert 'id' in columns
    assert 'habr_id' in columns
    assert 'source_url' in columns
    assert 'source_title' in columns
    assert 'source_content' in columns
    assert 'target_title' in columns
    assert 'target_content' in columns
    assert 'target_excerpt' in columns
    assert 'target_path' in columns
    assert 'lead_image' in columns
    assert 'image_prompt' in columns
    assert 'status' in columns
    assert 'approved_by' in columns
    assert 'approved_at' in columns
    assert 'editorial_notes' in columns
    assert 'related_article_ids' in columns
    assert 'created_at' in columns
    assert 'updated_at' in columns

def test_article_default_status():
    article = Article()
    assert article.status == ArticleStatus.DISCOVERED.value

def test_article_timestamps(session: AsyncSession):
    article = Article()
    session.add(article)
    await session.commit()
    await session.refresh(article)
    assert isinstance(article.created_at, datetime)
    assert isinstance(article.updated_at, datetime)