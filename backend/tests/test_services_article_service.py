"""
Tests for app.services.article_service — ArticleService business logic.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.article_service import ArticleService, VALID_STATUS_TRANSITIONS
from app.models.article import Article, Tag, Hub, Image
from app.models.enums import ArticleStatus
from app.schemas import (
    ArticleCreate,
    ArticleUpdate,
    ArticleResponse,
    ArticleListResponse,
    PaginationMeta,
)


# ---------------------------------------------------------------------------
# VALID_STATUS_TRANSITIONS
# ---------------------------------------------------------------------------

def test_valid_status_transitions_has_all_statuses():
    """All ArticleStatus values should be keys in VALID_STATUS_TRANSITIONS."""
    for s in ArticleStatus:
        assert s in VALID_STATUS_TRANSITIONS


def test_published_has_no_valid_transitions():
    """PUBLISHED status should have no valid transitions."""
    assert VALID_STATUS_TRANSITIONS[ArticleStatus.PUBLISHED] == []


def test_useless_has_no_valid_transitions():
    """USELESS status should have no valid transitions."""
    assert VALID_STATUS_TRANSITIONS[ArticleStatus.USELESS] == []


def test_discovered_can_transition_to_extracted():
    """DISCOVERED can transition to EXTRACTED."""
    assert ArticleStatus.EXTRACTED in VALID_STATUS_TRANSITIONS[ArticleStatus.DISCOVERED]


def test_discovered_can_transition_to_useless():
    """DISCOVERED can transition to USELESS."""
    assert ArticleStatus.USELESS in VALID_STATUS_TRANSITIONS[ArticleStatus.DISCOVERED]


def test_discovered_can_transition_to_draft():
    """DISCOVERED can transition to DRAFT."""
    assert ArticleStatus.DRAFT in VALID_STATUS_TRANSITIONS[ArticleStatus.DISCOVERED]


def test_extracted_can_transition_to_translated():
    """EXTRACTED can transition to TRANSLATED."""
    assert ArticleStatus.TRANSLATED in VALID_STATUS_TRANSITIONS[ArticleStatus.EXTRACTED]


def test_translated_can_transition_to_published():
    """TRANSLATED can transition to PUBLISHED."""
    assert ArticleStatus.PUBLISHED in VALID_STATUS_TRANSITIONS[ArticleStatus.TRANSLATED]


def test_draft_can_transition_to_extracted():
    """DRAFT can transition to EXTRACTED."""
    assert ArticleStatus.EXTRACTED in VALID_STATUS_TRANSITIONS[ArticleStatus.DRAFT]


# ---------------------------------------------------------------------------
# _article_to_response
# ---------------------------------------------------------------------------

def test_article_to_response_maps_fields():
    """_article_to_response correctly maps Article ORM to ArticleResponse."""
    now = datetime.now(timezone.utc)
    article = MagicMock(spec=Article)
    article.id = 1
    article.source_title = "Test Article"
    article.source_url = "https://example.com/1"
    article.status = ArticleStatus.DISCOVERED.value
    article.target_content = "Translated text"
    article.editorial_notes = "Some notes"
    article.created_at = now
    article.updated_at = now

    tag = MagicMock()
    tag.name = "python"
    hub = MagicMock()
    hub.name = "development"
    article.tags = [tag]
    article.hubs = [hub]

    service = ArticleService(AsyncMock(spec=AsyncSession))
    result = service._article_to_response(article)

    assert isinstance(result, ArticleResponse)
    assert result.id == 1
    assert result.title == "Test Article"
    assert result.url == "https://example.com/1"
    assert result.status == ArticleStatus.DISCOVERED
    assert result.source_language == "ru"
    assert result.target_language == "uk"
    assert result.translated_content == "Translated text"
    assert result.editorial_notes == "Some notes"
    assert result.tags == ["python"]
    assert result.hubs == ["development"]


def test_article_to_response_handles_empty_relationships():
    """_article_to_response handles articles with no tags or hubs."""
    now = datetime.now(timezone.utc)
    article = MagicMock(spec=Article)
    article.id = 2
    article.source_title = "No Tags"
    article.source_url = "https://example.com/2"
    article.status = ArticleStatus.DRAFT.value
    article.target_content = None
    article.editorial_notes = None
    article.created_at = now
    article.updated_at = now
    article.tags = []
    article.hubs = []

    service = ArticleService(AsyncMock(spec=AsyncSession))
    result = service._article_to_response(article)

    assert result.tags == []
    assert result.hubs == []


# ---------------------------------------------------------------------------
# list_articles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_articles_returns_paginated_response():
    """list_articles returns ArticleListResponse with items and metadata."""
    now = datetime.now(timezone.utc)
    article = MagicMock(spec=Article)
    article.id = 1
    article.source_title = "Test"
    article.source_url = "https://example.com"
    article.status = ArticleStatus.DISCOVERED.value
    article.target_content = None
    article.editorial_notes = None
    article.created_at = now
    article.updated_at = now
    article.tags = []
    article.hubs = []

    mock_session = AsyncMock(spec=AsyncSession)

    count_result = MagicMock()
    count_result.scalar.return_value = 1

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [article]

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return count_result
        return list_result

    mock_session.execute = mock_execute

    service = ArticleService(mock_session)
    result = await service.list_articles(limit=10, offset=0)

    assert isinstance(result, ArticleListResponse)
    assert len(result.items) == 1
    assert result.meta.total == 1
    assert result.meta.limit == 10
    assert result.meta.offset == 0
    assert result.meta.has_next is False


@pytest.mark.asyncio
async def test_list_articles_filters_by_status():
    """list_articles applies status filter when provided."""
    mock_session = AsyncMock(spec=AsyncSession)

    count_result = MagicMock()
    count_result.scalar.return_value = 0
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return count_result
        return list_result

    mock_session.execute = mock_execute

    service = ArticleService(mock_session)
    await service.list_articles(status_filter=ArticleStatus.PUBLISHED, limit=10, offset=0)

    # Verify the query was built with the filter — check execute was called twice
    assert mock_session.execute.call_count == 2


@pytest.mark.asyncio
async def test_list_articles_has_next_true():
    """list_articles sets has_next=True when more items exist."""
    mock_session = AsyncMock(spec=AsyncSession)

    count_result = MagicMock()
    count_result.scalar.return_value = 100
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = []

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return count_result
        return list_result

    mock_session.execute = mock_execute

    service = ArticleService(mock_session)
    result = await service.list_articles(limit=10, offset=0)

    assert result.meta.has_next is True


# ---------------------------------------------------------------------------
# get_article
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_article_returns_article_response():
    """get_article returns ArticleResponse for a valid article ID."""
    now = datetime.now(timezone.utc)
    article = MagicMock(spec=Article)
    article.id = 1
    article.source_title = "Test"
    article.source_url = "https://example.com"
    article.status = ArticleStatus.DISCOVERED.value
    article.target_content = None
    article.editorial_notes = None
    article.created_at = now
    article.updated_at = now
    article.tags = []
    article.hubs = []

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = article
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = ArticleService(mock_session)
    result = await service.get_article(1)

    assert isinstance(result, ArticleResponse)
    assert result.id == 1


@pytest.mark.asyncio
async def test_get_article_raises_404_not_found():
    """get_article raises 404 when article does not exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = ArticleService(mock_session)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_article(999)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# create_article
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_article_returns_article_response():
    """create_article creates an article and returns ArticleResponse."""
    now = datetime.now(timezone.utc)
    mock_session = AsyncMock(spec=AsyncSession)

    async def mock_flush():
        pass

    async def mock_refresh(obj):
        obj.id = 1
        obj.created_at = now
        obj.updated_at = now

    mock_session.flush = mock_flush
    mock_session.refresh = mock_refresh

    service = ArticleService(mock_session)
    article_data = ArticleCreate(
        title="New Article",
        url="https://example.com/new",
    )

    result = await service.create_article(article_data)

    assert isinstance(result, ArticleResponse)
    assert result.title == "New Article"
    assert result.url == "https://example.com/new"
    assert result.status == ArticleStatus.DISCOVERED
    mock_session.add.assert_called_once()


