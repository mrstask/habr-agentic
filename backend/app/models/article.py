from sqlalchemy import Column, Integer, String, Text, ForeignKey, Table, func, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import text
from app.models.enums import ArticleStatus

ArticleBase = declarative_base()

article_tags = Table('article_tags', ArticleBase.metadata,
    Column('article_id', Integer, ForeignKey('articles.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True)
)

article_hubs = Table('article_hubs', ArticleBase.metadata,
    Column('article_id', Integer, ForeignKey('articles.id'), primary_key=True),
    Column('hub_id', Integer, ForeignKey('hubs.id'), primary_key=True)
)

class Article(ArticleBase):
    __tablename__ = 'articles'

    id = Column(Integer, primary_key=True, index=True)
    habr_id = Column(String, unique=True, nullable=False)
    source_url = Column(String, nullable=False)
    source_title = Column(String, nullable=False)
    source_content = Column(Text, nullable=False)
    target_title = Column(String, nullable=True)
    target_content = Column(Text, nullable=True)
    target_excerpt = Column(Text, nullable=True)
    target_path = Column(String, nullable=True)
    lead_image = Column(String, nullable=True)
    image_prompt = Column(String, nullable=True)
    status = Column(Integer, default=ArticleStatus.DISCOVERED.value, index=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    editorial_notes = Column(Text, nullable=True)
    related_article_ids = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    tags = relationship('Tag', secondary=article_tags, back_populates='articles')
    hubs = relationship('Hub', secondary=article_hubs, back_populates='articles')
    images = relationship('Image', back_populates='article')

class Tag(ArticleBase):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    target_name = Column(String, nullable=True)

    articles = relationship('Article', secondary=article_tags, back_populates='tags')

class Hub(ArticleBase):
    __tablename__ = 'hubs'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    target_name = Column(String, nullable=True)

    articles = relationship('Article', secondary=article_hubs, back_populates='hubs')

class Image(ArticleBase):
    __tablename__ = 'images'

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey('articles.id'), nullable=False)
    original_url = Column(String, nullable=False)
    local_path = Column(String, nullable=True)
    is_lead = Column(Boolean, default=False)

    article = relationship('Article', back_populates='images')