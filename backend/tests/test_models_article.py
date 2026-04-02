import pytest
from app.models.article import Article, Tag, Hub, Image
from app.db.base import Base
from app.models.enums import ArticleStatus


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
    col = Article.__table__.c.status
    # Default is applied at INSERT — verify the column definition carries it
    default_val = col.default.arg if col.default is not None else None
    assert default_val == ArticleStatus.DISCOVERED.value


def test_tag_table():
    assert Tag.__tablename__ == 'tags'
    columns = [c.name for c in Tag.__table__.columns]
    assert 'id' in columns
    assert 'name' in columns


def test_hub_table():
    assert Hub.__tablename__ == 'hubs'
    columns = [c.name for c in Hub.__table__.columns]
    assert 'id' in columns
    assert 'name' in columns


def test_image_table():
    assert Image.__tablename__ == 'images'
    columns = [c.name for c in Image.__table__.columns]
    assert 'article_id' in columns
    assert 'original_url' in columns
    assert 'is_lead' in columns
