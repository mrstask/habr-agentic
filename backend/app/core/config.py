from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    APP_DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'app.db'}"
    ARTICLES_DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'articles.db'}"
    
    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    # Admin credentials
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "change-me-in-production"
    
    # Agent Config defaults
    AGENT_CONFIG_DEFAULTS: dict = {
        "translation_provider": "openai",
        "translation_model": "gpt-4o-mini",
        "embedding_model": "text-embedding-3-small",
        "max_retries": "3",
        "timeout_seconds": "300",
    }
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()