# ---------------------------------------------------------------------------
# update_article
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_article_updates_title():
    """update_article updates the title field."""
    now = datetime.now(timezone.utc)
    article = MagicMock(spec=Article)
    article.id = 1
    article.source_title = "Old Title"
    article.source_url = "https://example.com"
    article.status = ArticleStatus.DISCOVERED.value
    article.target_content = None
    article.editorial_notes = None
    article.created_at = now
    article.updated_at = now
    article.tags = []
    article.hubs = []

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = article
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = ArticleService(mock_session)
    update_data = ArticleUpdate(title="New Title")

    result = await service.update_article(1, update_data)

    assert article.source_title == "New Title"
    assert result.title == "New Title"


@pytest.mark.asyncio
async def test_update_article_updates_status():
    """update_article updates the status field."""
    now = datetime.now(timezone.utc)
    article = MagicMock(spec=Article)
    article.id = 1
    article.source_title = "Test"
    article.source_url = "https://example.com"
    article.status = ArticleStatus.DISCOVERED.value
    article.target_content = None
    article.editorial_notes = None
    article.created_at = now
    article.updated_at = now
    article.tags = []
    article.hubs = []

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = article
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = ArticleService(mock_session)
    update_data = ArticleUpdate(status=ArticleStatus.EXTRACTED)

    result = await service.update_article(1, update_data)

    assert article.status == ArticleStatus.EXTRACTED.value
    assert result.status == ArticleStatus.EXTRACTED


