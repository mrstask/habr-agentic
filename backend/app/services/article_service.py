"""
Article business logic service.

Provides high-level article operations that coordinate between
repositories and apply business rules (status transitions, validation).
"""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.article import Article, Tag, Hub, Image
from app.models.enums import ArticleStatus
from app.schemas import (
    ArticleCreate,
    ArticleUpdate,
    ArticleResponse,
    ArticleListResponse,
    PaginationMeta,
)


# Valid status transitions
VALID_STATUS_TRANSITIONS: dict[ArticleStatus, list[ArticleStatus]] = {
    ArticleStatus.DISCOVERED: [
        ArticleStatus.EXTRACTED,
        ArticleStatus.USELESS,
        ArticleStatus.DRAFT,
    ],
    ArticleStatus.EXTRACTED: [
        ArticleStatus.TRANSLATED,
        ArticleStatus.USELESS,
        ArticleStatus.DRAFT,
    ],
    ArticleStatus.TRANSLATED: [
        ArticleStatus.PUBLISHED,
        ArticleStatus.USELESS,
        ArticleStatus.DRAFT,
    ],
    ArticleStatus.DRAFT: [
        ArticleStatus.EXTRACTED,
        ArticleStatus.TRANSLATED,
        ArticleStatus.USELESS,
    ],
    ArticleStatus.PUBLISHED: [],
    ArticleStatus.USELESS: [],
}


class ArticleService:
    """
    Service layer for article management operations.

    Coordinates between the article repository and business rules
    such as status transition validation and data enrichment.

    Args:
        session: Async SQLAlchemy session for the Articles database.
    """

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize the ArticleService with a database session.

        Args:
            session: Async SQLAlchemy session for the Articles database.
        """
        self.session = session

    def _article_to_response(self, article: Article) -> ArticleResponse:
        """Map an Article ORM model to an ArticleResponse schema."""
        return ArticleResponse(
            id=article.id,
            title=article.source_title,
            url=article.source_url,
            status=ArticleStatus(article.status),
            source_language="ru",
            target_language="uk",
            translated_content=article.target_content,
            editorial_notes=article.editorial_notes,
            created_at=article.created_at,
            updated_at=article.updated_at,
            tags=[tag.name for tag in article.tags] if article.tags else [],
            hubs=[hub.name for hub in article.hubs] if article.hubs else [],
        )

    async def list_articles(
        self,
        status_filter: Optional[ArticleStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ArticleListResponse:
        """
        List articles with optional filtering and pagination.

        Args:
            status_filter: Filter by ArticleStatus enum value.
            limit: Maximum number of articles to return.
            offset: Number of articles to skip.

        Returns:
            ArticleListResponse: Paginated list of articles with metadata.
        """
        query = select(Article)
        count_query = select(func.count(Article.id))

        if status_filter is not None:
            query = query.where(Article.status == status_filter.value)
            count_query = count_query.where(Article.status == status_filter.value)

        # Get total count
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        query = query.order_by(Article.id.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        articles = result.scalars().all()

        items = [self._article_to_response(a) for a in articles]

        return ArticleListResponse(
            items=items,
            meta=PaginationMeta(
                total=total,
                limit=limit,
                offset=offset,
                has_next=offset + limit < total,
            ),
        )

    async def get_article(self, article_id: int) -> ArticleResponse:
        """
        Retrieve a single article by ID with all related data.

        Args:
            article_id: The unique identifier of the article.

        Returns:
            ArticleResponse: Article details including tags, hubs, and images.

        Raises:
            HTTPException: 404 Not Found if article does not exist.
        """
        from sqlalchemy.orm import selectinload

        result = await self.session.execute(
            select(Article)
            .where(Article.id == article_id)
            .options(
                selectinload(Article.tags),
                selectinload(Article.hubs),
            )
        )
        article = result.scalar_one_or_none()

        if article is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article {article_id} not found",
            )

        return self._article_to_response(article)

    async def create_article(self, article_data: ArticleCreate) -> ArticleResponse:
        """
        Create a new article entry in the pipeline.

        Args:
            article_data: Article creation data including title, URL, and language.

        Returns:
            ArticleResponse: The created article with generated ID and timestamps.
        """
        # Create article ORM model from schema
        new_article = Article(
            habr_id=article_data.url,  # Use URL as habr_id for uniqueness
            source_url=article_data.url,
            source_title=article_data.title,
            source_content="",
            status=ArticleStatus.DISCOVERED.value,
        )
        self.session.add(new_article)
        await self.session.flush()
        await self.session.refresh(new_article)

        return self._article_to_response(new_article)

    async def update_article(
        self, article_id: int, update_data: ArticleUpdate
    ) -> ArticleResponse:
        """
        Update an existing article with provided fields.

        Only non-None fields in update_data are applied.

        Args:
            article_id: The unique identifier of the article to update.
            update_data: Fields to update.

        Returns:
            ArticleResponse: The updated article information.

        Raises:
            HTTPException: 404 Not Found if article does not exist.
        """
        # Fetch article by ID
        result = await self.session.execute(
            select(Article).where(Article.id == article_id)
        )
        article = result.scalar_one_or_none()

        if article is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article {article_id} not found",
            )

        # Apply non-None fields from update_data to the model
        if update_data.title is not None:
            article.source_title = update_data.title
        if update_data.status is not None:
            article.status = update_data.status.value
        if update_data.translated_content is not None:
            article.target_content = update_data.translated_content
        if update_data.editorial_notes is not None:
            article.editorial_notes = update_data.editorial_notes

        await self.session.flush()
        await self.session.refresh(article)

        return self._article_to_response(article)

    async def update_article_status(
        self, article_id: int, new_status: ArticleStatus
    ) -> ArticleResponse:
        """
        Update the status of an article with transition validation.

        Args:
            article_id: The unique identifier of the article.
            new_status: New ArticleStatus enum value.

        Returns:
            ArticleResponse: Updated article information.

        Raises:
            HTTPException: 404 Not Found if article does not exist.
            HTTPException: 400 Bad Request if status transition is invalid.
        """
        # Fetch article by ID
        result = await self.session.execute(
            select(Article).where(Article.id == article_id)
        )
        article = result.scalar_one_or_none()

        if article is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article {article_id} not found",
            )

        # Validate status transition
        current_status = ArticleStatus(article.status)
        allowed_transitions = VALID_STATUS_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_transitions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from {current_status.name} to {new_status.name}",
            )

        # Update status and persist
        article.status = new_status.value
        await self.session.flush()
        await self.session.refresh(article)

        return self._article_to_response(article)

    async def delete_article(self, article_id: int) -> None:
        """
        Delete an article and all associated data.

        This includes tags, hubs, images, and embeddings linked to the article.

        Args:
            article_id: The unique identifier of the article to delete.

        Raises:
            HTTPException: 404 Not Found if article does not exist.
        """
        from sqlalchemy.orm import selectinload

        # Fetch article by ID with relationships
        result = await self.session.execute(
            select(Article)
            .where(Article.id == article_id)
            .options(
                selectinload(Article.tags),
                selectinload(Article.hubs),
                selectinload(Article.images),
            )
        )
        article = result.scalar_one_or_none()

        if article is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article {article_id} not found",
            )

        # Delete associated records (tags, hubs, images, embeddings)
        # Clear relationships first
        article.tags.clear()
        article.hubs.clear()
        for image in article.images:
            await self.session.delete(image)

        # Delete the article itself
        await self.session.delete(article)
        await self.session.flush()
