"""SQLAlchemy model registry.

Importing this package ensures all models are registered with their
respective metadata objects (AppBase / ArticleBase), which is required
for Alembic autogenerate to detect them.

The env.py file does ``import app.models`` to trigger this registration.
"""

# Import all model modules so their tables are registered on the Base metadata.
# This is critical for Alembic to discover tables during autogenerate.
from app.models.admin import AdminUser, SidebarBanner, Category, SeoSettings  # noqa: F401
from app.models.article import Article, Tag, Hub, Image  # noqa: F401
from app.models.embedding import ArticleEmbedding  # noqa: F401
from app.models.pipeline import PipelineRun, AgentConfig  # noqa: F401
from app.models.enums import ArticleStatus, PipelineStep, RunStatus  # noqa: F401