@pytest.mark.asyncio
async def test_update_article_raises_404_not_found():
    """update_article raises 404 when article does not exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = ArticleService(mock_session)
    update_data = ArticleUpdate(title="New Title")

    with pytest.raises(HTTPException) as exc_info:
        await service.update_article(999, update_data)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# update_article_status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_article_status_valid_transition():
    """update_article_status succeeds for a valid status transition."""
    now = datetime.now(timezone.utc)
    article = MagicMock(spec=Article)
    article.id = 1
    article.source_title = "Test"
    article.source_url = "https://example.com"
    article.status = ArticleStatus.DISCOVERED.value
    article.target_content = None
    article.editorial_notes = None
    article.created_at = now
    article.updated_at = now
    article.tags = []
    article.hubs = []

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = article
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = ArticleService(mock_session)
    result = await service.update_article_status(1, ArticleStatus.EXTRACTED)

    assert article.status == ArticleStatus.EXTRACTED.value
    assert result.status == ArticleStatus.EXTRACTED


@pytest.mark.asyncio
async def test_update_article_status_invalid_transition():
    """update_article_status raises 400 for an invalid status transition."""
    now = datetime.now(timezone.utc)
    article = MagicMock(spec=Article)
    article.id = 1
    article.source_title = "Test"
    article.source_url = "https://example.com"
    article.status = ArticleStatus.PUBLISHED.value
    article.target_content = None
    article.editorial_notes = None
    article.created_at = now
    article.updated_at = now
    article.tags = []
    article.hubs = []

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = article
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = ArticleService(mock_session)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_article_status(1, ArticleStatus.DRAFT)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid status transition" in exc_info.value.detail


@pytest.mark.asyncio
async def test_update_article_status_raises_404_not_found():
    """update_article_status raises 404 when article does not exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = ArticleService(mock_session)

    with pytest.raises(HTTPException) as exc_info:
        await service.update_article_status(999, ArticleStatus.EXTRACTED)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# delete_article
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_article_succeeds():
    """delete_article deletes the article and its relationships."""
    now = datetime.now(timezone.utc)
    article = MagicMock(spec=Article)
    article.id = 1
    article.tags = []
    article.hubs = []
    article.images = []

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = article
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = ArticleService(mock_session)
    await service.delete_article(1)

    mock_session.delete.assert_called_once_with(article)


@pytest.mark.asyncio
async def test_delete_article_clears_relationships():
    """delete_article clears tags, hubs, and deletes images."""
    article = MagicMock(spec=Article)
    article.id = 1
    article.tags = [MagicMock()]
    article.hubs = [MagicMock()]
    image = MagicMock()
    article.images = [image]

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = article
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = ArticleService(mock_session)
    await service.delete_article(1)

    article.tags.clear.assert_called_once()
    article.hubs.clear.assert_called_once()
    mock_session.delete.assert_any_call(image)


@pytest.mark.asyncio
async def test_delete_article_raises_404_not_found():
    """delete_article raises 404 when article does not exist."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    service = ArticleService(mock_session)

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_article(999)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
