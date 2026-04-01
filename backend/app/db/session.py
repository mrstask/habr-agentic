from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

# Create async engines for both databases
APP_ENGINE = create_async_engine(settings.APP_DATABASE_URL, echo=False)
ARTICLES_ENGINE = create_async_engine(settings.ARTICLES_DATABASE_URL, echo=False)

# Create async session makers
AppSessionLocal = async_sessionmaker(APP_ENGINE, expire_on_commit=False, class_=AsyncSession)
ArticlesSessionLocal = async_sessionmaker(ARTICLES_ENGINE, expire_on_commit=False, class_=AsyncSession)

# For backward compatibility
DATABASE_URL = settings.APP_DATABASE_URL
