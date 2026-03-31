from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

ArticleBase = declarative_base()

class ArticleEmbedding(ArticleBase):
    __tablename__ = 'article_embeddings'

    id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey('articles.id'), unique=True, index=True)
    embedding = Column(Text, nullable=False)
    embedding_model = Column(String(100), nullable=False)
    dimensions = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)