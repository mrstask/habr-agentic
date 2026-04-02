"""
Core application configuration module.

Provides the Settings class (backed by pydantic-settings) that aggregates
all runtime configuration for the Habr Agentic Pipeline.  Values are read
from environment variables and/or a ``.env`` file at the project root.

Usage::

    from app.core.config import settings
    print(settings.OPENAI_API_KEY)
"""

import logging
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project-root anchor: three levels up from backend/app/core/config.py
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """
    Unified settings for the Habr Agentic Pipeline backend.

    All fields can be overridden via environment variables (case-sensitive by
    default) or a ``.env`` file placed at the project root.

    Sections
    --------
    * App / API
    * Security / Auth
    * Database
    * LLM — OpenAI
    * LLM — Grok (xAI)
    * LLM — Ollama (local)
    * Pipeline agent
    * Translation
    * Embedding
    * Content filter
    * Blog publishing (potik.dev)
    * Image generation
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # App / API
    # ------------------------------------------------------------------

    APP_ENV: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Runtime environment tag used for feature gating.",
    )
    APP_HOST: str = Field(default="0.0.0.0", description="Uvicorn bind host.")
    APP_PORT: int = Field(default=8000, description="Uvicorn bind port.")
    APP_DEBUG: bool = Field(
        default=False,
        description="Enable FastAPI debug mode (auto-reloader, detailed errors).",
    )
    CORS_ORIGINS: list[str] = Field(
        default=["http://localhost:5173"],
        description="Allowed CORS origins for the FastAPI app.",
    )

    # ------------------------------------------------------------------
    # Security / Auth
    # ------------------------------------------------------------------

    SECRET_KEY: str = Field(
        default="your-secret-key-here-change-in-production",
        description="HMAC secret used to sign JWT access tokens.  MUST be changed in production.",
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm.",
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60 * 24 * 7,  # 1 week
        description="JWT token lifetime in minutes.",
    )

    # ------------------------------------------------------------------
    # Admin credentials (bootstrap user)
    # ------------------------------------------------------------------

    ADMIN_USERNAME: str = Field(
        default="admin",
        description="Default admin username created on first startup.",
    )
    ADMIN_PASSWORD: str = Field(
        default="change-me-in-production",
        description="Default admin password.  MUST be changed in production.",
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    APP_DATABASE_URL: str = Field(
        default_factory=lambda: f"sqlite+aiosqlite:///{BASE_DIR / 'app.db'}",
        description=(
            "SQLAlchemy async URL for the application/admin database "
            "(admin_users, pipeline_runs, agent_configs, …)."
        ),
    )
    ARTICLES_DATABASE_URL: str = Field(
        default_factory=lambda: f"sqlite+aiosqlite:///{BASE_DIR / 'articles.db'}",
        description=(
            "SQLAlchemy async URL for the articles/content database "
            "(articles, tags, hubs, images, embeddings)."
        ),
    )
    CHECKPOINTS_DATABASE_URL: str = Field(
        default_factory=lambda: f"sqlite+aiosqlite:///{BASE_DIR / 'checkpoints.db'}",
        description="SQLAlchemy async URL for LangGraph pipeline checkpoint persistence.",
    )

    # ------------------------------------------------------------------
    # LLM — OpenAI
    # ------------------------------------------------------------------

    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key.  Required when translation_provider='openai'.",
    )
    OPENAI_TRANSLATION_MODEL: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model name used for translation and review steps.",
    )
    OPENAI_EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="OpenAI model used for article vectorisation.",
    )
    OPENAI_TIMEOUT_SECONDS: int = Field(
        default=120,
        description="HTTP timeout (seconds) for OpenAI API calls.",
    )
    OPENAI_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retry attempts for transient OpenAI errors.",
    )

    # ------------------------------------------------------------------
    # LLM — Grok / xAI
    # ------------------------------------------------------------------

    GROK_API_KEY: Optional[str] = Field(
        default=None,
        description="xAI Grok API key.  Required when translation_provider='grok'.",
    )
    GROK_BASE_URL: str = Field(
        default="https://api.x.ai/v1",
        description="Base URL for the xAI Grok API (OpenAI-compatible).",
    )
    GROK_TRANSLATION_MODEL: str = Field(
        default="grok-3-mini",
        description="Grok model used for translation (primary provider).",
    )
    GROK_TIMEOUT_SECONDS: int = Field(
        default=120,
        description="HTTP timeout (seconds) for Grok API calls.",
    )
    GROK_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retry attempts for transient Grok errors.",
    )

    # ------------------------------------------------------------------
    # LLM — Ollama (local)
    # ------------------------------------------------------------------

    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Base URL of the locally running Ollama API server.",
    )
    OLLAMA_CONTENT_FILTER_MODEL: str = Field(
        default="qwen2.5:7b-instruct",
        description="Ollama model used for the content-filter pipeline node.",
    )
    OLLAMA_EMBEDDING_MODEL: str = Field(
        default="nomic-embed-text",
        description="Ollama model used for local embedding generation.",
    )
    OLLAMA_TIMEOUT_SECONDS: int = Field(
        default=300,
        description="HTTP timeout (seconds) for Ollama API calls (local inference can be slow).",
    )
    OLLAMA_ENABLED: bool = Field(
        default=True,
        description=(
            "When False, skip Ollama entirely and fall back to cloud providers "
            "for content filtering and embeddings."
        ),
    )

    # ------------------------------------------------------------------
    # Pipeline agent master switches
    # ------------------------------------------------------------------

    AGENT_ENABLED: bool = Field(
        default=False,
        description="Master switch — when False the pipeline scheduler does not start.",
    )
    AGENT_DRY_RUN: bool = Field(
        default=True,
        description=(
            "When True the pipeline logs all actions but makes no external writes "
            "(no DB changes, no publishing).  Safe for local testing."
        ),
    )
    AGENT_AUTO_PUBLISH: bool = Field(
        default=False,
        description="When True, successfully reviewed articles are published autonomously.",
    )
    AGENT_QUALITY_THRESHOLD: float = Field(
        default=5.0,
        ge=0.0,
        le=10.0,
        description=(
            "Minimum usefulness score (0–10) an article must receive from the "
            "review nodes to proceed toward publishing."
        ),
    )
    AGENT_POLL_INTERVAL_SECONDS: int = Field(
        default=3600,
        description="How often (seconds) the scheduler checks for new articles to process.",
    )
    AGENT_MAX_CONCURRENT_RUNS: int = Field(
        default=3,
        description="Maximum number of LangGraph pipeline threads running simultaneously.",
    )

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    TRANSLATION_PROVIDER: Literal["grok", "openai"] = Field(
        default="grok",
        description="Primary translation provider.  'openai' is used as fallback.",
    )
    TRANSLATION_FALLBACK_ENABLED: bool = Field(
        default=True,
        description="When True, failed primary-provider calls fall back to the secondary provider.",
    )
    TRANSLATION_SOURCE_LANG: str = Field(
        default="ru",
        description="BCP-47 language code of the source articles.",
    )
    TRANSLATION_TARGET_LANG: str = Field(
        default="uk",
        description="BCP-47 language code for translated output.",
    )

    # ------------------------------------------------------------------
    # Embedding / vectorisation
    # ------------------------------------------------------------------

    EMBEDDING_PROVIDER: Literal["openai", "ollama"] = Field(
        default="openai",
        description="Provider used to generate article embeddings for dedup / similarity search.",
    )
    EMBEDDING_DIMENSIONS: int = Field(
        default=1536,
        description="Dimensionality of the embedding vectors stored in article_embeddings.",
    )

    # ------------------------------------------------------------------
    # Content filter
    # ------------------------------------------------------------------

    CONTENT_FILTER_ENABLED: bool = Field(
        default=True,
        description="When False, the content_filter pipeline node is bypassed (all articles pass).",
    )
    CONTENT_FILTER_PROVIDER: Literal["ollama", "openai", "grok"] = Field(
        default="ollama",
        description="LLM provider used by the content-filter node.",
    )
    CONTENT_FILTER_REJECT_RUSSIA_SPECIFIC: bool = Field(
        default=True,
        description="Automatically reject articles that are Russia-geography-specific.",
    )

    # ------------------------------------------------------------------
    # Blog publishing — potik.dev (WordPress / REST API)
    # ------------------------------------------------------------------

    BLOG_API_URL: Optional[str] = Field(
        default=None,
        description="Base URL of the target blog's REST API (e.g. https://potik.dev/wp-json/wp/v2).",
    )
    BLOG_API_USER: Optional[str] = Field(
        default=None,
        description="WordPress application-password username for authenticated publishing.",
    )
    BLOG_API_PASSWORD: Optional[str] = Field(
        default=None,
        description="WordPress application password (not the account password).",
    )
    BLOG_DEFAULT_CATEGORY_ID: Optional[int] = Field(
        default=None,
        description="WordPress category ID assigned to newly published articles.",
    )
    BLOG_DEPLOY_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Webhook URL triggered after publishing to initiate a site re-deploy.",
    )

    # ------------------------------------------------------------------
    # Image generation
    # ------------------------------------------------------------------

    IMAGE_GENERATION_ENABLED: bool = Field(
        default=False,
        description="Enable the image_gen pipeline node (requires OPENAI_API_KEY).",
    )
    IMAGE_GENERATION_MODEL: str = Field(
        default="dall-e-3",
        description="OpenAI image model used by the image_gen node.",
    )
    IMAGE_GENERATION_SIZE: Literal["1024x1024", "1792x1024", "1024x1792"] = Field(
        default="1792x1024",
        description="Image resolution requested from the image generation API.",
    )

    # ------------------------------------------------------------------
    # Agent config DB defaults (seed values written to agent_configs table)
    # ------------------------------------------------------------------

    AGENT_CONFIG_DEFAULTS: dict = Field(
        default={
            "translation_provider": "grok",
            "translation_model": "grok-3-mini",
            "embedding_model": "text-embedding-3-small",
            "max_retries": "3",
            "timeout_seconds": "300",
        },
        description=(
            "Key-value pairs seeded into the agent_configs table on first startup.  "
            "These can be overridden at runtime via the ops dashboard."
        ),
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("AGENT_QUALITY_THRESHOLD", mode="before")
    @classmethod
    def validate_quality_threshold(cls, v: float) -> float:
        """
        Ensure AGENT_QUALITY_THRESHOLD is within the valid 0–10 scoring range.

        Raises ValueError if the value is out of bounds.
        """
        if v < 0 or v > 10:
            raise ValueError(
                f"AGENT_QUALITY_THRESHOLD must be between 0 and 10, got {v}"
            )
        return v

    @model_validator(mode="after")
    def validate_provider_keys(self) -> "Settings":
        """
        Cross-field validation: ensure the configured LLM providers have the
        required API keys available.

        Rules
        -----
        * TRANSLATION_PROVIDER='grok'  → GROK_API_KEY must be set
        * TRANSLATION_PROVIDER='openai' → OPENAI_API_KEY must be set
        * EMBEDDING_PROVIDER='openai'  → OPENAI_API_KEY must be set
        * IMAGE_GENERATION_ENABLED=True → OPENAI_API_KEY must be set

        Warnings (not errors) are emitted when AGENT_ENABLED=False, because
        the pipeline won't actually run.
        """
        missing_errors: list[str] = []
        missing_warnings: list[str] = []

        # Translation provider key check
        if self.TRANSLATION_PROVIDER == "grok" and not self.GROK_API_KEY:
            msg = "TRANSLATION_PROVIDER='grok' but GROK_API_KEY is not set"
            if self.AGENT_ENABLED:
                missing_errors.append(msg)
            else:
                missing_warnings.append(msg)

        if self.TRANSLATION_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            msg = "TRANSLATION_PROVIDER='openai' but OPENAI_API_KEY is not set"
            if self.AGENT_ENABLED:
                missing_errors.append(msg)
            else:
                missing_warnings.append(msg)

        # Embedding provider key check
        if self.EMBEDDING_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            msg = "EMBEDDING_PROVIDER='openai' but OPENAI_API_KEY is not set"
            if self.AGENT_ENABLED:
                missing_errors.append(msg)
            else:
                missing_warnings.append(msg)

        # Image generation key check
        if self.IMAGE_GENERATION_ENABLED and not self.OPENAI_API_KEY:
            msg = "IMAGE_GENERATION_ENABLED=True but OPENAI_API_KEY is not set"
            if self.AGENT_ENABLED:
                missing_errors.append(msg)
            else:
                missing_warnings.append(msg)

        # Log warnings for non-blocking issues
        for warning in missing_warnings:
            logger.warning("%s (AGENT_ENABLED=False, so this is non-blocking)", warning)

        # Raise errors for blocking issues
        if missing_errors:
            raise ValueError(
                "Missing required API keys:\n" + "\n".join(f"  - {e}" for e in missing_errors)
            )

        return self

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_production(self) -> bool:
        """Return True when APP_ENV is 'production'."""
        return self.APP_ENV == "production"

    @property
    def active_translation_model(self) -> str:
        """
        Return the model name for the currently configured translation provider.

        Selects between GROK_TRANSLATION_MODEL and OPENAI_TRANSLATION_MODEL
        based on TRANSLATION_PROVIDER.
        """
        if self.TRANSLATION_PROVIDER == "grok":
            return self.GROK_TRANSLATION_MODEL
        return self.OPENAI_TRANSLATION_MODEL

    @property
    def active_embedding_model(self) -> str:
        """
        Return the model name for the currently configured embedding provider.

        Selects between OLLAMA_EMBEDDING_MODEL and OPENAI_EMBEDDING_MODEL
        based on EMBEDDING_PROVIDER.
        """
        if self.EMBEDDING_PROVIDER == "ollama":
            return self.OLLAMA_EMBEDDING_MODEL
        return self.OPENAI_EMBEDDING_MODEL


# ---------------------------------------------------------------------------
# Module-level singleton — import this wherever settings are needed.
# ---------------------------------------------------------------------------
settings: Settings = Settings()
