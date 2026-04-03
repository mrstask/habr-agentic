from app.models.embedding import ArticleEmbedding


def test_article_embedding_table_creation():
    assert hasattr(ArticleEmbedding, '__tablename__')
    assert ArticleEmbedding.__tablename__ == 'article_embeddings'


def test_article_embedding_columns():
    columns = [c.name for c in ArticleEmbedding.__table__.columns]
    assert 'id' in columns
    assert 'article_id' in columns
    assert 'embedding' in columns
    assert 'embedding_model' in columns
    assert 'dimensions' in columns
    assert 'created_at' in columns
    assert 'updated_at' in columns


def test_article_embedding_unique_constraint():
    constraints = ArticleEmbedding.__table__.constraints
    unique_cols = set()
    for c in constraints:
        if hasattr(c, 'columns'):
            for col in c.columns:
                unique_cols.add(col.name)
    assert 'article_id' in unique_cols
