"""
Article management API routes.

Provides endpoints for listing, retrieving, creating, updating, and
deleting articles in the Habr Agentic Pipeline. Supports filtering
by status, date, and other criteria.

All endpoints use the ArticleService for business logic and the
centralized database session dependency from app.dependencies.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_articles_session
from app.models.enums import ArticleStatus
from app.schemas import (
    ArticleCreate,
    ArticleUpdate,
    ArticleResponse,
    ArticleListResponse,
)
from app.services.article_service import ArticleService

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get(
    "/",
    response_model=ArticleListResponse,
    summary="List articles with filtering and pagination",
)
async def list_articles(
    status_filter: Optional[ArticleStatus] = Query(
        None, alias="status", description="Filter by ArticleStatus enum value"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of articles to return"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
    session: AsyncSession = Depends(get_articles_session),
) -> ArticleListResponse:
    """
    List articles with optional filtering and pagination.

    Args:
        status_filter: Filter by ArticleStatus enum value.
        limit: Maximum number of articles to return (1-200).
        offset: Number of articles to skip for pagination.
        session: Async database session.

    Returns:
        ArticleListResponse: Paginated list of articles with metadata.
    """
    service = ArticleService(session)
    return await service.list_articles(
        status=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{article_id}",
    response_model=ArticleResponse,
    summary="Get article by ID",
)
async def get_article(
    article_id: int,
    session: AsyncSession = Depends(get_articles_session),
) -> ArticleResponse:
    """
    Retrieve a single article by ID.

    Args:
        article_id: The unique identifier of the article.
        session: Async database session.

    Returns:
        ArticleResponse: Article details including metadata, tags, hubs, and images.

    Raises:
        HTTPException: 404 Not Found if article does not exist.
    """
    service = ArticleService(session)
    return await service.get_article(article_id)


@router.post(
    "/",
    response_model=ArticleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new article",
)
async def create_article(
    article_data: ArticleCreate,
    session: AsyncSession = Depends(get_articles_session),
) -> ArticleResponse:
    """
    Create a new article entry in the pipeline.

    Args:
        article_data: Article creation data including title, URL, and language.
        session: Async database session.

    Returns:
        ArticleResponse: The created article with generated ID and timestamps.
    """
    service = ArticleService(session)
    return await service.create_article(article_data)


@router.put(
    "/{article_id}",
    response_model=ArticleResponse,
    summary="Update an article",
)
async def update_article(
    article_id: int,
    update_data: ArticleUpdate,
    session: AsyncSession = Depends(get_articles_session),
) -> ArticleResponse:
    """
    Update an existing article with provided fields.

    Args:
        article_id: The unique identifier of the article to update.
        update_data: Fields to update (only non-None fields are applied).
        session: Async database session.

    Returns:
        ArticleResponse: The updated article information.

    Raises:
        HTTPException: 404 Not Found if article does not exist.
    """
    service = ArticleService(session)
    return await service.update_article(article_id, update_data)


@router.put(
    "/{article_id}/status",
    response_model=ArticleResponse,
    summary="Update article status",
)
async def update_article_status(
    article_id: int,
    new_status: ArticleStatus,
    session: AsyncSession = Depends(get_articles_session),
) -> ArticleResponse:
    """
    Update the status of an article.

    Args:
        article_id: The unique identifier of the article.
        new_status: New ArticleStatus enum value.
        session: Async database session.

    Returns:
        ArticleResponse: Updated article information.

    Raises:
        HTTPException: 404 Not Found if article does not exist.
        HTTPException: 400 Bad Request if status transition is invalid.
    """
    service = ArticleService(session)
    return await service.update_article_status(article_id, new_status)


@router.delete(
    "/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an article",
)
async def delete_article(
    article_id: int,
    session: AsyncSession = Depends(get_articles_session),
) -> None:
    """
    Delete an article and all associated data (tags, hubs, images, embeddings).

    Args:
        article_id: The unique identifier of the article to delete.
        session: Async database session.

    Raises:
        HTTPException: 404 Not Found if article does not exist.
    """
    service = ArticleService(session)
    await service.delete_article(article_id)
