"""
Tests for app.api.routes.articles — Article management API routes.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.articles import router as articles_router
from app.models.enums import ArticleStatus
from app.schemas import (
    ArticleResponse,
    ArticleListResponse,
    PaginationMeta,
)


@pytest.fixture
def app():
    """Create a FastAPI app with the articles router."""
    app = FastAPI()
    app.include_router(articles_router)
    return app


@pytest.fixture
def client(app):
    """Create a TestClient for the articles router."""
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# list_articles
# ---------------------------------------------------------------------------

def test_list_articles_returns_200(client):
    """GET /articles/ returns 200 with paginated article list."""
    now = datetime.now(timezone.utc).isoformat()

    mock_response = ArticleListResponse(
        items=[
            ArticleResponse(
                id=1,
                title="Test Article",
                url="https://example.com/1",
                status=ArticleStatus.DISCOVERED,
                source_language="ru",
                target_language="uk",
                translated_content=None,
                editorial_notes=None,
                created_at=now,
                updated_at=now,
                tags=[],
                hubs=[],
            )
        ],
        meta=PaginationMeta(total=1, limit=50, offset=0, has_next=False),
    )

    mock_service = MagicMock()
    mock_service.list_articles = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.get("/articles/")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["meta"]["total"] == 1


def test_list_articles_with_status_filter(client):
    """GET /articles/?status=published filters by status."""
    mock_response = ArticleListResponse(
        items=[],
        meta=PaginationMeta(total=0, limit=50, offset=0, has_next=False),
    )

    mock_service = MagicMock()
    mock_service.list_articles = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.get("/articles/?status=published")

    assert response.status_code == 200
    mock_service.list_articles.assert_called_once()


def test_list_articles_with_pagination_params(client):
    """GET /articles/?limit=10&offset=5 passes pagination params."""
    mock_response = ArticleListResponse(
        items=[],
        meta=PaginationMeta(total=0, limit=10, offset=5, has_next=False),
    )

    mock_service = MagicMock()
    mock_service.list_articles = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.get("/articles/?limit=10&offset=5")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# get_article
# ---------------------------------------------------------------------------

def test_get_article_returns_200(client):
    """GET /articles/{id} returns 200 with article details."""
    now = datetime.now(timezone.utc).isoformat()

    mock_response = ArticleResponse(
        id=1,
        title="Test Article",
        url="https://example.com/1",
        status=ArticleStatus.DISCOVERED,
        source_language="ru",
        target_language="uk",
        translated_content=None,
        editorial_notes=None,
        created_at=now,
        updated_at=now,
        tags=["python"],
        hubs=["development"],
    )

    mock_service = MagicMock()
    mock_service.get_article = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.get("/articles/1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["title"] == "Test Article"
    assert data["tags"] == ["python"]
    assert data["hubs"] == ["development"]


def test_get_article_returns_404(client):
    """GET /articles/{id} returns 404 when article not found."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.get_article = AsyncMock(
        side_effect=HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article 999 not found")
    )

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.get("/articles/999")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# create_article
# ---------------------------------------------------------------------------

def test_create_article_returns_201(client):
    """POST /articles/ returns 201 with created article."""
    now = datetime.now(timezone.utc).isoformat()

    mock_response = ArticleResponse(
        id=1,
        title="New Article",
        url="https://example.com/new",
        status=ArticleStatus.DISCOVERED,
        source_language="ru",
        target_language="uk",
        translated_content=None,
        editorial_notes=None,
        created_at=now,
        updated_at=now,
        tags=[],
        hubs=[],
    )

    mock_service = MagicMock()
    mock_service.create_article = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.post(
            "/articles/",
            json={"title": "New Article", "url": "https://example.com/new"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Article"
    assert data["status"] == "discovered"


def test_create_article_validation_error(client):
    """POST /articles/ returns 422 when required fields are missing."""
    response = client.post("/articles/", json={})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# update_article
# ---------------------------------------------------------------------------

def test_update_article_returns_200(client):
    """PUT /articles/{id} returns 200 with updated article."""
    now = datetime.now(timezone.utc).isoformat()

    mock_response = ArticleResponse(
        id=1,
        title="Updated Title",
        url="https://example.com/1",
        status=ArticleStatus.DRAFT,
        source_language="ru",
        target_language="uk",
        translated_content=None,
        editorial_notes=None,
        created_at=now,
        updated_at=now,
        tags=[],
        hubs=[],
    )

    mock_service = MagicMock()
    mock_service.update_article = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.put(
            "/articles/1",
            json={"title": "Updated Title"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"


def test_update_article_returns_404(client):
    """PUT /articles/{id} returns 404 when article not found."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.update_article = AsyncMock(
        side_effect=HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article 999 not found")
    )

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.put("/articles/999", json={"title": "Updated"})

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# update_article_status
# ---------------------------------------------------------------------------

def test_update_article_status_returns_200(client):
    """PUT /articles/{id}/status returns 200 with updated article."""
    now = datetime.now(timezone.utc).isoformat()

    mock_response = ArticleResponse(
        id=1,
        title="Test",
        url="https://example.com/1",
        status=ArticleStatus.EXTRACTED,
        source_language="ru",
        target_language="uk",
        translated_content=None,
        editorial_notes=None,
        created_at=now,
        updated_at=now,
        tags=[],
        hubs=[],
    )

    mock_service = MagicMock()
    mock_service.update_article_status = AsyncMock(return_value=mock_response)

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.put("/articles/1/status?new_status=extracted")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "extracted"


def test_update_article_status_returns_400_invalid_transition(client):
    """PUT /articles/{id}/status returns 400 for invalid transition."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.update_article_status = AsyncMock(
        side_effect=HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status transition from published to draft",
        )
    )

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.put("/articles/1/status?new_status=draft")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# delete_article
# ---------------------------------------------------------------------------

def test_delete_article_returns_204(client):
    """DELETE /articles/{id} returns 204 on success."""
    mock_service = MagicMock()
    mock_service.delete_article = AsyncMock(return_value=None)

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.delete("/articles/1")

    assert response.status_code == 204


def test_delete_article_returns_404(client):
    """DELETE /articles/{id} returns 404 when article not found."""
    from fastapi import HTTPException, status

    mock_service = MagicMock()
    mock_service.delete_article = AsyncMock(
        side_effect=HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article 999 not found")
    )

    with patch("app.api.routes.articles.ArticleService", return_value=mock_service):
        response = client.delete("/articles/999")

    assert response.status_code == 404
