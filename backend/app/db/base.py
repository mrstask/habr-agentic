"""Centralized SQLAlchemy declarative base for dual-database architecture.

All ORM models MUST import their base from here (not create their own).
This ensures Alembic's ``env.py`` sees every table via ``Base.metadata``.

The dual-database separation is handled at the engine/session level,
not through separate declarative bases. Both AppBase and ArticleBase
are aliases to the same Base class for backward compatibility.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
"""Unified base class for all ORM models."""

# Backward compatibility aliases
AppBase = Base
"""Alias for Base — models stored in the App database (admin, pipeline, config)."""

ArticleBase = Base
"""Alias for Base — models stored in the Articles database (articles, tags, hubs, images, embeddings)."""
