"""
Pydantic schemas for the Habr Agentic Pipeline API.

This module defines all request and response models used by the API routes.
Schemas are organized by domain (articles, pipeline, admin, settings)
and provide type-safe validation for all API inputs and outputs.

Usage::

    from app.schemas import ArticleResponse, ArticleListResponse
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import ArticleStatus, PipelineStep, RunStatus


# ---------------------------------------------------------------------------
# Shared schemas
# ---------------------------------------------------------------------------

class PaginationMeta(BaseModel):
    """
    Pagination metadata included in list responses.

    Attributes:
        total: Total number of items matching the query.
        limit: Maximum number of items returned per page.
        offset: Number of items skipped from the beginning.
        has_next: Whether there are more items after the current page.
    """
    total: int = Field(..., description="Total number of items matching the query")
    limit: int = Field(..., description="Maximum items per page")
    offset: int = Field(..., description="Number of items skipped")
    has_next: bool = Field(..., description="Whether more items exist after this page")


class ErrorResponse(BaseModel):
    """
    Standard error response schema for API errors.

    Attributes:
        error: Human-readable error type or category.
        detail: Detailed error message (only in debug mode).
        status_code: HTTP status code of the error.
    """
    error: str = Field(..., description="Error type or category")
    detail: Optional[str] = Field(None, description="Detailed error message")
    status_code: int = Field(..., description="HTTP status code")


# ---------------------------------------------------------------------------
# Article schemas
# ---------------------------------------------------------------------------

class ArticleBase(BaseModel):
    """
    Base schema for article data shared between request and response.

    Attributes:
        title: Article title.
        url: Original Habr article URL.
        source_language: Source language code (e.g., 'ru').
        target_language: Target language code (e.g., 'uk').
    """
    title: str = Field(..., description="Article title")
    url: str = Field(..., description="Original Habr article URL")
    source_language: str = Field(default="ru", description="Source language code")
    target_language: str = Field(default="uk", description="Target language code")


class ArticleCreate(ArticleBase):
    """
    Request schema for creating a new article entry.

    Attributes:
        title: Article title.
        url: Original Habr article URL.
        source_language: Source language code.
        target_language: Target language code.
        hub: Optional Hubr hub/category name.
    """
    hub: Optional[str] = Field(None, description="Habr hub/category name")


class ArticleUpdate(BaseModel):
    """
    Request schema for updating an existing article.

    All fields are optional — only provided fields will be updated.

    Attributes:
        title: Updated article title.
        status: Updated article status.
        translated_content: Translated article content in Ukrainian.
        editorial_notes: Notes from the review/pipeline process.
    """
    title: Optional[str] = Field(None, description="Updated article title")
    status: Optional[ArticleStatus] = Field(None, description="Updated article status")
    translated_content: Optional[str] = Field(None, description="Translated content")
    editorial_notes: Optional[str] = Field(None, description="Review/pipeline notes")


class ArticleResponse(BaseModel):
    """
    Response schema for a single article with full details.

    Attributes:
        id: Unique article identifier.
        title: Article title.
        url: Original Habr article URL.
        status: Current article status.
        source_language: Source language code.
        target_language: Target language code.
        translated_content: Translated article content (if available).
        editorial_notes: Notes from the review/pipeline process.
        created_at: When the article was discovered/created.
        updated_at: When the article was last modified.
        tags: List of tag names associated with the article.
        hubs: List of hub names associated with the article.
    """
    id: int = Field(..., description="Unique article identifier")
    title: str = Field(..., description="Article title")
    url: str = Field(..., description="Original Habr article URL")
    status: ArticleStatus = Field(..., description="Current article status")
    source_language: str = Field(..., description="Source language code")
    target_language: str = Field(..., description="Target language code")
    translated_content: Optional[str] = Field(None, description="Translated content")
    editorial_notes: Optional[str] = Field(None, description="Review/pipeline notes")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    tags: list[str] = Field(default_factory=list, description="Associated tag names")
    hubs: list[str] = Field(default_factory=list, description="Associated hub names")


class ArticleListResponse(BaseModel):
    """
    Response schema for a paginated list of articles.

    Attributes:
        items: List of article summaries.
        meta: Pagination metadata.
    """
    items: list[ArticleResponse] = Field(..., description="List of articles")
    meta: PaginationMeta = Field(..., description="Pagination metadata")


# ---------------------------------------------------------------------------
# Pipeline schemas
# ---------------------------------------------------------------------------

class PipelineRunResponse(BaseModel):
    """
    Response schema for a single pipeline run.

    Attributes:
        id: Unique run identifier.
        article_id: ID of the article being processed.
        status: Current run status.
        current_step: The pipeline step currently executing.
        started_at: When the run started.
        completed_at: When the run completed (if finished).
        error_message: Error message if the run failed.
        duration_seconds: Total run duration in seconds.
    """
    id: int = Field(..., description="Unique run identifier")
    article_id: int = Field(..., description="Article ID being processed")
    status: RunStatus = Field(..., description="Current run status")
    current_step: Optional[PipelineStep] = Field(None, description="Current pipeline step")
    started_at: datetime = Field(..., description="Run start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Run completion timestamp")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    duration_seconds: Optional[float] = Field(None, description="Run duration in seconds")


class PipelineRunListResponse(BaseModel):
    """
    Response schema for a paginated list of pipeline runs.

    Attributes:
        items: List of pipeline run summaries.
        meta: Pagination metadata.
    """
    items: list[PipelineRunResponse] = Field(..., description="List of pipeline runs")
    meta: PaginationMeta = Field(..., description="Pagination metadata")


class PipelineTriggerResponse(BaseModel):
    """
    Response schema for a manually triggered pipeline run.

    Attributes:
        run_id: ID of the newly created pipeline run.
        article_id: ID of the article being processed.
        status: Initial run status.
        message: Human-readable status message.
    """
    run_id: int = Field(..., description="Newly created run ID")
    article_id: int = Field(..., description="Article ID being processed")
    status: RunStatus = Field(..., description="Initial run status")
    message: str = Field(..., description="Status message")


class PipelineStatusResponse(BaseModel):
    """
    Response schema for overall pipeline status and statistics.

    Attributes:
        agent_enabled: Whether the pipeline scheduler is active.
        agent_dry_run: Whether the pipeline is in dry-run mode.
        active_runs: Number of currently running pipeline executions.
        queued_articles: Number of articles waiting to be processed.
        total_runs_today: Total pipeline runs completed today.
        success_rate: Percentage of successful runs (0-100).
        average_duration_seconds: Average run duration in seconds.
    """
    agent_enabled: bool = Field(..., description="Pipeline scheduler active")
    agent_dry_run: bool = Field(..., description="Dry-run mode active")
    active_runs: int = Field(..., description="Currently running executions")
    queued_articles: int = Field(..., description="Articles waiting to be processed")
    total_runs_today: int = Field(..., description="Runs completed today")
    success_rate: float = Field(..., description="Success rate percentage (0-100)")
    average_duration_seconds: float = Field(..., description="Average run duration")


# ---------------------------------------------------------------------------
# Admin schemas
# ---------------------------------------------------------------------------

class AdminLoginRequest(BaseModel):
    """
    Request schema for admin authentication.

    Attributes:
        username: Admin username.
        password: Admin password.
    """
    username: str = Field(..., description="Admin username", min_length=1)
    password: str = Field(..., description="Admin password", min_length=1)


class AdminLoginResponse(BaseModel):
    """
    Response schema for successful admin authentication.

    Attributes:
        access_token: JWT access token for authenticated requests.
        token_type: Token type (always "bearer").
        expires_in: Token lifetime in seconds.
    """
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token lifetime in seconds")


class AdminUserResponse(BaseModel):
    """
    Response schema for admin user information.

    Attributes:
        id: Unique user identifier.
        username: Admin username.
        email: Optional email address.
        is_active: Whether the account is active.
        created_at: When the user was created.
        updated_at: When the user was last modified.
    """
    id: int = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Admin username")
    email: Optional[str] = Field(None, description="Email address")
    is_active: bool = Field(..., description="Account active status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class AdminUserCreate(BaseModel):
    """
    Request schema for creating a new admin user.

    Attributes:
        username: New admin username.
        password: New admin password.
        email: Optional email address.
    """
    username: str = Field(..., description="New admin username", min_length=3)
    password: str = Field(..., description="New admin password", min_length=8)
    email: Optional[str] = Field(None, description="Optional email address")


class AdminUserUpdate(BaseModel):
    """
    Request schema for updating an existing admin user.

    All fields are optional — only provided fields will be updated.

    Attributes:
        password: New password.
        email: New email address.
        is_active: Active status.
    """
    password: Optional[str] = Field(None, description="New password", min_length=8)
    email: Optional[str] = Field(None, description="New email address")
    is_active: Optional[bool] = Field(None, description="Active status")


# ---------------------------------------------------------------------------
# Settings schemas
# ---------------------------------------------------------------------------

class AppSettingsResponse(BaseModel):
    """
    Response schema for application settings (read-only).

    Attributes:
        app_env: Runtime environment (development, staging, production).
        app_debug: Whether debug mode is enabled.
        cors_origins: Allowed CORS origins.
        translation_provider: Primary translation provider.
        embedding_provider: Embedding provider.
        content_filter_provider: Content filter LLM provider.
    """
    app_env: str = Field(..., description="Runtime environment")
    app_debug: bool = Field(..., description="Debug mode status")
    cors_origins: list[str] = Field(..., description="Allowed CORS origins")
    translation_provider: str = Field(..., description="Primary translation provider")
    embedding_provider: str = Field(..., description="Embedding provider")
    content_filter_provider: str = Field(..., description="Content filter LLM provider")


class AgentConfigResponse(BaseModel):
    """
    Response schema for agent configuration.

    Attributes:
        key: Configuration key.
        value: Configuration value.
        description: Human-readable description of the setting.
        updated_at: When the configuration was last updated.
    """
    key: str = Field(..., description="Configuration key")
    value: str = Field(..., description="Configuration value")
    description: Optional[str] = Field(None, description="Setting description")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class AgentConfigUpdate(BaseModel):
    """
    Request schema for updating agent configuration.

    Attributes:
        value: New configuration value.
    """
    value: str = Field(..., description="New configuration value")


class TranslationSettingsResponse(BaseModel):
    """
    Response schema for translation provider settings.

    Attributes:
        provider: Primary translation provider.
        fallback_enabled: Whether fallback to secondary provider is enabled.
        source_language: Source language code.
        target_language: Target language code.
        model: Current translation model name.
    """
    provider: str = Field(..., description="Primary translation provider")
    fallback_enabled: bool = Field(..., description="Fallback enabled")
    source_language: str = Field(..., description="Source language code")
    target_language: str = Field(..., description="Target language code")
    model: str = Field(..., description="Current translation model")


class EmbeddingSettingsResponse(BaseModel):
    """
    Response schema for embedding provider settings.

    Attributes:
        provider: Embedding provider (openai or ollama).
        model: Current embedding model name.
        dimensions: Embedding vector dimensionality.
    """
    provider: str = Field(..., description="Embedding provider")
    model: str = Field(..., description="Current embedding model")
    dimensions: int = Field(..., description="Vector dimensionality")


class ContentFilterSettingsResponse(BaseModel):
    """
    Response schema for content filter settings.

    Attributes:
        enabled: Whether content filtering is active.
        provider: LLM provider used for content filtering.
        reject_russia_specific: Whether Russia-specific articles are rejected.
    """
    enabled: bool = Field(..., description="Content filtering active")
    provider: str = Field(..., description="LLM provider for filtering")
    reject_russia_specific: bool = Field(..., description="Reject Russia-specific articles")
