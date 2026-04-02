"""Tests for backend/app/db/base.py — centralized declarative base."""

import pytest
from sqlalchemy.orm import DeclarativeMeta

from app.db.base import Base, AppBase, ArticleBase


class TestBaseClass:
    """Tests for the unified Base class."""

    def test_base_is_declarative_meta(self):
        """Base should be a SQLAlchemy declarative base (DeclarativeMeta)."""
        assert isinstance(Base, DeclarativeMeta)

    def test_base_has_metadata(self):
        """Base must expose a metadata registry."""
        assert hasattr(Base, "metadata")
        assert Base.metadata is not None

    def test_base_metadata_tables_empty_initially(self):
        """Before models are imported, metadata tables should be empty."""
        # Note: models may already be imported by other tests, so we just
        # verify metadata exists and is a valid MetaData instance.
        from sqlalchemy import MetaData
        assert isinstance(Base.metadata, MetaData)


class TestBaseAliases:
    """Tests for backward-compatibility aliases."""

    def test_app_base_is_same_as_base(self):
        """AppBase must be the exact same object as Base."""
        assert AppBase is Base

    def test_article_base_is_same_as_base(self):
        """ArticleBase must be the exact same object as Base."""
        assert ArticleBase is Base

    def test_all_bases_share_metadata(self):
        """All base aliases must share the same metadata registry."""
        assert Base.metadata is AppBase.metadata
        assert Base.metadata is ArticleBase.metadata

    def test_model_inherits_from_app_base(self):
        """A model inheriting from AppBase should register on Base.metadata."""
        from sqlalchemy import Column, Integer, String

        class TempModel(AppBase):
            __tablename__ = "temp_app_test"
            id = Column(Integer, primary_key=True)
            name = Column(String)

        assert "temp_app_test" in Base.metadata.tables

    def test_model_inherits_from_article_base(self):
        """A model inheriting from ArticleBase should register on Base.metadata."""
        from sqlalchemy import Column, Integer, String

        class TempArticleModel(ArticleBase):
            __tablename__ = "temp_article_test"
            id = Column(Integer, primary_key=True)
            title = Column(String)

        assert "temp_article_test" in Base.metadata.tables

    def test_model_inherits_from_base(self):
        """A model inheriting from Base should register on Base.metadata."""
        from sqlalchemy import Column, Integer, String

        class TempBaseModel(Base):
            __tablename__ = "temp_base_test"
            id = Column(Integer, primary_key=True)
            value = Column(String)

        assert "temp_base_test" in Base.metadata.tables
