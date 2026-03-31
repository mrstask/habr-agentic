import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.embedding import ArticleEmbedding
from app.db.base import ArticleBase
def test_article_embedding_table_creation():
    assert hasattr(ArticleEmbedding, '__tablename__') and ArticleEmbedding.__tablename__ == 'article_embeddings'

def test_article_embedding_unique_constraint(session: AsyncSession):
    article = Article()
    session.add(article)
    await session.commit()
    embedding1 = ArticleEmbedding(article_id=article.id, embedding='embedding_data_1', embedding_model='model_1', dimensions=100)
    session.add(embedding1)
    await session.commit()
    with pytest.raises(Exception):
        embedding2 = ArticleEmbedding(article_id=article.id, embedding='embedding_data_2', embedding_model='model_2', dimensions=100)
        session.add(embedding2)
        await session.commit()